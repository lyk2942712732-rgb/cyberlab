import copy
import json
from datetime import timedelta
from unittest.mock import Mock
from urllib.parse import unquote
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker
from app.assessment import collect_evidence, evaluate, learning_reference, redact, validate_report
from app import assessment_worker
from app.core.config import settings
from app.core.db import utcnow
from app.models import LabAssessment, Submission
from app.orchestrator.lab_orchestrator import LabOrchestrator
from app.services.assessments import enqueue
from app.services.sessions import SessionService
from tests.test_sessions import start_ready


def report():
    return {"schema_version": 3, "scoring": {"band": "unscored", "reason": "尚无充分记录。", "evidence_ids": [],
            "adjustment": 0, "adjustment_reason": "暂不评分。", "adjustment_evidence_ids": [], "adjustment_basis": "none"}, "summary": "你尝试了修改输入，实际结果尚无法确认。",
            "path": [{"title": "调整输入", "text": "你修改了输入。", "evidence_ids": ["g1:e1"]}],
            "reasoning": {"text": "从修改输入看，你可能在尝试改变查询边界。", "evidence_ids": ["g1:e1"]},
            "criteria": [{"key": key, "verdict": "insufficient_evidence", "text": "需要对应结果。", "evidence_ids": []}
                         for key in ("method", "verification")],
            "suggestions": [{"text": "对比修改前后的响应。", "evidence_ids": []}], "limitations": []}


@pytest.mark.parametrize("reason", ["stop", "expiry", "failure"])
def test_end_automatically_enqueues_once_and_snapshots_reference(db, lab, users, runtime, reason):
    lab.writeup = "# 原始题解"
    db.commit()
    if reason == "failure":
        runtime.fail_on_type = "TARGET"
    session = start_ready(db, lab, users["student01"], runtime)
    if reason != "failure":
        assert db.get(LabAssessment, session.id) is None
        if reason == "stop":
            SessionService(db).command(session.id, users["student01"], "stop")
        else:
            session.expires_at = utcnow() - timedelta(seconds=1)
        LabOrchestrator(runtime).reconcile(db, session)
        db.commit()
    job = db.get(LabAssessment, session.id)
    assert job.status == "QUEUED"
    assert job.reference["writeup"] == "# 原始题解"
    lab.writeup = "修改后的题解"
    enqueue(db, session)
    db.commit()
    assert job.reference["writeup"] == "# 原始题解"
    assert db.scalar(select(func.count()).select_from(LabAssessment)) == 1


