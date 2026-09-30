import logging
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, text
from app.core.config import settings
from app.core.db import SessionLocal, aware, utcnow
from app.core.limits import cache
from app.models import ACTIVE_STATUSES, LabSession, SessionStopRequest, TargetImage
from app.orchestrator.image_manager import ImageManager
from app.orchestrator.lab_orchestrator import LabOrchestrator

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, orchestrator: LabOrchestrator):
        self.orchestrator = orchestrator
        self.images = ImageManager(orchestrator.runtime)
        self.last_recovery = 0.0
        self.pool = ThreadPoolExecutor(max_workers=settings().max_active_sessions)
        self.pending = {}
        self.next_health_check = {}

    def tick(self) -> None:
        # Per-record transactions plus SKIP LOCKED allow multiple workers and durable
        # recovery. Failed transactions leave the original command pending for retry.
        with SessionLocal() as db:
            sessions = list(db.execute(select(LabSession.id, LabSession.status, LabSession.expires_at, SessionStopRequest.session_id)
                .outerjoin(SessionStopRequest, SessionStopRequest.session_id == LabSession.id)
                .where(LabSession.status.in_(ACTIVE_STATUSES))))
        def reconcile_one(identifier: str):
            try:
                with SessionLocal.begin() as db:
                    session = db.scalar(select(LabSession).where(LabSession.id == identifier).with_for_update(skip_locked=True))
                    if session is None or session.status not in ACTIVE_STATUSES:
                        return
                    self.orchestrator.reconcile(db, session)
                    status = session.status
                try:
                    cache().setex(f"session:{identifier}:status", 120, status)
                except Exception:
                    log.warning("Redis state cache unavailable; PostgreSQL remains authoritative")
                return status
            except Exception:
                log.exception("Session reconcile will retry session=%s", identifier)
        # Each admitted session has a worker slot, so one slow health check cannot
        # postpone cleanup of unrelated sessions. MAX_ACTIVE_SESSIONS bounds threads.
        for identifier, future in list(self.pending.items()):
            if future.done():
                status = future.result()
                if status == "READY":
                    self.next_health_check[identifier] = time.monotonic() + 5
                else:
                    self.next_health_check.pop(identifier, None)
                del self.pending[identifier]
        active_ids = {row[0] for row in sessions}
        self.next_health_check = {identifier: deadline for identifier, deadline in self.next_health_check.items() if identifier in active_ids}
        for identifier, status, expires_at, stop_request in sessions:
            # Admission/control still runs every tick. Only steady-state Docker
            # inspection is paced; stop/reset/expiry always bypass this delay.
            if (status == "READY" and stop_request is None and aware(expires_at) > utcnow()
                    and time.monotonic() < self.next_health_check.get(identifier, 0)):
                continue
            if identifier not in self.pending:
                self.pending[identifier] = self.pool.submit(reconcile_one, identifier)
        if time.monotonic() - self.last_recovery >= 60:
            self.recover_orphans()
            self.last_recovery = time.monotonic()

    def close(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)

    def import_tick(self) -> None:
        # Image I/O has its own loop and cannot starve the TTL/session worker.
        try:
            with SessionLocal() as db:
                if db.bind.dialect.name == "postgresql" and not db.scalar(text("SELECT pg_try_advisory_xact_lock(738211)")):
                    return
                image = db.scalar(select(TargetImage).where(TargetImage.status == "IMPORTING").order_by(TargetImage.created_at).with_for_update(skip_locked=True).limit(1))
                if image:
                    self.images.load(db, image)
        except Exception:
            log.exception("Image job will retry")

    def recover_orphans(self) -> None:
        try:
            # Lock each extant session before deciding its resources are orphaned.
            for identifier in self.orchestrator.runtime.managed_session_ids():
                with SessionLocal.begin() as db:
                    existing = db.get(LabSession, identifier)
                    if existing:
                        row = db.scalar(select(LabSession).where(LabSession.id == identifier).with_for_update(skip_locked=True))
                        if row is None or row.status in ACTIVE_STATUSES:
                            continue
                    self.orchestrator.networks.cleanup(identifier)
            # Interrupted uploads that never produced a DB row must not fill the disk.
            root = Path(settings().upload_dir)
            with SessionLocal() as db:
                leftovers = list(db.scalars(select(TargetImage).where(TargetImage.status.in_(("READY", "ERROR")), TargetImage.upload_path.is_not(None))))
                for image in leftovers:
                    self.images.cleanup_upload(db, image)
                referenced = set(db.scalars(select(TargetImage.upload_path).where(TargetImage.upload_path.is_not(None))))
            for path in root.glob("*.tar"):
                if str(path) not in referenced and time.time() - path.stat().st_mtime > 86400:
                    path.unlink(missing_ok=True)
        except Exception:
            log.exception("Orphan reconciliation failed; will retry")
