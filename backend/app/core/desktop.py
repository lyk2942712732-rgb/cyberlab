"""Validation shared by the public gateway and the private orchestrator."""
from fastapi import HTTPException
from sqlalchemy import select
from app.core.db import SessionLocal, aware, utcnow
from app.core.security import decode
from app.models import LabInstance, LabSession, User


def validate_desktop(identifier: str, ticket: str) -> tuple[dict, str]:
    claims = decode(ticket, "desktop")
    return validate_claims(identifier, claims)


def validate_claims(identifier: str, claims: dict) -> tuple[dict, str]:
    with SessionLocal() as db:
        session = db.get(LabSession, identifier)
        user = db.get(User, claims.get("sub"))
        if not session or not user or claims.get("sid") != identifier or (user.id != session.user_id and user.role != "ADMIN"):
            raise HTTPException(403, "无权访问此桌面")
        if session.status != "READY" or aware(session.expires_at) <= utcnow() or claims.get("gen") != session.generation:
            raise HTTPException(409, "实验已结束或正在重置")
        instance = db.scalar(select(LabInstance).where(LabInstance.session_id == identifier, LabInstance.instance_type == "KALI", LabInstance.status != "removed"))
        if not instance:
            raise HTTPException(409, "桌面实例不可用")
        return claims, instance.runtime_id