def test_owner_access_manual_history_and_idempotent_retry(client, headers, db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    path = f"/api/lab-sessions/{session.id}/assessment"
    assert client.get(path).status_code == 401
    for method in (client.get, client.post):
        assert method(path, headers=headers["student02"]).status_code == 404
    assert client.post(path, headers=headers["student01"]).status_code == 409
    # An old session without a job can be evaluated explicitly.
    session.status = "DESTROYED"
    db.commit()
    assert client.get(path, headers=headers["student01"]).json()["data"]["status"] == "NOT_REQUESTED"
    for _ in range(2):
        assert client.post(path, headers=headers["student01"]).status_code == 202
    job = db.get(LabAssessment, session.id)
    job.status, job.error, job.attempts = "FAILED", "临时失败", 3
    db.commit()
    assert client.post(path, headers=headers["student01"]).json()["data"]["status"] == "QUEUED"
    assert job.attempts == 0 and job.error is None
    assert client.get('/api/me/assessments', headers=headers["student02"]).json()["data"] == []
    assert len(client.get('/api/me/assessments', headers=headers["student01"]).json()["data"]) == 1
    job.status, job.report = "COMPLETED", report()
    db.commit()
    assert client.post(path, headers=headers["student01"]).json()["data"]["status"] == "COMPLETED"
    assert client.get(path, headers=headers["admin"]).status_code == 200


def test_redaction_preserves_learning_inputs_and_removes_encoded_credentials():
    raw = {"url": "http://target/login?username=admin%27%20--&%70assword=private123&PASSWORD=other456",
           "page": "http://target/?redirect=http%3A%2F%2Ftarget%2F%3Fpassword%3Dnested789",
           "fields": [{"name": "password", "value": "value_secret"}, {"name": "username", "value": "admin ' --"}],
           "command": "curl --password 'shell_secret' http://target; TOKEN=env_secret",
           "note": "Bearer token_secret flag{actual_value}"}
    cleaned = redact(raw)
    text = unquote(json.dumps(cleaned, ensure_ascii=False))
    for secret in ("private123", "other456", "nested789", "value_secret", "shell_secret", "env_secret", "token_secret", "actual_value"):
        assert secret not in text
    assert cleaned["fields"][1]["value"] == "admin ' --"
    assert "username=admin%27%20--" in cleaned["url"]
    assert raw["fields"][0]["value"] == "value_secret"


def test_collects_all_pages_and_generations_without_submitted_flags(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    SessionService(db).submit(session.id, users["student01"], "flag{expected}")
    client = Mock()
    def page(identifier, generation, after):
        generation = generation or 2
        count = 100 if generation == 1 and after == 0 else 2
        return {"generations": [1, 2], "state": {"complete": True, "status": "finished"},
                "events": [{"seq": after + i, "timestamp": 1, "type": "terminal.submit", "data": {"command": f"echo {i}"}}
                           for i in range(1, count + 1)], "next": 100 if count == 100 else None}
    client.session_activity.side_effect = page
    evidence = collect_evidence(db, session.id, client)
    assert len(evidence["events"]) == 104
    assert {e["id"] for e in evidence["events"]} >= {"g1:e1", "g1:e102", "g2:e2"}
    assert evidence["capture_complete"] and evidence["flag_correct"]
    assert "flag{expected}" not in json.dumps(evidence)
    assert db.scalar(select(Submission)).submitted_flag == "flag{expected}"


def test_validation_rejects_fabricated_citations_and_missing_dimensions():
    evidence = {"events": [{"id": "g1:e1"}], "submissions": []}
    value = report()
    assert validate_report(value, evidence)["summary"]
    wrong = copy.deepcopy(value)
    wrong["path"][0]["evidence_ids"] = ["g9:e999"]
    with pytest.raises(ValueError):
        validate_report(wrong, evidence)
    wrong = copy.deepcopy(value)
    wrong["criteria"][1]["key"] = "method"
    with pytest.raises(ValueError):
        validate_report(wrong, evidence)
    value["criteria"][0]["verdict"] = "achieved"
    assert validate_report(value, evidence)["criteria"][0]["verdict"] == "insufficient_evidence"


def test_deepseek_request_and_output_validation(monkeypatch):
    monkeypatch.setattr(settings(), "deepseek_api_key", "test-provider-key")
    response = httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(report())}}], "usage": {"total_tokens": 100}},
                              request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"))
    post = Mock(return_value=response)
    monkeypatch.setattr(httpx.Client, "post", post)
    evidence = {"events": [{"id": "g1:e1"}], "submissions": [], "truncated": False, "capture_complete": True}
    result = evaluate({"writeup": "教师题解"}, evidence)
    assert result["usage"]["total_tokens"] == 100
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "deepseek-flash"
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"
    assert payload["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("field", ["summary", "stage", "criterion", "reasoning", "suggestions", "limitations"])
def test_internal_identifiers_stay_in_citations_not_student_prose(field):
    evidence = {"events": [{"id": "g1:e1"}], "submissions": []}
    value = report()
    assert validate_report(value, evidence)["path"][0]["evidence_ids"] == ["g1:e1"]
    text = "你的操作已记录（g1:e1）。"
    if field == "stage":
        value["path"][0]["title"] = text
    elif field == "criterion":
        value["criteria"][0]["text"] = text
    elif field == "reasoning":
        value[field]["text"] = text
    elif field == "suggestions":
        value[field][0]["text"] = text
    elif field == "limitations":
        value[field] = [text]
    else:
        value[field] = text
    with pytest.raises(ValueError, match="Internal evidence identifiers"):
        validate_report(value, evidence)


def test_reference_retains_lab_content_without_shared_evaluator_footer():
    original = {"writeup": "# SQL\n步骤与常见失败\n## 学习验收与评估约定\n评估器事件规则"}
    assert learning_reference(original)["writeup"] == "# SQL\n步骤与常见失败"
    assert "评估器事件规则" in original["writeup"]
    assert learning_reference({"writeup": "自定义题解"})["writeup"] == "自定义题解"


@pytest.mark.parametrize("internal", ["correct=true", "capture_complete", "flag_correct"])
def test_internal_status_fields_are_not_student_feedback(internal):
    value = report()
    value["summary"] = "本次判题 " + internal
    with pytest.raises(ValueError, match="Internal evidence identifiers"):
        validate_report(value, {"events": [{"id": "g1:e1"}], "submissions": []})


def test_worker_persists_success_and_recovers_failure(db, lab, users, runtime, monkeypatch):
    session = start_ready(db, lab, users["student01"], runtime)
    LabOrchestrator(runtime).stop(db, session)
    db.commit()
    monkeypatch.setattr(assessment_worker, "SessionLocal", sessionmaker(db.get_bind(), expire_on_commit=False))
    evidence = {"events": [{"id": "g1:e1"}], "submissions": []}
    monkeypatch.setattr(assessment_worker, "collect_evidence", Mock(return_value=evidence))
    evaluator = Mock(side_effect=ValueError("private error body must not be saved"))
    monkeypatch.setattr(assessment_worker, "evaluate", evaluator)
    identifier = assessment_worker.claim(db)
    db.commit()
    assert identifier == session.id
    assert assessment_worker.claim(db) is None
    db.commit()
    assessment_worker.process(identifier)
    db.expire_all()
    job = db.get(LabAssessment, identifier)
    assert job.status == "QUEUED" and "private" not in job.error
    assert job.evidence == evidence
    job.available_at = utcnow() - timedelta(seconds=1)
    db.commit()
    evaluator.side_effect = None
    evaluator.return_value = report()
    assert assessment_worker.claim(db) == identifier
    db.commit()
    assessment_worker.process(identifier)
    db.expire_all()
    assert job.status == "COMPLETED" and job.report == report()
    assert job.completed_at


def test_stale_jobs_recover_with_bounded_attempts(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    LabOrchestrator(runtime).stop(db, session)
    db.commit()
    job = db.get(LabAssessment, session.id)
    job.status, job.attempts = "RUNNING", 1
    job.updated_at = utcnow() - timedelta(minutes=11)
    db.commit()
    assert assessment_worker.claim(db) == session.id
    db.commit()
    assert job.attempts == 2 and job.status == "RUNNING"
    job.attempts = 3
    job.updated_at = utcnow() - timedelta(minutes=11)
    db.commit()
    assert assessment_worker.claim(db) is None
    assert job.status == "FAILED"


def test_optional_dimensions_and_duplicate_advice_are_omitted():
    evidence = {"events": [{"id": "g1:e1"}], "submissions": []}
    value = report()
    value["criteria"].append({"key": "understanding", "verdict": "insufficient_evidence", "text": "未记录解释。", "evidence_ids": []})
    value["criteria"].append({"key": "strategy", "verdict": "partial", "text": "你调整了输入。", "evidence_ids": ["g1:e1"]})
    value["suggestions"].append({"text": "对比修改前后的响应！", "evidence_ids": ["g1:e1"]})
    result = validate_report(value, evidence)
    assert [c["key"] for c in result["criteria"]] == ["method", "verification", "strategy"]
    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["evidence_ids"] == ["g1:e1"]
    value["reasoning"]["evidence_ids"] = []
    with pytest.raises(ValueError, match="Reasoning without supporting"):
        validate_report(value, evidence)


def test_legacy_report_upgrade_is_explicit_and_idempotent(db, lab, users, runtime):
    from app.services.assessments import AssessmentService
    session = start_ready(db, lab, users["student01"], runtime)
    LabOrchestrator(runtime).stop(db, session)
    db.commit()
    job = db.get(LabAssessment, session.id)
    old = {"summary": "历史反馈", "approach": []}
    job.status, job.report = "COMPLETED", old
    db.commit()
    service = AssessmentService(db)
    assert service.get(session.id, users["student01"])["status"] == "COMPLETED"
    assert service.request(session.id, users["student01"])["status"] == "QUEUED"
    job.attempts = 1
    db.commit()
    assert service.request(session.id, users["student01"])["status"] == "QUEUED"
    assert job.attempts == 1 and job.report == old
    job.status, job.report = "COMPLETED", report()
    db.commit()
    assert service.request(session.id, users["student01"])["status"] == "COMPLETED"


def test_sql_placeholders_remain_readable_in_feedback():
    assert redact("username = ? AND password = ?") == "username = ? AND password = ?"
    assert redact("password = %s") == "password = %s"
    assert "private123" not in redact("password = private123")
