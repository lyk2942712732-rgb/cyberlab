from datetime import timedelta
from typing import Annotated
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import get_db, utcnow
from app.models import User

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]


def token(subject: str, kind: str = "access", minutes: int | None = None, **claims) -> str:
    return jwt.encode({"sub": subject, "kind": kind, "exp": utcnow() + timedelta(minutes=minutes or settings().token_minutes), **claims}, settings().secret_key, algorithm="HS256")


def decode(value: str, kind: str = "access") -> dict:
    try:
        claims = jwt.decode(value, settings().secret_key, algorithms=["HS256"], options={"require": ["sub", "exp", "kind"]})
        if claims["kind"] != kind:
            raise ValueError("wrong token type")
        return claims
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "登录凭证无效或已过期") from None


def current_user(db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
    if not credentials:
        raise HTTPException(401, "请先登录")
    user = db.get(User, decode(credentials.credentials)["sub"])
    if not user:
        raise HTTPException(401, "用户不存在")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def admin(user: CurrentUser) -> User:
    if user.role != "ADMIN":
        raise HTTPException(403, "需要教学管理端权限")
    return user


AdminUser = Annotated[User, Depends(admin)]
