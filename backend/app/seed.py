"""Idempotent demo content. Runtime images are always uploaded by an ADMIN."""
import argparse
import os
from sqlalchemy import select
from app.core.db import SessionLocal
from app.core.security import passwords
from app.models import Chapter, Course, LabTemplate, Lesson, TargetImage, User
from app.writeups import reference

LESSON = """# SQL 注入原理

SQL 注入发生在应用将不可信输入直接拼接进 SQL 语句时。输入中的引号、运算符可能改变原本的查询逻辑。

## 学习目标

- 理解数据库查询与应用输入的关系。
- 识别字符串拼接造成的查询边界问题。
- 在专属靶机中观察登录校验异常。
- 使用参数化查询修复漏洞。

## 错误示例

```python
query = "SELECT * FROM users WHERE username = '" + username + "'"
```

## 推荐修复

```python
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
```

> 请仅在课程提供的独立实验环境中操作，不要向未授权系统发送测试请求。

阅读完成后标记学习进度，进入关联实验验证你的理解。
"""

STEPS = """1. 启动实验，等待 Kali Desktop 就绪。
2. 在 Kali 中打开 Firefox，访问 `http://靶机IP:8000`，将“靶机IP”替换为实验页显示的地址。
3. 观察登录表单，尝试理解用户名如何影响后端查询。
4. 通过实验靶机的登录页面获取 Flag，并提交到下方判题区域。
5. 思考如何用参数化查询修复问题，完成后结束实验。

提示：本实验重点在于查询语句中的引号边界与布尔表达式，无需扫描其他网络。
"""


def ensure_user(db, username: str, role: str, password: str | None, **profile):
    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        return existing
    if not password or len(password) < 12 or password.startswith("replace-"):
        raise ValueError(f"Set a unique {username} password of at least 12 characters in .env")
    user = User(username=username, password_hash=passwords.hash(password), role=role, **profile)
    db.add(user)
    db.flush()
    return user


def seed(image_id: str | None = None):
    with SessionLocal.begin() as db:
        ensure_user(db, "admin", "ADMIN", os.getenv("ADMIN_PASSWORD"), real_name="教学管理员")
        ensure_user(db, "student01", "STUDENT", os.getenv("STUDENT_PASSWORD"), real_name="演示学生", student_number="20260001")
        course = db.scalar(select(Course).where(Course.name == "Web 安全基础"))
        if not course:
            course = Course(name="Web 安全基础", description="理解 Web 应用常见安全问题，在独立环境中建立防护意识与实践能力。", status="PUBLISHED")
            db.add(course)
            db.flush()
        chapter = db.scalar(select(Chapter).where(Chapter.course_id == course.id, Chapter.title == "SQL Injection"))
        if not chapter:
            chapter = Chapter(course_id=course.id, title="SQL Injection", sort_order=1)
            db.add(chapter)
            db.flush()
        lesson = db.scalar(select(Lesson).where(Lesson.chapter_id == chapter.id, Lesson.title == "SQL 注入原理"))
        if not lesson:
            lesson = Lesson(chapter_id=chapter.id, title="SQL 注入原理", content=LESSON, sort_order=1, status="PUBLISHED")
            db.add(lesson)
        if image_id:
            image = db.get(TargetImage, image_id)
            if not image or image.status != "READY":
                raise ValueError("The image must first be uploaded and reach READY in the teaching console")
            lab = db.scalar(select(LabTemplate).where(LabTemplate.name == "SQL 注入基础实验"))
            if not lab:
                lab = LabTemplate(name="SQL 注入基础实验", description="通过一个简单的教学登录页面，理解 SQL 注入的成因与参数化查询的价值。", objective="- 理解 SQL 查询边界\n- 在授权靶机上验证输入处理缺陷\n- 掌握参数化查询的防护思路", steps=STEPS, target_image_id=image.id, target_port=8000, flag="flag{sqli_success}", status="PUBLISHED", duration_minutes=120, cpu_limit=1, memory_limit=512)
                db.add(lab)
                db.flush()
            lesson.related_lab_id = lab.id
            if not lab.writeup:
                lab.writeup = reference("sqli-basic")
        print("Demo users and theory course are ready." + (" Demo lab linked." if image_id else " Upload the target, then re-run with --demo-image-id to link the demo lab."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-image-id", help="target_images UUID from the admin image API")
    args = parser.parse_args()
    seed(args.demo_image_id)
