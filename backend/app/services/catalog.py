from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Chapter, Course, LabSession, LabTemplate, LearningProgress, Lesson, TargetImage, User, ACTIVE_STATUSES
from app.repositories.catalog import Repository, public
from app.schemas.inputs import ChapterInput, CourseInput, LabInput, LessonInput


class CatalogService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = Repository(db)

    def courses(self, user: User) -> list[dict]:
        filters = [] if user.role == "ADMIN" else [Course.status == "PUBLISHED"]
        return [self.course(c.id, user) for c in self.repo.list(Course, *filters, order=Course.created_at.desc())]

    def course(self, identifier: str, user: User) -> dict:
        course = self.repo.get(Course, identifier)
        if user.role != "ADMIN" and course.status != "PUBLISHED":
            raise HTTPException(404, "课程不存在")
        result = public(course)
        result["chapters"] = []
        for chapter in self.repo.list(Chapter, Chapter.course_id == identifier, order=Chapter.sort_order):
            lessons = self.repo.list(Lesson, Lesson.chapter_id == chapter.id, order=Lesson.sort_order)
            result["chapters"].append({**public(chapter), "lessons": [public(lesson, ["content"]) for lesson in lessons if user.role == "ADMIN" or lesson.status == "PUBLISHED"]})
        return result

    def lesson(self, identifier: str, user: User) -> dict:
        lesson = self.repo.get(Lesson, identifier)
        chapter = self.repo.get(Chapter, lesson.chapter_id)
        self.course(chapter.course_id, user)
        if user.role != "ADMIN" and lesson.status != "PUBLISHED":
            raise HTTPException(404, "课时不存在")
        return {**public(lesson), "course_id": chapter.course_id}

    def complete(self, identifier: str, user: User) -> dict:
        self.lesson(identifier, user)
        # Serialize updates per user; repeated completion stays idempotent.
        self.db.scalar(select(User).where(User.id == user.id).with_for_update())
        progress = self.db.scalar(select(LearningProgress).where(LearningProgress.user_id == user.id, LearningProgress.lesson_id == identifier))
        return public(progress or self.repo.save(LearningProgress(user_id=user.id, lesson_id=identifier)))

    def progress(self, user: User) -> list[dict]:
        return [public(p) for p in self.repo.list(LearningProgress, LearningProgress.user_id == user.id)]

    def labs(self, user: User) -> list[dict]:
        filters = [] if user.role == "ADMIN" else [LabTemplate.status == "PUBLISHED"]
        return [public(lab) for lab in self.repo.list(LabTemplate, *filters, order=LabTemplate.created_at.desc())]

    def lab(self, identifier: str, user: User, include_flag: bool = False) -> dict:
        lab = self.repo.get(LabTemplate, identifier)
        if user.role != "ADMIN" and lab.status != "PUBLISHED":
            raise HTTPException(404, "实验不存在")
        result = public(lab)
        if include_flag and user.role == "ADMIN":
            result["flag"] = lab.flag
            result["writeup"] = lab.writeup
        return result

    def writeup(self, identifier: str, user: User) -> dict:
        self.lab(identifier, user)  # Same publication/access rules as the lab.
        lab = self.repo.get(LabTemplate, identifier)
        return {"schema_version": 1, "lab_id": lab.id, "title": lab.name,
                "format": "markdown", "content": lab.writeup, "updated_at": lab.updated_at}

    def save(self, model, data: CourseInput | ChapterInput | LessonInput | LabInput, identifier: str | None = None) -> dict:
        values = data.model_dump()
        if model is Chapter:
            self.repo.get(Course, values["course_id"])
        if model is Lesson:
            self.repo.get(Chapter, values["chapter_id"])
            if values["related_lab_id"]:
                self.repo.get(LabTemplate, values["related_lab_id"])
        if model is LabTemplate:
            if identifier and "writeup" not in data.model_fields_set:
                values.pop("writeup", None)  # Older clients must preserve reference edits.
            if identifier:
                self.db.scalar(select(LabTemplate).where(LabTemplate.id == identifier).with_for_update())
            # Same lock used by ImageManager.delete prevents delete/association races.
            image = self.db.scalar(select(TargetImage).where(TargetImage.id == values["target_image_id"]).with_for_update())
            if not image:
                raise HTTPException(404, "靶机镜像不存在")
            if image.status != "READY":
                raise HTTPException(409, "请先选择导入成功的靶机镜像")
            if identifier:
                # Running sessions use the template's flag/resources; edits wait until all finish.
                active = self.db.scalar(select(LabSession).where(LabSession.lab_template_id == identifier, LabSession.status.in_(ACTIVE_STATUSES)))
                if active:
                    raise HTTPException(409, "此实验仍有运行实例，请结束实例后再修改")
        obj = self.repo.get(model, identifier) if identifier else model()
        for name, value in values.items():
            setattr(obj, name, value)
        return public(self.repo.save(obj))

    def delete(self, model, identifier: str):
        obj = self.repo.get(model, identifier)
        if model is LabTemplate and self.db.scalar(select(LabSession.id).where(LabSession.lab_template_id == identifier).limit(1)):
            obj.status = "DISABLED"
            self.repo.save(obj)
            return {"archived": True}
        self.repo.remove(obj)
        return {"deleted": True}
