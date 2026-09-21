import os

# Never connects to Docker, PostgreSQL, Redis or the developer's environment.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-" + "a" * 48
os.environ["ORCHESTRATOR_SECRET"] = "test-controller-" + "b" * 48
os.environ["TESTING"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import Base, get_db  # noqa: E402
from app.core.security import passwords, token  # noqa: E402
from app.main import app  # noqa: E402
from app.models import LabTemplate, TargetImage, User  # noqa: E402
from tests.fake_runtime import FakeRuntime  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(settings(), "upload_dir", str(tmp_path))
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def users(db):
    hashed = passwords.hash("test-password-123")
    result = {}
    for name, role in (("student01", "STUDENT"), ("student02", "STUDENT"), ("admin", "ADMIN")):
        user = User(username=name, password_hash=hashed, role=role, student_number=name if role == "STUDENT" else None)
        db.add(user)
        result[name] = user
    db.commit()
    return result


@pytest.fixture
def lab(db):
    image = TargetImage(display_name="Test Target", image_id="sha256:target", repository="cyberlab/test", tag="v1", status="READY")
    db.add(image)
    db.flush()
    lab = LabTemplate(name="SQL test", target_image_id=image.id, target_port=8000, flag="flag{expected}", status="PUBLISHED", duration_minutes=120, cpu_limit=1, memory_limit=256)
    db.add(lab)
    db.commit()
    return lab


@pytest.fixture
def client(db):
    def override():
        yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def headers(users):
    return {name: {"Authorization": f"Bearer {token(user.id)}"} for name, user in users.items()}


@pytest.fixture
def runtime():
    return FakeRuntime()
