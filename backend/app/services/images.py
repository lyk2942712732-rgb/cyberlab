from pathlib import Path
import tarfile
import uuid
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import TargetImage
from app.orchestrator.client import OrchestratorClient
from app.repositories.catalog import Repository, public

MIME_TYPES = {"application/x-tar", "application/tar", "application/octet-stream", "application/x-gtar"}


class ImageService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = Repository(db)

    def upload(self, file: UploadFile, display_name: str) -> dict:
        if not file.filename or not file.filename.lower().endswith(".tar") or file.content_type not in MIME_TYPES:
            raise HTTPException(415, "仅支持 Docker save 生成的 .tar 镜像文件")
        if not 1 <= len(display_name.strip()) <= 200:
            raise HTTPException(422, "镜像名称长度应为 1–200 字符")
        root = Path(settings().upload_dir)
        root.mkdir(parents=True, exist_ok=True)
        destination = root / f"{uuid.uuid4()}.tar"
        size = 0
        try:
            with destination.open("wb") as output:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings().max_upload_mb * 1024 * 1024:
                        raise HTTPException(413, "镜像超过上传大小限制")
                    output.write(chunk)
            # Inspect structure without extracting untrusted tar members onto the host.
            try:
                with tarfile.open(destination, "r:") as archive:
                    manifest = archive.getmember("manifest.json")
                    if not manifest.isfile() or manifest.size > 1024 * 1024:
                        raise ValueError("invalid manifest")
            except (tarfile.TarError, KeyError, ValueError):
                raise HTTPException(422, "不是有效的 Docker save tar 包（缺少 manifest.json）") from None
            original_filename = file.filename.replace('\\', '/').rsplit('/', 1)[-1][:255]
            image = TargetImage(display_name=display_name.strip(), original_filename=original_filename, status="IMPORTING", upload_path=str(destination), size_bytes=size)
            self.repo.save(image)
            return public(image)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            file.file.close()

    def delete(self, identifier: str) -> dict:
        return OrchestratorClient().delete_image(identifier)
