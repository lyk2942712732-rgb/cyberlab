from contextlib import contextmanager
import pytest
from fastapi import HTTPException
from starlette.websockets import WebSocketDisconnect
from app.core.security import decode
from app.core.desktop import validate_desktop, validate_claims
from app.models import LabSession
from app.orchestrator.lab_orchestrator import LabOrchestrator
from app.services.sessions import SessionService


def test_desktop_tickets_are_scoped_to_owner_session_and_generation(db, lab, users, runtime, monkeypatch):
    @contextmanager
    def factory():
        yield db
    monkeypatch.setattr("app.core.desktop.SessionLocal", factory)
    service = SessionService(db)
    session = db.get(LabSession, service.start(lab.id, users["student01"])["id"])
    LabOrchestrator(runtime).reconcile(db, session); db.commit()
    ticket = service.desktop_ticket(session.id, users["student01"])["ticket"]
    claims, container = validate_desktop(session.id, ticket)
    assert container in runtime.containers
    assert claims["sub"] == users["student01"].id and claims["sid"] == session.id
    assert claims["jti"]
    with pytest.raises(HTTPException):
        decode(ticket, "access")
    with pytest.raises(HTTPException):
        validate_claims(session.id, {**claims, "sub": users["student02"].id})
    service.command(session.id, users["student01"], "reset")
    with pytest.raises(HTTPException):
        validate_claims(session.id, claims)


def test_websocket_rejects_foreign_origin(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/lab-sessions/not-a-session/desktop", headers={"origin": "https://attacker.invalid"}):
            pass
