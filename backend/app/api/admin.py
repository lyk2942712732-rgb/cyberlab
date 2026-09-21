from fastapi import APIRouter, Form, UploadFile
from app.core.security import AdminUser, DB
from app.models import Chapter, Course, LabSession, LabTemplate, Lesson, TargetImage, User
from app.repositories.catalog import public
from app.schemas.inputs import ChapterInput, CourseInput, LabInput, LessonInput
from app.services.catalog import CatalogService
from app.services.images import ImageService
from app.services.scores import ScoreService
from app.services.sessions import SessionService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
def dashboard(db: DB, user: AdminUser):
    return {"data": ScoreService(db).dashboard()}


@router.get("/students")
def students(db: DB, user: AdminUser):
    return {"data": ScoreService(db).students()}


@router.get("/students/{identifier}")
def student(identifier: str, db: DB, user: AdminUser):
    return {"data": ScoreService(db).student(identifier)}


@router.get("/scores")
def scores(db: DB, user: AdminUser):
    service = ScoreService(db)
    return {"data": [{**public(student), "scores": service.scores(student.id)} for student in service.repo.list(User, User.role == "STUDENT")]}


@router.post("/courses", status_code=201)
def create_course(data: CourseInput, db: DB, user: AdminUser):
    return {"data": CatalogService(db).save(Course, data)}


@router.put("/courses/{identifier}")
def update_course(identifier: str, data: CourseInput, db: DB, user: AdminUser):
    return {"data": CatalogService(db).save(Course, data, identifier)}


@router.delete("/courses/{identifier}")
def delete_course(identifier: str, db: DB, user: AdminUser):
    return {"data": CatalogService(db).delete(Course, identifier)}


@router.post("/chapters", status_code=201)
def create_chapter(data: ChapterInput, db: DB, user: AdminUser):
    return {"data": CatalogService(db).save(Chapter, data)}


@router.put("/chapters/{identifier}")
def update_chapter(identifier: str, data: ChapterInput, db: DB, user: AdminUser):
    return {"data": CatalogService(db).save(Chapter, data, identifier)}


@router.delete("/chapters/{identifier}")
def delete_chapter(identifier: str, db: DB, user: AdminUser):
    return {"data": CatalogService(db).delete(Chapter, identifier)}


@router.post("/lessons", status_code=201)
def create_lesson(data: LessonInput, db: DB, user: AdminUser):
    return {"data": CatalogService(db).save(Lesson, data)}


@router.put("/lessons/{identifier}")
def update_lesson(identifier: str, data: LessonInput, db: DB, user: AdminUser):
    return {"data": CatalogService(db).save(Lesson, data, identifier)}


@router.delete("/lessons/{identifier}")
def delete_lesson(identifier: str, db: DB, user: AdminUser):
    return {"data": CatalogService(db).delete(Lesson, identifier)}


@router.get("/labs/{identifier}")
def read_lab(identifier: str, db: DB, user: AdminUser):
    return {"data": CatalogService(db).lab(identifier, user, include_flag=True)}


@router.post("/labs", status_code=201)
def create_lab(data: LabInput, db: DB, user: AdminUser):
    return {"data": CatalogService(db).save(LabTemplate, data)}


@router.put("/labs/{identifier}")
def update_lab(identifier: str, data: LabInput, db: DB, user: AdminUser):
    return {"data": CatalogService(db).save(LabTemplate, data, identifier)}


@router.delete("/labs/{identifier}")
def delete_lab(identifier: str, db: DB, user: AdminUser):
    return {"data": CatalogService(db).delete(LabTemplate, identifier)}


@router.post("/images/upload", status_code=202)
def upload_image(file: UploadFile, db: DB, user: AdminUser, display_name: str = Form(...)):
    return {"data": ImageService(db).upload(file, display_name)}


@router.get("/images")
def images(db: DB, user: AdminUser):
    service = ImageService(db)
    return {"data": [public(i) for i in service.repo.list(TargetImage, order=TargetImage.created_at.desc())]}


@router.delete("/images/{identifier}")
def delete_image(identifier: str, db: DB, user: AdminUser):
    return {"data": ImageService(db).delete(identifier)}


@router.get("/lab-sessions")
def sessions(db: DB, user: AdminUser):
    service = SessionService(db)
    return {"data": [{**service.describe(s), "student": public(service.repo.get(User, s.user_id))} for s in service.repo.list(LabSession, order=LabSession.started_at.desc())]}


@router.post("/lab-sessions/{identifier}/stop", status_code=202)
def stop(identifier: str, db: DB, user: AdminUser):
    return {"data": SessionService(db).command(identifier, user, "stop")}
