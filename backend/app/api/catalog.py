from fastapi import APIRouter
from app.core.security import CurrentUser, DB
from app.services.catalog import CatalogService

router = APIRouter(tags=["Learning"])


@router.get("/courses")
def courses(db: DB, user: CurrentUser):
    return {"data": CatalogService(db).courses(user)}


@router.get("/courses/{identifier}")
def course(identifier: str, db: DB, user: CurrentUser):
    return {"data": CatalogService(db).course(identifier, user)}


@router.get("/lessons/{identifier}")
def lesson(identifier: str, db: DB, user: CurrentUser):
    return {"data": CatalogService(db).lesson(identifier, user)}


@router.post("/lessons/{identifier}/complete")
def complete(identifier: str, db: DB, user: CurrentUser):
    return {"data": CatalogService(db).complete(identifier, user)}


@router.get("/me/progress")
def progress(db: DB, user: CurrentUser):
    return {"data": CatalogService(db).progress(user)}


@router.get("/labs")
def labs(db: DB, user: CurrentUser):
    return {"data": CatalogService(db).labs(user)}


@router.get("/labs/{identifier}")
def lab(identifier: str, db: DB, user: CurrentUser):
    return {"data": CatalogService(db).lab(identifier, user)}


@router.get("/labs/{identifier}/writeup")
def writeup(identifier: str, db: DB, user: CurrentUser):
    return {"data": CatalogService(db).writeup(identifier, user)}
