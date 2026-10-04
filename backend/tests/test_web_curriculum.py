from sqlalchemy import select, func
import pytest
from app.models import Course, LabTemplate, Lesson, TargetImage
from app.seed_web_security import CATALOG, seed
from app.writeups import reference


def test_curriculum_complete_idempotent_and_preserves_edits(db):
    images = {}
    for item in CATALOG:
        image = TargetImage(display_name=item["slug"], image_id="sha256:" + item["slug"], status="READY")
        db.add(image); db.flush()
        images[item["slug"]] = image.id
    result = seed(db, images)
    db.flush()
    assert len(result) == 12
    assert {i["category"].split(" · ")[0] for i in CATALOG} == {f"A{i:02d}:2025" for i in range(1, 11)}
    assert db.scalar(select(func.count()).select_from(Course)) == 4
    assert db.scalar(select(func.count()).select_from(Lesson)) == 12
    for item in result:
        assert db.get(LabTemplate, item["lab_id"]).writeup == reference(item["slug"])
    lab = db.get(LabTemplate, result[0]["lab_id"])
    lab.steps = "Teacher customization"
    lab.writeup = "# Teacher's custom solution\n\nKeep this content."
    missing = db.get(LabTemplate, result[1]["lab_id"])
    missing.writeup = ""
    assert seed(db, images) == result
    db.flush()
    assert lab.steps == "Teacher customization"
    assert lab.writeup == "# Teacher's custom solution\n\nKeep this content."
    assert missing.writeup == reference(result[1]["slug"])
    assert db.scalar(select(func.count()).select_from(LabTemplate)) == 12
    for lesson in db.scalars(select(Lesson)):
        assert lesson.related_lab_id and "修复建议" in lesson.content and "复盘问题" in lesson.content


def test_incomplete_image_map_publishes_nothing(db):
    with pytest.raises(ValueError):
        seed(db, {})
    assert db.scalar(select(func.count()).select_from(Course)) == 0
