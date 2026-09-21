import io
import json
import tarfile
from pathlib import Path
import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile
from app.core.config import settings
from app.models import TargetImage
from app.orchestrator.image_manager import ImageManager
from app.orchestrator.models import ContainerSpec
from app.services.images import ImageService


def docker_tar(manifest=None) -> bytes:
    stream = io.BytesIO()
    content = json.dumps(manifest if manifest is not None else [{"Config": "config.json", "RepoTags": ["teaching/target:v1"], "Layers": []}]).encode()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo("manifest.json"); member.size = len(content)
        archive.addfile(member, io.BytesIO(content))
    return stream.getvalue()


def upload_file(data=None, name="demo.tar", mime="application/x-tar"):
    return UploadFile(file=io.BytesIO(data if data is not None else docker_tar()), filename=name, headers=Headers({"content-type": mime}))


def test_upload_is_temporary_uuid_then_load_preserves_metadata(db, runtime):
    data = ImageService(db).upload(upload_file(name="../../outside.tar"), "教学靶机")
    image = db.get(TargetImage, data["id"])
    path = Path(image.upload_path)
    assert path.parent == Path(settings().upload_dir)
    assert path.name != "outside.tar" and path.name.endswith(".tar")
    assert image.original_filename == "outside.tar"
    assert image.status == "IMPORTING" and "upload_path" not in data
    ImageManager(runtime).load(db, image)
    assert image.status == "READY"
    assert image.repository == "teaching/target" and image.tag == "v1"
    assert image.image_id == "sha256:uploaded" and image.size_bytes == 123456
    assert image.repo_digest is None  # docker-save images need not have registry digests.
    assert not path.exists() and image.upload_path is None


@pytest.mark.parametrize("filename,mime", [("demo.zip", "application/x-tar"), ("demo.tar", "text/plain")])
def test_upload_checks_extension_and_mime(db, filename, mime):
    with pytest.raises(HTTPException) as exc:
        ImageService(db).upload(upload_file(name=filename, mime=mime), "Target")
    assert exc.value.status_code == 415


def test_non_docker_tar_rejected_and_temp_cleaned(db):
    with pytest.raises(HTTPException) as exc:
        ImageService(db).upload(upload_file(data=b"invalid archive"), "Target")
    assert exc.value.status_code == 422
    assert not list(Path(settings().upload_dir).glob("*.tar"))


def test_oversized_upload_cleaned(db, monkeypatch):
    monkeypatch.setattr(settings(), "max_upload_mb", 1)
    with pytest.raises(HTTPException) as exc:
        ImageService(db).upload(upload_file(data=b"x" * (1024 * 1024 + 1)), "Target")
    assert exc.value.status_code == 413
    assert not list(Path(settings().upload_dir).glob("*.tar"))


def test_failed_load_records_error_and_cleans_temp(db, runtime, monkeypatch):
    data = ImageService(db).upload(upload_file(), "Target")
    image = db.get(TargetImage, data["id"])
    path = Path(image.upload_path)
    def fail(path):
        raise RuntimeError("daemon private details /secret/path")
    monkeypatch.setattr(runtime, "load_image", fail)
    ImageManager(runtime).load(db, image)
    assert image.status == "ERROR" and image.error_message
    assert "private details" not in image.error_message
    assert not path.exists() and image.upload_path is None


def test_multiple_images_do_not_load(db, runtime):
    data = ImageService(db).upload(upload_file(data=docker_tar([{}, {}])), "Target")
    image = db.get(TargetImage, data["id"])
    ImageManager(runtime).load(db, image)
    assert image.status == "ERROR" and not runtime.loaded


def test_duplicate_image_id_reuses_existing_asset(db, runtime):
    manager = ImageManager(runtime)
    first = db.get(TargetImage, ImageService(db).upload(upload_file(), "First")["id"])
    manager.load(db, first)
    second = db.get(TargetImage, ImageService(db).upload(upload_file(), "Duplicate")["id"])
    manager.load(db, second)
    assert first.status == "READY" and second.status == "ERROR"
    assert second.image_id is None and first.image_id in runtime.images


def test_image_referenced_by_template_cannot_be_deleted(db, lab, runtime):
    with pytest.raises(HTTPException) as exc:
        ImageManager(runtime).delete(db, lab.target_image_id)
    assert exc.value.status_code == 409 and exc.value.detail["code"] == "IMAGE_IN_USE"
    assert not runtime.removed_images


def test_image_referenced_by_container_cannot_be_deleted(db, runtime):
    image = TargetImage(display_name="In-use image", image_id="sha256:target", status="READY")
    db.add(image); db.commit()
    runtime.create_container(ContainerSpec("target", "sha256:target", "network", "TARGET", "session", 1, 128))
    with pytest.raises(HTTPException) as exc:
        ImageManager(runtime).delete(db, image.id)
    assert exc.value.detail["code"] == "IMAGE_IN_USE"
    assert db.get(TargetImage, image.id)


def test_unreferenced_image_is_removed_from_engine_then_database(db, runtime):
    image = TargetImage(display_name="Unused", image_id="sha256:target", status="READY")
    db.add(image); db.commit()
    identifier = image.id
    assert ImageManager(runtime).delete(db, identifier) == {"deleted": True}
    assert "sha256:target" not in runtime.images
    assert db.get(TargetImage, identifier) is None


def test_only_admin_can_upload(client, headers):
    result = client.post("/api/admin/images/upload", headers=headers["student01"], data={"display_name": "No"}, files={"file": ("target.tar", docker_tar(), "application/x-tar")})
    assert result.status_code == 403
