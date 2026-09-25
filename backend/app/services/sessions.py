import hmac
import uuid
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import aware, utcnow
from app.core.security import token
from app.core.session_control import stop_requested
from app.models import ACTIVE_STATUSES, LabInstance, LabSession, LabTemplate, SessionStopRequest, Submission, TargetImage, User
from app.repositories.catalog import Repository, public


class SessionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = Repository(db)

    def owned(self, identifier: str, user: User, lock: bool = False) -> LabSession:
        statement = select(LabSession).where(LabSession.id == identifier)
        if lock:
            statement = statement.with_for_update(nowait=True)
        session = self.db.scalar(statement)
        if not session or (session.user_id != user.id and user.role != "ADMIN"):
            raise HTTPException(404, "实验实例不存在")
        return session

    def describe(self, session: LabSession) -> dict:
        instances = self.repo.list(LabInstance, LabInstance.session_id == session.id)
        target = next((i for i in instances if i.instance_type == "TARGET" and i.status != "removed"), None)
        lab = self.repo.get(LabTemplate, session.lab_template_id)
        data = {**public(session), "lab_name": lab.name, "lab": public(lab), "instances": [public(i) for i in instances], "target_ip": target.ip_address if target else None}
        if session.status in ACTIVE_STATUSES and stop_requested(self.db, session.id):
            data["status"] = "STOPPING"
        return data

    def start(self, lab_id: str, user: User) -> dict:
        if user.role != "STUDENT":
            raise HTTPException(403, "请使用学生账号启动实验")
        # Lock the template against edits and serialize admission per student.
        lab = self.db.scalar(select(LabTemplate).where(LabTemplate.id == lab_id).with_for_update())
        if not lab or lab.status != "PUBLISHED":
            raise HTTPException(404, "实验未发布")
        self.db.scalar(select(User).where(User.id == user.id).with_for_update())
        existing = self.db.scalar(select(LabSession).where(LabSession.user_id == user.id, LabSession.status.in_(ACTIVE_STATUSES)))
        if existing:
            if existing.lab_template_id == lab_id:
                return self.describe(existing)
            raise HTTPException(409, "请先结束当前运行的实验")
        image = self.repo.get(TargetImage, lab.target_image_id)
        if image.status != "READY":
            raise HTTPException(409, "靶机镜像尚未准备好")
        # PostgreSQL transaction-level advisory lock makes the global capacity check atomic.
        if self.db.bind.dialect.name == "postgresql":
            from sqlalchemy import text
            self.db.execute(text("SELECT pg_advisory_xact_lock(738210)"))
        count = self.db.scalar(select(func.count()).select_from(LabSession).where(LabSession.status.in_(ACTIVE_STATUSES)))
        if count >= settings().max_active_sessions:
            raise HTTPException(429, "实验资源已满，请稍后再试")
        session = LabSession(user_id=user.id, lab_template_id=lab.id, expires_at=utcnow() + timedelta(minutes=lab.duration_minutes))
        try:
            self.repo.save(session)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(409, "实验正在启动，请刷新页面") from None
        return self.describe(session)

    def command(self, identifier: str, user: User, action: str) -> dict:
        if action == "stop":
            # Provisioning holds the session row while talking to Docker. Write
            # cancellation independently so this endpoint can always acknowledge it.
            session = self.owned(identifier, user)
            if session.status not in ("DESTROYED", "FAILED") and not stop_requested(self.db, identifier):
                self.db.add(SessionStopRequest(session_id=identifier))
                try:
                    self.db.commit()
                except IntegrityError:
                    self.db.rollback()
                    if not stop_requested(self.db, identifier):
                        raise
            return self.describe(session)
        session = self.owned(identifier, user, lock=True)
        if action == "reset":
            if session.status != "READY" or aware(session.expires_at) <= utcnow() or stop_requested(self.db, identifier):
                raise HTTPException(409, "仅可重置尚未过期的就绪实验")
            session.status = "RESETTING"
        else:
            if session.status in ("DESTROYED", "FAILED"):
                return self.describe(session)
            session.status = "STOPPING"
            session.finished_at = session.finished_at or utcnow()
        session.generation += 1  # Immediately revokes desktop tickets and open connections.
        self.repo.save(session)
        return self.describe(session)

    def desktop_ticket(self, identifier: str, user: User) -> dict:
        session = self.owned(identifier, user)
        if session.status != "READY" or aware(session.expires_at) <= utcnow() or stop_requested(self.db, identifier):
            raise HTTPException(409, "桌面尚未就绪或实验已到期")
        value = token(user.id, "desktop", minutes=2, sid=session.id, gen=session.generation, jti=str(uuid.uuid4()))
        return {"ticket": value, "desktop_url": f"/desktop/{session.id}", "expires_in": 120}

    def submit(self, identifier: str, user: User, flag: str) -> dict:
        session = self.owned(identifier, user, lock=True)
        if session.user_id != user.id:
            raise HTTPException(403, "只能提交自己的实验")
        if session.status != "READY" or aware(session.expires_at) <= utcnow() or stop_requested(self.db, identifier):
            raise HTTPException(409, "实验未就绪或已结束")
        lab = self.repo.get(LabTemplate, session.lab_template_id)
        correct = hmac.compare_digest(flag.encode(), lab.flag.encode())
        submission = Submission(user_id=user.id, session_id=session.id, lab_template_id=lab.id, submitted_flag=flag, correct=correct, score=100 if correct else 0)
        self.repo.save(submission)
        return {"correct": correct, "score": submission.score, "submission_id": submission.id}
