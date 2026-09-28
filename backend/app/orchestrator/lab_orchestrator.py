import logging
import time
import uuid
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import aware, utcnow
from app.core.session_control import stop_requested
from app.models import LabInstance, LabSession, LabTemplate, TargetImage
from app.orchestrator.base import RuntimeProvider
from app.orchestrator.models import ContainerSpec, ProvisionCancelled, RuntimeFailure
from app.orchestrator.network_manager import NetworkManager

log = logging.getLogger(__name__)


class LabOrchestrator:
    def __init__(self, runtime: RuntimeProvider):
        self.runtime = runtime
        self.networks = NetworkManager(runtime)

    def cleanup(self, db: Session, session: LabSession) -> None:
        containers, _ = self.runtime.session_resources(session.id)
        # A claimed warm desktop keeps its parking slot label, so label lookup
        # cannot see it; the DB rows own the authoritative container list.
        for instance in db.scalars(select(LabInstance).where(LabInstance.session_id == session.id)):
            if instance.container_name and instance.runtime_id not in containers:
                containers.append(instance.runtime_id)
        for container in containers:
            try:
                self.runtime.disconnect_desktop(container)
                self.runtime.stop_activity(container)
            except Exception as exc:
                log.exception("Activity finalization failed session=%s container=%s: %s", session.id, container, exc)
                # Preserve a visible failure but always reclaim the desktop resources.
                session.error = "操作记录收尾失败，记录可能不完整"
        self.networks.cleanup(session.id)
        for instance in db.scalars(select(LabInstance).where(LabInstance.session_id == session.id)):
            instance.status = "removed"
        session.network_id = None

    def stop(self, db: Session, session: LabSession) -> None:
        session.status = "STOPPING"
        session.generation += 1
        session.finished_at = session.finished_at or utcnow()
        self.cleanup(db, session)
        session.status = "FINISHED"
        db.flush()
        session.status = "DESTROYED"
        log.info("Session destroyed session=%s", session.id)

    def provision(self, db: Session, session: LabSession) -> None:
        def cancelled():
            return aware(session.expires_at) <= utcnow() or stop_requested(db, session.id)

        try:
            # Retry/reset always first removes previous generation, including unlinked
            # resources discovered by labels after a controller crash.
            self.cleanup(db, session)
            db.execute(delete(LabInstance).where(LabInstance.session_id == session.id))
            if cancelled():
                self.stop(db, session)
                return
            lab = db.get(LabTemplate, session.lab_template_id)
            image = db.get(TargetImage, lab.target_image_id)
            if image.status != "READY" or not self.runtime.image_exists(image.image_id):
                raise RuntimeFailure("靶机镜像不存在或尚未导入成功")
            if not self.runtime.image_exists(settings().kali_image):
                raise RuntimeFailure("Kali 镜像不存在，请先构建系统 Kali 镜像")
            session.network_id = self.networks.create(session.id)
            session.status = "STARTING"
            kali_id = self._place_kali(db, session)
            target_spec = ContainerSpec(f"target-{uuid.uuid4()}", image.image_id, session.network_id, "TARGET", session.id, lab.cpu_limit, lab.memory_limit, {"LAB_FLAG": lab.flag})
            if cancelled():
                raise ProvisionCancelled("实验启动已取消")
            target_id = self.runtime.create_container(target_spec)
            db.add(LabInstance(session_id=session.id, instance_type="TARGET", runtime_id=target_id, container_name=target_spec.name, image=target_spec.image))
            self.runtime.start_container(target_id)
            identifiers = [kali_id, target_id]
            db.flush()
            deadline = time.monotonic() + settings().health_timeout
            while time.monotonic() < deadline:
                if cancelled():
                    self.stop(db, session)
                    return
                states = [self.runtime.inspect_container(identifier) for identifier in identifiers]
                if all(state.healthy for state in states) and self.runtime.probe_target(identifiers[0], states[1].ip_address, lab.target_port):
                    for instance in db.scalars(select(LabInstance).where(LabInstance.session_id == session.id)):
                        info = next(s for s in states if s.id == instance.runtime_id)
                        instance.status, instance.ip_address = info.status, info.ip_address
                    session.status, session.error = "READY", None
                    self.runtime.start_activity(identifiers[0], session.id, session.generation, cancelled=cancelled)
                    if cancelled():
                        raise ProvisionCancelled("实验启动已取消")
                    log.info("Session ready session=%s", session.id)
                    return
                if any(s.status in ("exited", "dead") for s in states):
                    raise RuntimeFailure("实验容器启动后意外退出")
                time.sleep(1)
            raise RuntimeFailure("实验健康检查超时，请重试或联系管理员")
        except ProvisionCancelled:
            self.stop(db, session)
        except Exception as exc:
            log.exception("Session provisioning failed session=%s", session.id)
            session.error = str(exc) if isinstance(exc, RuntimeFailure) else "实验环境创建失败，请联系管理员检查运行服务"
            session.finished_at = utcnow()
            try:
                self.cleanup(db, session)
                session.status = "FAILED"
            except Exception:
                # Do not report a terminal state until leaked resources have been removed.
                log.exception("Cleanup scheduled for retry session=%s", session.id)
                session.status = "STOPPING"

    def _place_kali(self, db: Session, session: LabSession) -> str:
        # A pre-started desktop skips the ~90 s cold boot; claiming is a DB
        # unique-constraint race, so concurrent workers cannot double-book it.
        current = self.runtime.image_id(settings().kali_image)
        for container_id, slot in self.runtime.parked_containers(current):
            try:
                with db.begin_nested():
                    db.add(LabInstance(session_id=session.id, instance_type="KALI", runtime_id=container_id,
                                      container_name=f"kali-warm-{slot}", image=settings().kali_image))
                    db.flush()
            except Exception:
                log.info("Warm desktop %s was claimed by another session", container_id)
                continue
            try:
                self.runtime.claim_container(container_id, session.network_id)
                log.info("Claimed warm desktop session=%s container=%s", session.id, container_id)
                return container_id
            except Exception as exc:
                log.warning("Warm desktop %s unusable during claim: %s", container_id, exc)
                db.rollback()
                try:
                    self.runtime.delete_container(container_id)
                except Exception:
                    log.exception("Failed to discard broken warm desktop %s", container_id)
        spec = ContainerSpec(f"kali-{uuid.uuid4()}", settings().kali_image, session.network_id, "KALI", session.id, settings().kali_cpu, settings().kali_memory_mb)
        runtime_id = self.runtime.create_container(spec)
        db.add(LabInstance(session_id=session.id, instance_type="KALI", runtime_id=runtime_id, container_name=spec.name, image=spec.image))
        self.runtime.start_container(runtime_id)
        return runtime_id

    def reconcile(self, db: Session, session: LabSession) -> None:
        if aware(session.expires_at) <= utcnow() or session.status in ("STOPPING", "FINISHED") or stop_requested(db, session.id):
            self.stop(db, session)
        elif session.status in ("CREATING", "STARTING", "RESETTING"):
            session.generation += 1
            self.provision(db, session)
        elif session.status == "READY":
            instances = list(db.scalars(select(LabInstance).where(LabInstance.session_id == session.id)))
            try:
                if len(instances) != 2:
                    raise RuntimeFailure("实验实例数据不完整")
                unhealthy = []
                for instance in instances:
                    state = self.runtime.inspect_container(instance.runtime_id)
                    instance.status = state.status
                    # Docker healthchecks can briefly report `starting` or
                    # `unhealthy` while the process is still running. Keep the
                    # session usable and let the next reconciliation observe it
                    # again; only a stopped container is terminal.
                    if state.status in ("exited", "dead"):
                        raise RuntimeFailure("实验容器已退出，资源已安排回收")
                    if not state.healthy:
                        unhealthy.append(instance.container_name)
                if unhealthy:
                    log.warning("Container healthcheck pending session=%s containers=%s", session.id, unhealthy)
                    return
            except Exception:
                session.error = "实验容器异常退出，资源已安排回收"
                self.stop(db, session)
