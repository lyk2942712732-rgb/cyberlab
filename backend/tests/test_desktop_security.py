from contextlib import contextmanager
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect
from app.core.security import decode
from app.core.desktop import validate_desktop, validate_claims
from app.models import LabInstance, LabSession
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


def test_desktop_verify_consumes_ticket_and_rejects_reuse(client, db, lab, users, runtime, monkeypatch):
    @contextmanager
    def factory():
        yield db
    monkeypatch.setattr("app.core.desktop.SessionLocal", factory)
    monkeypatch.setattr("app.api.desktop.SessionLocal", factory)
    consumed = {"set": set()}
    class _FakeRedis:
        def set(self, key, value, nx=None, ex=None):
            if key in consumed["set"]:
                return None
            consumed["set"].add(key)
            return True
    monkeypatch.setattr("app.api.desktop.cache", lambda: _FakeRedis())

    service = SessionService(db)
    session = db.get(LabSession, service.start(lab.id, users["student01"])["id"])
    from app.orchestrator.lab_orchestrator import LabOrchestrator
    LabOrchestrator(runtime).reconcile(db, session); db.commit()
    ticket = service.desktop_ticket(session.id, users["student01"])["ticket"]
    instance = db.scalar(select(LabInstance).where(LabInstance.session_id == session.id, LabInstance.instance_type == "KALI"))

    response = client.get(f"/api/desktop/verify?identifier={session.id}", headers={"X-Desktop-Ticket": ticket})
    assert response.status_code == 204
    assert response.headers["X-Desktop-Container"] == instance.container_name

    replay = client.get(f"/api/desktop/verify?identifier={session.id}", headers={"X-Desktop-Ticket": ticket})
    assert replay.status_code == 401

    forged = client.get(f"/api/desktop/verify?identifier={session.id}", headers={"X-Desktop-Ticket": "forged-token"})
    assert forged.status_code == 401

    cross = client.get("/api/desktop/verify?identifier=not-a-session", headers={"X-Desktop-Ticket": ticket})
    assert cross.status_code == 403
