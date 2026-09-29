from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.core.db import aware, utcnow
from app.models import LabInstance, LabSession, Submission
from app.orchestrator.lab_orchestrator import LabOrchestrator
from app.services.sessions import SessionService


def start_ready(db, lab, user, runtime):
    service = SessionService(db)
    data = service.start(lab.id, user)
    session = db.get(LabSession, data["id"])
    LabOrchestrator(runtime).reconcile(db, session)
    db.commit()
    return session


def test_start_is_idempotent_and_returns_async_status(client, headers, lab):
    first = client.post(f"/api/labs/{lab.id}/sessions", headers=headers["student01"])
    second = client.post(f"/api/labs/{lab.id}/sessions", headers=headers["student01"])
    assert first.status_code == second.status_code == 202
    assert first.json()["data"]["status"] == "CREATING"
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert "flag{expected}" not in first.text


def test_students_are_isolated_and_admin_can_inspect(client, headers, lab):
    sid = client.post(f"/api/labs/{lab.id}/sessions", headers=headers["student01"]).json()["data"]["id"]
    for method, suffix, payload in (("get", "", None), ("post", "/reset", None), ("post", "/stop", None), ("post", "/submit", {"flag": "x"}), ("post", "/desktop-ticket", None)):
        response = client.request(method, f"/api/lab-sessions/{sid}{suffix}", headers=headers["student02"], json=payload)
        assert response.status_code == 404
    assert client.get(f"/api/lab-sessions/{sid}", headers=headers["admin"]).status_code == 200


