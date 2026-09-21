from fastapi import APIRouter
from app.core.security import CurrentUser, DB
from app.core.limits import limit
from app.models import LabSession
from app.schemas.inputs import FlagInput
from app.services.sessions import SessionService
from app.services.scores import ScoreService

router = APIRouter(tags=["Sessions"])


@router.post("/labs/{identifier}/sessions", status_code=202)
def start(identifier: str, db: DB, user: CurrentUser):
    limit(f"start:{user.id}", 10, 60)
    return {"data": SessionService(db).start(identifier, user)}


@router.get("/me/sessions")
def sessions(db: DB, user: CurrentUser):
    service = SessionService(db)
    return {"data": [service.describe(s) for s in service.repo.list(LabSession, LabSession.user_id == user.id, order=LabSession.started_at.desc())]}


@router.get("/lab-sessions/{identifier}")
def session(identifier: str, db: DB, user: CurrentUser):
    service = SessionService(db)
    return {"data": service.describe(service.owned(identifier, user))}


@router.post("/lab-sessions/{identifier}/reset", status_code=202)
def reset(identifier: str, db: DB, user: CurrentUser):
    limit(f"reset:{user.id}", 6, 60)
    return {"data": SessionService(db).command(identifier, user, "reset")}


@router.post("/lab-sessions/{identifier}/stop", status_code=202)
def stop(identifier: str, db: DB, user: CurrentUser):
    return {"data": SessionService(db).command(identifier, user, "stop")}


@router.post("/lab-sessions/{identifier}/desktop-ticket")
def desktop_ticket(identifier: str, db: DB, user: CurrentUser):
    limit(f"desktop-ticket:{user.id}", 20, 60)
    return {"data": SessionService(db).desktop_ticket(identifier, user)}


@router.post("/lab-sessions/{identifier}/submit")
def submit(identifier: str, data: FlagInput, db: DB, user: CurrentUser):
    limit(f"submit:{user.id}", 30, 60)
    return {"data": SessionService(db).submit(identifier, user, data.flag)}


@router.get("/me/scores")
def scores(db: DB, user: CurrentUser):
    return {"data": ScoreService(db).scores(user.id)}
