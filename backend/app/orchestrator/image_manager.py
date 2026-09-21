import json
import logging
import tarfile
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import LabTemplate, TargetImage
from app.orchestrator.base import RuntimeProvider
from app.orchestrator.models import ImageInUse, RuntimeFailure

log = logging.getLogger(__name__)


class ImageManager:
    def __init__(self, runtime: RuntimeProvider):
        self.runtime = runtime

    def load(self, db: Session, image: TargetImage) -> None:
        source = Path(image.upload_path or "")
        try:
            if not image.upload_path or source.parent.resolve() != Path(settings().upload_dir).resolve():
                raise RuntimeFailure("镜像上传文件丢失，请重新上传")
            # This is Docker's native manifest.json inside docker-save archives,
            # not a CyberLab challenge manifest. No extraction, rewriting or build.
            with tarfile.open(source, "r:") as original:
                manifest_member = original.getmember("manifest.json")
                if not manifest_member.isfile() or manifest_member.size > 1024 * 1024:
                    raise RuntimeFailure("镜像清单不合法")
                manifest_file = original.extractfile(manifest_member)
                manifest = json.load(manifest_file)
                if not isinstance(manifest, list) or len(manifest) != 1:
                    raise RuntimeFailure("每次上传仅支持包含一个镜像的 tar 包")
                if settings().kali_image in (manifest[0].get("RepoTags") or []):
                    raise RuntimeFailure("靶机镜像标签不能与系统 Kali 镜像相同")
            result = self.runtime.load_image(str(source))
            if db.scalar(select(TargetImage.id).where(TargetImage.image_id == result.id, TargetImage.id != image.id)):
                raise RuntimeFailure("此 Image ID 已在镜像库中，请直接使用已有镜像")
            image.image_id, image.repository, image.tag = result.id, result.repository, result.tag
            image.size_bytes, image.repo_digest = result.size, result.repo_digest
            image.status, image.error_message = "READY", None
        except Exception as exc:
            log.exception("Image import failed image=%s", image.id)
            image.status = "ERROR"
            image.error_message = str(exc) if isinstance(exc, RuntimeFailure) else "镜像导入失败，请检查 Docker 服务和 docker save tar 格式"
        # Commit metadata before deleting its recovery input. A crash between these
        # operations leaves a terminal record with upload_path, cleaned by recovery.
        db.commit()
        self.cleanup_upload(db, image)

    def cleanup_upload(self, db: Session, image: TargetImage) -> None:
        if not image.upload_path:
            return
        source = Path(image.upload_path)
        if source.parent.resolve() != Path(settings().upload_dir).resolve():
            return
        try:
            source.unlink(missing_ok=True)
            image.upload_path = None
            db.commit()
        except OSError:
            log.warning("Temporary tar cleanup will retry image=%s", image.id)

    def delete(self, db: Session, identifier: str) -> dict:
        image = db.scalar(select(TargetImage).where(TargetImage.id == identifier).with_for_update(nowait=True))
        if not image:
            raise HTTPException(404, "镜像不存在")
        if image.status == "IMPORTING":
            raise HTTPException(409, {"code": "IMAGE_IMPORTING", "message": "镜像导入中，请稍后操作"})
        if db.scalar(select(LabTemplate.id).where(LabTemplate.target_image_id == identifier).limit(1)):
            raise HTTPException(409, {"code": "IMAGE_IN_USE", "message": "镜像仍被实验模板引用，请先解除关联"})
        if image.image_id:
            try:
                self.runtime.remove_image(image.image_id)
            except ImageInUse as exc:
                raise HTTPException(409, {"code": "IMAGE_IN_USE", "message": str(exc)}) from None
        db.delete(image)
        db.commit()
        return {"deleted": True}
