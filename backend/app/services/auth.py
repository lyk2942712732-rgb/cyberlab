from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.security import passwords, token
from app.models import User
from app.repositories.catalog import Repository, public
from app.schemas.inputs import Login, Register

_DUMMY_HASH = passwords.hash("dummy-password-for-timing")


def login(db: Session, data: Login) -> dict:
    user = db.scalar(select(User).where(User.username == data.username))
    valid = passwords.verify(data.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "用户名或密码错误")
    return {"access_token": token(user.id), "token_type": "bearer", "user": public(user)}


def register(db: Session, data: Register) -> dict:
    user = User(**data.model_dump(exclude={"password"}), password_hash=passwords.hash(data.password), role="STUDENT")
    try:
        Repository(db).save(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "用户名或学号已存在") from None
    return public(user)
