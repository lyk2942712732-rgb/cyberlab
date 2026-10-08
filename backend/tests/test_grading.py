import pytest
from app.grading import calculate_score
from app.models import LabAssessment
from app.orchestrator.lab_orchestrator import LabOrchestrator
from app.services.scores import ScoreService
from app.services.sessions import SessionService
from tests.test_sessions import start_ready


def inputs(band="result", adjustment=5):
    decision = {"band": band, "reason": "已看到成功响应。", "evidence_ids": ["g1:e1"],
                "adjustment": adjustment, "adjustment_reason": "通过对照调整了输入。",
                "adjustment_evidence_ids": ["g1:e1"], "adjustment_basis": "targeted_adjustment"}
    evidence = {"events": [{"id": "g1:e1", "type": "web.submit"}], "submissions": [],
                "capture_complete": True, "truncated": False}
    criteria = [{"key": key, "verdict": "achieved", "evidence_ids": ["g1:e1"]}
                for key in ("method", "verification", "strategy")]
    return decision, evidence, criteria


@pytest.mark.parametrize("band,expected", [("preparation", 25), ("attempt", 55), ("progress", 75), ("result", 89)])
def test_anchor_and_adjustment_cannot_cross_band(band, expected):
    result = calculate_score(*inputs(band))
    assert result["score"] == expected
    assert result["score"] == result["baseline"] + result["adjustment"]


def test_correct_submission_overrides_model_band_but_missing_capture_cannot_earn_bonus():
    decision, evidence, criteria = inputs("unscored")
    evidence["submissions"] = [{"id": "submission:1", "correct": True}]
    evidence["capture_complete"] = False
    result = calculate_score(decision, evidence, criteria)
    assert (result["band"], result["score"], result["adjustment"]) == ("verified", 95, 0)
    assert result["evidence_ids"] == ["submission:1"]
    evidence["capture_complete"] = True
    assert calculate_score(decision, evidence, criteria)["score"] == 100


@pytest.mark.parametrize("change", ["capture", "truncated", "empty"])
def test_insufficient_capture_is_unscored_not_zero(change):
    decision, evidence, criteria = inputs()
    if change == "capture":
        evidence["capture_complete"] = False
    elif change == "truncated":
        evidence["truncated"] = True
    else:
        evidence["events"] = []
        decision["evidence_ids"] = decision["adjustment_evidence_ids"] = []
    assert calculate_score(decision, evidence, criteria)["score"] is None


def test_fabricated_pass_unknown_citations_and_unbounded_adjustments_rejected():
    decision, evidence, criteria = inputs("verified")
    with pytest.raises(ValueError, match="correct submission"):
        calculate_score(decision, evidence, criteria)
    decision["band"] = "attempt"
    for delta in (6, -6, True, 2.5):
        with pytest.raises(ValueError):
            calculate_score({**decision, "adjustment": delta}, evidence, criteria)
    with pytest.raises(ValueError, match="Unknown scoring citation"):
        calculate_score({**decision, "adjustment_evidence_ids": ["invented"]}, evidence, criteria)
    evidence["events"][0]["type"] = "web.navigate"
    with pytest.raises(ValueError, match="recorded input"):
        calculate_score(decision, evidence, criteria)


def test_no_penalty_for_missing_explanation_or_corrected_errors():
    decision, evidence, criteria = inputs("attempt", -3)
    decision["adjustment_basis"] = "clear_explanation"
    assert calculate_score(decision, evidence, criteria)["score"] == 50
    decision["adjustment_basis"] = "unresolved_error"
    assert calculate_score(decision, evidence, criteria)["score"] == 50
    criteria[0]["verdict"] = "needs_work"
    assert calculate_score(decision, evidence, criteria)["score"] == 47
    criteria[0]["evidence_ids"] = []
    assert calculate_score(decision, evidence, criteria)["score"] == 50


def test_best_assessment_score_is_owned_and_ungraded_is_excluded(db, users, lab, runtime):
    service = ScoreService(db)
    assert service.scores(users["student01"].id)[0]["score"] is None
    assert next(s for s in service.students() if s["id"] == users["student01"].id)["average_score"] is None
    identifiers = []
    for user, score in (("student01", 95), ("student01", 70), ("student02", 100)):
        session = start_ready(db, lab, users[user], runtime)
        if score == 95:
            SessionService(db).submit(session.id, users[user], "flag{expected}")
        LabOrchestrator(runtime).stop(db, session)
        db.commit()
        job = db.get(LabAssessment, session.id)
        job.status = "COMPLETED"
        job.report = {"schema_version": 3, "scoring": {"policy_version": 1, "status": "scored", "score": score}}
        identifiers.append(session.id)
        db.commit()
    score = service.scores(users["student01"].id)[0]
    assert score["score"] == 95 and score["score_session_id"] == identifiers[0]
    assert score["completed"] and score["flag_score"] == 100
    assert next(s for s in service.students() if s["id"] == users["student01"].id)["average_score"] == 95
    # Old reports retain Flag completion but cannot create a synthetic AI grade.
    for identifier in identifiers[:2]:
        db.get(LabAssessment, identifier).report = {"schema_version": 2, "summary": "历史报告"}
    db.commit()
    score = service.scores(users["student01"].id)[0]
    assert score["score"] is None and score["completed"]
