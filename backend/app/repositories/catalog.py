from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


class Repository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, model, identifier: str):
        obj = self.db.get(model, identifier)
        if obj is None:
            raise HTTPException(404, "记录不存在")
        return obj

    def list(self, model, *conditions, order=None):
        query = select(model).where(*conditions)
        if order is not None:
            query = query.order_by(order)
        return list(self.db.scalars(query))

    def save(self, obj):
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def remove(self, obj):
        self.db.delete(obj)
        self.db.commit()


def public(obj, exclude=()) -> dict:
    # Never serialize password hashes, uploaded paths or submitted/expected flags implicitly.
    # Long reference solutions are fetched explicitly, not on every session poll.
    hidden = {"password_hash", "flag", "submitted_flag", "upload_path", "writeup", *exclude}
    return {col.name: getattr(obj, col.name) for col in obj.__table__.columns if col.name not in hidden}
