import pytest
from sqlalchemy import select

from app.models import LabTemplate
from app.seed_web_security import CATALOG
from app.writeups import NAMES, reference, fill_missing


BUILTIN_SLUGS = (
    "sqli-basic", "access", "config", "supply", "crypto", "sqli", "design",
    "auth", "integrity", "logging", "exception", "xss", "ssrf",
)
LONG_WRITEUP = "# 教师参考解答\n\n" + "WRITEUP_ONLY_MARKER: 复现、结果与修复。\n" * 1000


@pytest.fixture
def written_lab(db, lab):
    lab.writeup = LONG_WRITEUP
    db.commit()
    return lab


@pytest.mark.parametrize("actor", ["student01", "admin"])
@pytest.mark.parametrize("status", ["PUBLISHED", "DRAFT", "DISABLED"])
def test_writeup_access_follows_publication(client, headers, db, written_lab, actor, status):
    written_lab.status = status
    db.commit()
    response = client.get(f"/api/labs/{written_lab.id}/writeup", headers=headers[actor])
    if actor == "student01" and status != "PUBLISHED":
        assert response.status_code == 404
        assert "WRITEUP_ONLY_MARKER" not in response.text
    else:
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["schema_version"] == 1
        assert data["lab_id"] == written_lab.id
        assert data["title"] == written_lab.name
        assert data["format"] == "markdown"
        assert data["content"] == LONG_WRITEUP
        assert data["updated_at"]


def test_writeup_requires_login(client, written_lab):
    response = client.get(f"/api/labs/{written_lab.id}/writeup")
    assert response.status_code == 401
    assert "WRITEUP_ONLY_MARKER" not in response.text


@pytest.mark.parametrize("actor", ["student01", "admin"])
def test_missing_writeup_lab_returns_not_found(client, headers, actor):
    response = client.get("/api/labs/00000000-0000-0000-0000-000000000000/writeup", headers=headers[actor])
    assert response.status_code == 404


@pytest.mark.parametrize("actor", ["student01", "admin"])
def test_public_lab_serialization_omits_long_writeup(client, headers, written_lab, actor):
    for path in ("/api/labs", f"/api/labs/{written_lab.id}"):
        response = client.get(path, headers=headers[actor])
        assert response.status_code == 200
        data = response.json()["data"]
        labs = data if isinstance(data, list) else [data]
        assert [item["id"] for item in labs] == [written_lab.id]
        assert all("writeup" not in item for item in labs)
        assert "WRITEUP_ONLY_MARKER" not in response.text


def test_session_serialization_omits_long_writeup(client, headers, written_lab):
    started = client.post(f"/api/labs/{written_lab.id}/sessions", headers=headers["student01"])
    assert started.status_code == 202
    session_id = started.json()["data"]["id"]
    responses = [started]
    for actor, path in (
        ("student01", "/api/me/sessions"),
        ("student01", f"/api/lab-sessions/{session_id}"),
        ("admin", f"/api/lab-sessions/{session_id}"),
        ("admin", "/api/admin/lab-sessions"),
    ):
        response = client.get(path, headers=headers[actor])
        assert response.status_code == 200
        responses.append(response)
    for response in responses:
        data = response.json()["data"]
        sessions = data if isinstance(data, list) else [data]
        assert [item["id"] for item in sessions] == [session_id]
        for item in sessions:
            assert item["lab"]["id"] == written_lab.id
            assert "writeup" not in item["lab"]
        assert '"writeup"' not in response.text
        assert "WRITEUP_ONLY_MARKER" not in response.text


def lab_payload(lab):
    return {
        "name": lab.name,
        "target_image_id": lab.target_image_id,
        "target_port": lab.target_port,
        "flag": lab.flag,
        "status": "PUBLISHED",
    }


def test_admin_creates_lab_with_writeup(client, headers, db, lab):
    payload = {**lab_payload(lab), "name": "带参考题解的新实验", "writeup": LONG_WRITEUP}
    response = client.post("/api/admin/labs", headers=headers["admin"], json=payload)
    assert response.status_code == 201
    identifier = response.json()["data"]["id"]
    db.expire_all()
    assert db.get(LabTemplate, identifier).writeup == LONG_WRITEUP.strip()
    detail = client.get(f"/api/admin/labs/{identifier}", headers=headers["admin"])
    assert detail.status_code == 200
    assert detail.json()["data"]["writeup"] == LONG_WRITEUP.strip()


