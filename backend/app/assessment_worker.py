"""One lightweight polling process; no new task broker or agent framework required."""
import logging
import time
from datetime import timedelta
import httpx
from sqlalchemy import select
from app.assessment import collect_evidence, evaluate, PROMPT_VERSION
from app.core.config import settings
from app.core.db import SessionLocal, utcnow
from app.models import LabAssessment, LabSession
from app.services.assessments import TERMINAL

log = logging.getLogger(__name__)


def claim(db):
    now = utcnow()
    # Recover a process killed mid-call; lock before changing its durable job.
    stale = db.scalars(select(LabAssessment).where(LabAssessment.status == "RUNNING",
        LabAssessment.updated_at < now - timedelta(minutes=10)).with_for_update(skip_locked=True))
    for job in stale:
        job.status = "QUEUED" if job.attempts < 3 else "FAILED"
        job.error = "评估进程中断，可重试"
        job.available_at = now
    db.flush()
    job = db.scalar(select(LabAssessment).join(LabSession).where(
        LabAssessment.status == "QUEUED", LabAssessment.available_at <= now,
        LabSession.status.in_(TERMINAL)).order_by(LabAssessment.created_at)
        .with_for_update(skip_locked=True, of=LabAssessment).limit(1))
    if job:
        job.status, job.error = "RUNNING", None
        job.attempts += 1
        job.updated_at = now
        job.model = settings().deepseek_model
        job.prompt_version = PROMPT_VERSION
    return job.session_id if job else None


def process(identifier):
    try:
        with SessionLocal() as db:
            job = db.get(LabAssessment, identifier)
            evidence = job.evidence
            reference = job.reference
            if evidence is None:
                evidence = collect_evidence(db, identifier)
                job.evidence = evidence
                db.commit()
        report = evaluate(reference, evidence)
        with SessionLocal.begin() as db:
            job = db.get(LabAssessment, identifier)
            job.report, job.status, job.error = report, "COMPLETED", None
            job.completed_at = utcnow()
        log.info("Assessment completed session=%s", identifier)
    except Exception as exc:
        # Never print upstream bodies, headers, prompts, student inputs, or credentials.
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            reason = {401: "模型密钥无效，请联系管理员", 402: "模型账户余额不足，请联系管理员",
                      429: "模型服务繁忙，稍后重试"}.get(status, "模型服务暂时不可用")
        elif isinstance(exc, httpx.TimeoutException):
            reason = "模型响应超时，稍后重试"
        elif not settings().deepseek_api_key:
            reason = "模型密钥尚未配置，请联系管理员"
        else:
            reason = "记录读取或评估生成失败，可重试"
        with SessionLocal.begin() as db:
            job = db.get(LabAssessment, identifier)
            job.error = reason
            job.status = "QUEUED" if job.attempts < 3 else "FAILED"
            job.available_at = utcnow() + timedelta(seconds=15 * job.attempts)
        log.warning("Assessment attempt failed session=%s type=%s", identifier, type(exc).__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    while True:
        try:
            identifier = None
            if settings().assessment_enabled:
                with SessionLocal.begin() as db:
                    identifier = claim(db)
            if identifier:
                process(identifier)
            else:
                time.sleep(3)
        except Exception as exc:
            log.warning("Assessment queue unavailable type=%s", type(exc).__name__)
            time.sleep(5)


if __name__ == "__main__":
    main()
