import logging
import time
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, text
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.limits import cache
from app.models import ACTIVE_STATUSES, LabSession, TargetImage
from app.orchestrator.image_manager import ImageManager
from app.orchestrator.lab_orchestrator import LabOrchestrator
from app.orchestrator.models import ContainerSpec

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, orchestrator: LabOrchestrator):
        self.orchestrator = orchestrator
        self.images = ImageManager(orchestrator.runtime)
        self.last_recovery = 0.0
        self.pool = ThreadPoolExecutor(max_workers=settings().max_active_sessions)
        self.pending = {}

    def tick(self) -> None:
        # Per-record transactions plus SKIP LOCKED allow multiple workers and durable
        # recovery. Failed transactions leave the original command pending for retry.
        with SessionLocal() as db:
            ids = list(db.scalars(select(LabSession.id).where(LabSession.status.in_(ACTIVE_STATUSES))))
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
            except Exception:
                log.exception("Session reconcile will retry session=%s", identifier)
        # Each admitted session has a worker slot, so one slow health check cannot
        # postpone cleanup of unrelated sessions. MAX_ACTIVE_SESSIONS bounds threads.
        for identifier, future in list(self.pending.items()):
            if future.done():
                future.result()
                del self.pending[identifier]
        for identifier in ids:
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

    def warm_tick(self) -> None:
        # Parked desktops hold resident CPU/RAM, Refilling therefore waits for
        # an idle host; small deployments keep the pool at 0 or 1.
        target = settings().warm_kali_pool
        try:
            runtime = self.orchestrator.runtime
            if target <= 0:
                for container_id, _slot in runtime.parked_containers(healthy_only=False):
                    try:
                        runtime.delete_container(container_id)
                    except Exception:
                        log.warning("Parked container %s could not be removed", container_id[:12])
                runtime.prune_warm_networks()
                return
            with SessionLocal() as db:
                if db.scalar(select(LabSession.id).where(LabSession.status.in_(ACTIVE_STATUSES)).limit(1)):
                    return
            current = runtime.image_id(settings().kali_image)
            live = runtime.parked_containers(current, healthy_only=False)
            live_ids = {pair[0] for pair in live}
            # Desktops built from a replaced image are discarded first.
            for container_id, _slot in runtime.parked_containers(healthy_only=False):
                if container_id not in live_ids:
                    try:
                        runtime.delete_container(container_id)
                    except Exception:
                        log.warning("Stale parked container %s could not be removed", container_id[:12])
            # Starting desktops already occupy a pool slot; counting only
            # healthy ones would create a new Kali on every tick.
            healthy_ids = {pair[0] for pair in runtime.parked_containers(current)}
            ordered = sorted(live, key=lambda pair: pair[0] not in healthy_ids)
            for container_id, _slot in ordered[target:]:
                try:
                    runtime.delete_container(container_id)
                except Exception:
                    log.warning("Surplus parked container %s could not be removed", container_id[:12])
            for _ in range(max(0, target - len(ordered))):
                self._park_kali()
            runtime.prune_warm_networks()
        except Exception:
            log.exception("Warm pool maintenance failed; will retry")

    def _park_kali(self) -> None:
        slot = uuid.uuid4().hex[:8]
        network = self.orchestrator.runtime.create_network(f"warm-{slot}")
        try:
            spec = ContainerSpec(f"kali-warm-{slot}", settings().kali_image, network, "KALI", f"warm-{slot}",
                                 settings().kali_cpu, settings().kali_memory_mb, parked=True, slot=slot)
            container_id = self.orchestrator.runtime.create_container(spec)
            self.orchestrator.runtime.start_container(container_id)
            log.info("Parked warm desktop slot=%s container=%s", slot, container_id)
        except Exception:
            self.orchestrator.runtime.delete_network(network)
            raise

    def recover_orphans(self) -> None:
        try:
            # Lock each extant session before deciding its resources are orphaned.
            for identifier in self.orchestrator.runtime.managed_session_ids():
                # Warm parking slots use pseudo session ids; their containers
                # are owned by the pool, not by any lab session row.
                if identifier.startswith("warm-"):
                    continue
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
