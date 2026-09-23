"""Publish the Web curriculum after ADMIN tar uploads. Repeat runs preserve edits."""
import argparse
import json
from pathlib import Path
from sqlalchemy import select
from app.core.db import SessionLocal
from app.models import Chapter, Course, LabTemplate, Lesson, TargetImage

CATALOG = json.loads((Path(__file__).parent / "data" / "web_security.json").read_text(encoding="utf-8"))
SOURCE = "https://top10.owasp.org/2025/"


def seed(db, image_map):
    # Validate everything before writes; a partial mapping must never silently publish broken labs.
    expected = {item["slug"] for item in CATALOG}
    if set(image_map) != expected:
        raise ValueError("Image map must contain exactly: " + ", ".join(sorted(expected)))
    for identifier in image_map.values():
        image = db.get(TargetImage, identifier)
        if not image or image.status != "READY" or not image.image_id:
            raise ValueError("Upload all target tar files and wait for READY before seeding")
    if len(set(image_map.values())) != len(expected):
        raise ValueError("Each scenario requires its own image record")
    summary = []
    for index, item in enumerate(CATALOG):
        course_name = "Web 安全进阶 · " + item["course"]
        course = db.scalar(select(Course).where(Course.name == course_name))
        if not course:
            course = Course(name=course_name, description="以 OWASP Top 10:2025 为框架，通过独立靶机理解风险、验证现象并学习修复。", status="PUBLISHED")
            db.add(course); db.flush()
        chapter = db.scalar(select(Chapter).where(Chapter.course_id == course.id, Chapter.title == item["title"]))
        if not chapter:
            chapter = Chapter(course_id=course.id, title=item["title"], sort_order=index + 1)
            db.add(chapter); db.flush()
        name = item["category"] + " · " + item["title"]
        lab = db.scalar(select(LabTemplate).where(LabTemplate.name == name))
        if not lab:
            steps = ["启动实验并等待就绪，在 Kali 浏览器打开 `http://靶机IP:8000`（替换为实验页地址）。", *item["steps"], "提交 Flag 后，对照课程的修复建议解释根因，完成后结束实验。"]
            lab = LabTemplate(name=name, description=item["concept"], category=item["category"],
                              objective="- 观察正常与异常请求的差异\n- 验证「" + item["title"] + "」的成因\n- 提出并验证服务端修复方案",
                              steps="\n\n".join(f"{i + 1}. {step}" for i, step in enumerate(steps)),
                              target_image_id=image_map[item["slug"]], target_port=8000,
                              flag="flag{web2025_" + item["slug"] + "_completed}", status="PUBLISHED",
                              duration_minutes=90, cpu_limit=0.5, memory_limit=128,
                              difficulty="INTERMEDIATE" if item["slug"] in ("supply", "integrity", "ssrf", "exception") else "BEGINNER")
            db.add(lab); db.flush()
        lesson = db.scalar(select(Lesson).where(Lesson.chapter_id == chapter.id, Lesson.title == item["title"]))
        if not lesson:
            content = (f"# {item['title']}\n\n对应分类：**{item['category']}**\n\n## 原理与边界\n\n{item['concept']}"
                       f"\n\n## 实验观察\n\n" + "\n\n".join(f"{i + 1}. {step}" for i, step in enumerate(item["steps"]))
                       + f"\n\n## 修复建议\n\n{item['fix']}\n\n## 复盘问题\n\n{item['check']}"
                       + "\n\n## 学习验收\n\n记录一条正常请求、一条触发漏洞的请求及其结果。说明服务端在哪一步信任了不可信数据，并写出修复后应有的行为。Flag 仅作为实验完成凭据。"
                       + f"\n\n分类参考：[OWASP Top 10:2025]({SOURCE})。Top 10 是风险类别，并非恰好十种具体漏洞；本课是代表性教学场景。")
            db.add(Lesson(chapter_id=chapter.id, title=item["title"], content=content, sort_order=1, related_lab_id=lab.id, status="PUBLISHED"))
        summary.append({"slug": item["slug"], "lab_id": lab.id})
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-map", required=True, help="JSON mapping scenario slug to uploaded target_images UUID")
    args = parser.parse_args()
    image_map = json.loads(Path(args.image_map).read_text())
    with SessionLocal.begin() as db:
        result = seed(db, image_map)
    print(json.dumps(result, ensure_ascii=False, indent=2))
