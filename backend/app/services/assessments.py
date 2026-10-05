"""Small persistent queue: one report per session, owned by that session's student."""
from fastapi import HTTPException
from sqlalchemy import select
from app.assessment import REPORT_VERSION
from app.core.config import settings
from app.core.db import utcnow
from app.models import LabAssessment, LabSession, LabTemplate
from app.services.sessions import SessionService

TERMINAL = ("DESTROYED", "FAILED")


def enqueue(db, session):
    job = db.get(LabAssessment, session.id)
    if job or not settings().assessment_enabled:
        return job
    lab = db.get(LabTemplate, session.lab_template_id)
    job = LabAssessment(session_id=session.id, reference={
        "lab_id": lab.id, "title": lab.name, "objective": lab.objective,
        "writeup": lab.writeup, "updated_at": lab.updated_at.isoformat(),
    })
    db.add(job)
    db.flush()
    return job


def describe(job, session, detailed=False):
    result = {"session_id": session.id, "lab_name": (job.reference.get("title") if job else None),
              "status": job.status if job else "NOT_REQUESTED", "session_status": session.status,
              "enabled": settings().assessment_enabled, "created_at": job.created_at if job else None,
              "completed_at": job.completed_at if job else None, "error": job.error if job else None,
              "model": job.model if job else None}
    if detailed:
        result["report"] = job.report if job else None
        result["evidence"] = job.evidence if job and job.status == "COMPLETED" else None
    return result


class AssessmentService:
    def __init__(self, db):
        self.db = db

    def get(self, identifier, user):
        session = SessionService(self.db).owned(identifier, user)
        return describe(self.db.get(LabAssessment, identifier), session, True)

    def request(self, identifier, user):
        session = SessionService(self.db).owned(identifier, user, lock=True)
        if session.status not in TERMINAL:
            raise HTTPException(409, "实验结束后才能生成复盘")
        if not settings().assessment_enabled:
            raise HTTPException(503, "实验复盘暂未启用")
        job = enqueue(self.db, session)
        outdated = job.status == "COMPLETED" and (job.report or {}).get("schema_version") != REPORT_VERSION
        if job.status == "FAILED" or outdated:
            job.status, job.attempts, job.error = "QUEUED", 0, None
            job.available_at = utcnow()
            if outdated:
                job.completed_at = None
        self.db.commit()
        return describe(job, session, True)

    def history(self, user):
        rows = self.db.execute(select(LabSession, LabAssessment, LabTemplate.name)
            .join(LabTemplate, LabSession.lab_template_id == LabTemplate.id)
            .outerjoin(LabAssessment, LabAssessment.session_id == LabSession.id)
            .where(LabSession.user_id == user.id, LabSession.status.in_(TERMINAL))
            .order_by(LabSession.started_at.desc()).limit(100))
        return [{**describe(job, session), "lab_name": name, "started_at": session.started_at,
                 "finished_at": session.finished_at} for session, job, name in rows]
