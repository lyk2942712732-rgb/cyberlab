from concurrent.futures import Future
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.db import utcnow
from app.models import SessionStopRequest
from app.orchestrator import worker as worker_module
from app.orchestrator.lab_orchestrator import LabOrchestrator
from tests.test_sessions import start_ready


class InlinePool:
    def __init__(self, **_):
        pass

    def submit(self, operation, *args):
        future = Future()
        try:
            future.set_result(operation(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future

    def shutdown(self, **_):
        pass


@pytest.mark.parametrize("transition", ["health", "stop", "expiry", "reset"])
def test_ready_checks_are_paced_without_delaying_control(db, lab, users, runtime, monkeypatch, transition):
    session = start_ready(db, lab, users["student01"], runtime)
    initial_generation = session.generation
    clock = [100.0]
    monkeypatch.setattr(worker_module, "SessionLocal", sessionmaker(db.get_bind(), expire_on_commit=False))
    monkeypatch.setattr(worker_module, "ThreadPoolExecutor", InlinePool)
    monkeypatch.setattr(worker_module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(worker_module, "cache", lambda: Mock())
    inspect = Mock(wraps=runtime.inspect_container)
    monkeypatch.setattr(runtime, "inspect_container", inspect)
    worker = worker_module.Worker(LabOrchestrator(runtime))
    worker.last_recovery = clock[0]
    worker.tick()
    assert inspect.call_count == 2
    worker.tick()
    assert inspect.call_count == 2  # No repeated Docker inspection one tick later.

    if transition == "health":
        clock[0] += 6
    elif transition == "stop":
        db.add(SessionStopRequest(session_id=session.id))
    elif transition == "expiry":
        session.expires_at = utcnow() - timedelta(seconds=1)
    else:
        session.status = "RESETTING"
    db.commit()
    worker.tick()
    db.refresh(session)
    if transition == "health":
        assert inspect.call_count == 4
    elif transition == "reset":
        assert session.status == "READY" and session.generation > initial_generation
    else:
        assert session.status == "DESTROYED"
        assert not runtime.containers and not runtime.networks
    worker.close()