@pytest.mark.parametrize("writeup", ["# 更新题解\n\n教师自定义修复与回归。", ""])
def test_admin_updates_or_explicitly_clears_writeup(client, headers, db, written_lab, writeup):
    payload = {**lab_payload(written_lab), "writeup": writeup}
    response = client.put(f"/api/admin/labs/{written_lab.id}", headers=headers["admin"], json=payload)
    assert response.status_code == 200
    db.refresh(written_lab)
    assert written_lab.writeup == writeup
    detail = client.get(f"/api/admin/labs/{written_lab.id}", headers=headers["admin"])
    assert detail.status_code == 200
    assert detail.json()["data"]["writeup"] == writeup
    student = client.get(f"/api/labs/{written_lab.id}/writeup", headers=headers["student01"])
    assert student.status_code == 200
    assert student.json()["data"]["content"] == writeup


def test_legacy_admin_update_preserves_writeup(client, headers, db, written_lab):
    payload = {**lab_payload(written_lab), "description": "旧客户端修改实验介绍"}
    assert "writeup" not in payload
    response = client.put(f"/api/admin/labs/{written_lab.id}", headers=headers["admin"], json=payload)
    assert response.status_code == 200
    db.refresh(written_lab)
    assert written_lab.description == payload["description"]
    assert written_lab.writeup == LONG_WRITEUP
    detail = client.get(f"/api/admin/labs/{written_lab.id}", headers=headers["admin"])
    assert detail.status_code == 200
    assert detail.json()["data"]["writeup"] == LONG_WRITEUP


def test_student_cannot_save_writeup(client, headers, db, written_lab):
    payload = {**lab_payload(written_lab), "writeup": "学生覆盖题解"}
    response = client.put(f"/api/admin/labs/{written_lab.id}", headers=headers["student01"], json=payload)
    assert response.status_code == 403
    db.refresh(written_lab)
    assert written_lab.writeup == LONG_WRITEUP


def test_builtin_writeup_catalog_is_complete():
    expected = {"SQL 注入基础实验": "sqli-basic"}
    expected.update({item["category"] + " · " + item["title"]: item["slug"] for item in CATALOG})
    assert NAMES == expected
    assert len(NAMES) == 13
    assert set(NAMES.values()) == set(BUILTIN_SLUGS)


@pytest.mark.parametrize("slug", BUILTIN_SLUGS)
def test_builtin_writeup_has_solution_and_shared_assessment(slug):
    content = reference(slug)
    title = "SQL 注入基础实验" if slug == "sqli-basic" else next(item["title"] for item in CATALOG if item["slug"] == slug)
    assert content.startswith(f"# {title} · 参考解答\n")
    for heading in ("目标与实现边界", "复现步骤", "修复思路与回归", "本实验评估要点", "学习验收与评估约定"):
        section = content.split(f"## {heading}\n", 1)
        assert len(section) == 2, heading
        assert section[1].split("\n## ", 1)[0].strip(), heading
    assert content.count("## 学习验收与评估约定") == 1
    assert "### 如何使用操作采集记录" in content


def test_fill_missing_is_idempotent_and_preserves_custom_content(db, lab):
    builtins = []
    custom = "  # 教师自定义\n\n保留内容及首尾空白。\n"
    for index, (name, slug) in enumerate(NAMES.items()):
        item = LabTemplate(
            name=name, target_image_id=lab.target_image_id, target_port=8000,
            flag="flag{test}", writeup=custom if slug == "sqli-basic" else (" \n\t" if index % 2 else ""),
        )
        db.add(item)
        builtins.append((item, slug))
    unmatched_custom = LabTemplate(
        name="教师独立实验", target_image_id=lab.target_image_id, target_port=8000,
        flag="flag{custom}", writeup=custom,
    )
    db.add(unmatched_custom)
    db.commit()
    result = fill_missing(db)
    db.commit()
    db.expire_all()
    assert set(result["updated"]) == {item.id for item, slug in builtins if slug != "sqli-basic"}
    assert result["preserved"] == [item.id for item, slug in builtins if slug == "sqli-basic"]
    assert {item["id"]: item["name"] for item in result["unmatched"]} == {
        lab.id: lab.name, unmatched_custom.id: unmatched_custom.name,
    }
    for item, slug in builtins:
        assert item.writeup == (custom if slug == "sqli-basic" else reference(slug))
    assert lab.writeup == ""
    assert unmatched_custom.writeup == custom
    before = {item.id: item.writeup for item in db.scalars(select(LabTemplate))}
    repeated = fill_missing(db)
    db.commit()
    db.expire_all()
    assert repeated["updated"] == []
    assert set(repeated["preserved"]) == {item.id for item, _ in builtins}
    assert repeated["unmatched"] == result["unmatched"]
    assert {item.id: item.writeup for item in db.scalars(select(LabTemplate))} == before
