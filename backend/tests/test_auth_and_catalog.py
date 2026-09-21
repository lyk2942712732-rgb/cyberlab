from app.models import Chapter, Course, LearningProgress, Lesson
from sqlalchemy import select


def test_login_me_and_wrong_password(client, users):
    result = client.post("/api/auth/login", json={"username": "student01", "password": "test-password-123"})
    assert result.status_code == 200
    data = result.json()["data"]
    assert data["user"]["role"] == "STUDENT"
    assert "password_hash" not in data["user"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.json()["data"]["username"] == "student01"
    assert client.post("/api/auth/login", json={"username": "student01", "password": "wrong-password"}).status_code == 401


def test_registration_cannot_choose_role(client):
    payload = {"username": "newstudent", "password": "new-password-123", "student_number": "000123"}
    assert client.post("/api/auth/register", json={**payload, "role": "ADMIN"}).status_code == 422
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["data"]["role"] == "STUDENT"
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_student_cannot_call_admin(client, headers):
    for path in ("dashboard", "images", "students", "scores", "lab-sessions"):
        assert client.get(f"/api/admin/{path}", headers=headers["student01"]).status_code == 403
    assert client.post("/api/admin/courses", headers=headers["student01"], json={"name": "Forbidden"}).status_code == 403


def test_flag_never_leaks_via_public_lab_routes(client, headers, lab):
    for actor in ("student01", "admin"):
        for path in ("/api/labs", f"/api/labs/{lab.id}"):
            response = client.get(path, headers=headers[actor])
            assert response.status_code == 200
            assert "flag{expected}" not in response.text
            assert '"flag"' not in response.text
    assert client.get(f"/api/admin/labs/{lab.id}", headers=headers["admin"]).json()["data"]["flag"] == "flag{expected}"


def test_published_hierarchy_and_progress_idempotency(client, headers, db, users):
    course = Course(name="Test", status="PUBLISHED")
    db.add(course); db.flush()
    chapter = Chapter(course_id=course.id, title="Chapter")
    db.add(chapter); db.flush()
    lesson = Lesson(chapter_id=chapter.id, title="Lesson", status="PUBLISHED", content="# Safe Markdown")
    draft = Lesson(chapter_id=chapter.id, title="Hidden", status="DRAFT")
    db.add_all([lesson, draft]); db.commit()
    data = client.get(f"/api/courses/{course.id}", headers=headers["student01"]).json()["data"]
    assert len(data["chapters"][0]["lessons"]) == 1
    assert client.get(f"/api/lessons/{draft.id}", headers=headers["student01"]).status_code == 404
    for _ in range(2):
        assert client.post(f"/api/lessons/{lesson.id}/complete", headers=headers["student01"]).status_code == 200
    assert len(list(db.scalars(select(LearningProgress)))) == 1
    assert client.get("/api/me/progress", headers=headers["student02"]).json()["data"] == []


def test_lab_requires_explicit_valid_target_port(client, headers, lab):
    payload = client.get(f"/api/admin/labs/{lab.id}", headers=headers["admin"]).json()["data"]
    allowed = {"name", "description", "objective", "steps", "category", "difficulty", "target_image_id", "target_port", "duration_minutes", "cpu_limit", "memory_limit", "flag", "status"}
    payload = {k: v for k, v in payload.items() if k in allowed}
    payload.pop("target_port")
    assert client.post("/api/admin/labs", headers=headers["admin"], json=payload).status_code == 422
    for invalid in (0, 65536):
        assert client.post("/api/admin/labs", headers=headers["admin"], json={**payload, "target_port": invalid}).status_code == 422