def test_start_creates_two_containers_one_network_and_pins_image(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    assert session.status == "READY"
    specs = list(runtime.containers.values())
    assert len(specs) == 2 and len(runtime.networks) == 1
    assert {s.instance_type for s in specs} == {"KALI", "TARGET"}
    assert len({s.network_id for s in specs}) == 1
    target = next(s for s in specs if s.instance_type == "TARGET")
    assert target.image == "sha256:target"
    assert target.cpu == lab.cpu_limit and target.memory_mb == lab.memory_limit
    assert SessionService(db).describe(session)["target_ip"] == "10.20.0.20"


def test_multiple_students_use_same_image_but_different_networks(db, lab, users, runtime):
    a = start_ready(db, lab, users["student01"], runtime)
    b = start_ready(db, lab, users["student02"], runtime)
    assert a.network_id != b.network_id
    targets = [s for s in runtime.containers.values() if s.instance_type == "TARGET"]
    assert len(targets) == 2 and targets[0].image == targets[1].image


def test_stop_is_idempotent_and_preserves_image_and_scores(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    service = SessionService(db)
    service.submit(session.id, users["student01"], "flag{expected}")
    service.command(session.id, users["student01"], "stop")
    LabOrchestrator(runtime).reconcile(db, session); db.commit()
    assert session.status == "DESTROYED"
    assert not runtime.containers and not runtime.networks
    assert "sha256:target" in runtime.images
    assert not runtime.removed_images
    assert len(list(db.scalars(select(Submission)))) == 1
    assert service.command(session.id, users["student01"], "stop")["status"] == "DESTROYED"


def test_reset_replaces_environment_without_extending_ttl(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    old_ids, old_net, expires = set(runtime.containers), session.network_id, aware(session.expires_at)
    old_generation = session.generation
    SessionService(db).command(session.id, users["student01"], "reset")
    LabOrchestrator(runtime).reconcile(db, session); db.commit()
    assert session.status == "READY"
    assert not old_ids.intersection(runtime.containers)
    assert old_net != session.network_id
    assert expires == aware(session.expires_at)
    assert session.generation > old_generation


@pytest.mark.parametrize("state", ["READY", "CREATING", "STARTING", "RESETTING"])
def test_expired_sessions_are_destroyed_in_all_pending_states(db, lab, users, runtime, state):
    session = start_ready(db, lab, users["student01"], runtime)
    session.status = state
    session.expires_at = utcnow() - timedelta(seconds=1)
    LabOrchestrator(runtime).reconcile(db, session); db.commit()
    assert session.status == "DESTROYED"
    assert not runtime.containers and not runtime.networks


def test_partial_creation_failure_rolls_back_resources(db, lab, users, runtime):
    runtime.fail_on_type = "TARGET"
    session = start_ready(db, lab, users["student01"], runtime)
    assert session.status == "FAILED" and session.error
    assert not runtime.containers and not runtime.networks


def test_parallel_creation_joins_late_target_before_failure_cleanup(db, lab, users, runtime, monkeypatch):
    from threading import Barrier
    from app.orchestrator.models import RuntimeFailure
    both_started = Barrier(2)
    created = []
    original = runtime.create_container

    def create(spec):
        both_started.wait(timeout=3)
        if spec.instance_type == "KALI":
            raise RuntimeFailure("Kali failed while target was being created")
        identifier = original(spec)
        created.append(identifier)
        return identifier

    monkeypatch.setattr(runtime, "create_container", create)
    session = start_ready(db, lab, users["student01"], runtime)
    assert created  # A late-created target must be found by labels and reclaimed.
    assert session.status == "FAILED"
    assert not runtime.containers and not runtime.networks


def test_missing_image_has_actionable_error_and_no_resources(db, lab, users, runtime):
    runtime.images.remove("sha256:target")
    session = start_ready(db, lab, users["student01"], runtime)
    assert session.status == "FAILED"
    assert "镜像" in session.error
    assert not runtime.containers and not runtime.networks


def test_cleanup_failure_stays_pending_until_retry(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    SessionService(db).command(session.id, users["student01"], "stop")
    runtime.fail_cleanup = True
    with pytest.raises(Exception):
        LabOrchestrator(runtime).reconcile(db, session)
    assert session.status == "STOPPING"
    runtime.fail_cleanup = False
    LabOrchestrator(runtime).reconcile(db, session)
    assert session.status == "DESTROYED" and not runtime.containers


def test_activity_failure_does_not_leak_desktop_resources(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    SessionService(db).command(session.id, users["student01"], "stop")
    runtime.fail_activity_stop = True
    LabOrchestrator(runtime).reconcile(db, session)
    assert session.status == "DESTROYED" and not runtime.containers
    assert "操作记录收尾失败" in session.error


def test_every_flag_attempt_is_recorded_and_score_cannot_regress(client, headers, db, users, lab, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    for value, expected in (("wrong", False), ("flag{expected}", True), ("wrong-again", False)):
        response = client.post(f"/api/lab-sessions/{session.id}/submit", headers=headers["student01"], json={"flag": value})
        assert response.status_code == 200
        assert response.json()["data"]["correct"] is expected
    score = client.get("/api/me/scores", headers=headers["student01"]).json()["data"][0]
    assert score["score"] == 100 and score["submissions_count"] == 3 and score["completed_at"]
    assert len(list(db.scalars(select(Submission)))) == 3


def test_expired_session_rejects_submissions_and_desktop_ticket(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    session.expires_at = utcnow() - timedelta(seconds=1); db.commit()
    for action in (lambda: SessionService(db).submit(session.id, users["student01"], "flag{expected}"), lambda: SessionService(db).desktop_ticket(session.id, users["student01"])):
        with pytest.raises(HTTPException) as exc:
            action()
        assert exc.value.status_code == 409


def test_runtime_exit_is_reclaimed(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    runtime.states[next(iter(runtime.states))] = "exited"
    LabOrchestrator(runtime).reconcile(db, session)
    assert session.status == "DESTROYED" and session.error


def test_crash_recovery_removes_labeled_resources_without_instance_rows(db, lab, users, runtime):
    session = start_ready(db, lab, users["student01"], runtime)
    original = set(runtime.containers)
    for item in list(db.scalars(select(LabInstance))):
        db.delete(item)
    session.status = "STARTING"; db.commit()
    LabOrchestrator(runtime).reconcile(db, session)
    assert session.status == "READY" and not original.intersection(runtime.containers)
