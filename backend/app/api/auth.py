from fastapi import APIRouter, Request
from app.core.security import CurrentUser, DB
from app.schemas.inputs import Login, Register
from app.services import auth
from app.repositories.catalog import public
from app.core.limits import limit

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
def login(data: Login, request: Request, db: DB):
    limit(f"login:{request.headers.get('x-real-ip', request.client.host)}", 30, 60)
    return {"data": auth.login(db, data)}


@router.post("/register", status_code=201)
def register(data: Register, request: Request, db: DB):
    limit(f"register:{request.headers.get('x-real-ip', request.client.host)}", 10, 3600)
    return {"data": auth.register(db, data)}


@router.get("/me")
def me(user: CurrentUser):
    return {"data": public(user)}
