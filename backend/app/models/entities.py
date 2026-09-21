import uuid
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base, utcnow


def uid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    real_name: Mapped[str] = mapped_column(String(100), default="")
    student_number: Mapped[str | None] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(16), default="STUDENT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (CheckConstraint("role IN ('STUDENT','ADMIN')"),)


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Chapter(Base):
    __tablename__ = "chapters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    related_lab_id: Mapped[str | None] = mapped_column(ForeignKey("lab_templates.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")


class TargetImage(Base):
    __tablename__ = "target_images"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    display_name: Mapped[str] = mapped_column(String(200))
    repository: Mapped[str] = mapped_column(String(255), default="")
    tag: Mapped[str] = mapped_column(String(100), default="")
    image_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    repo_digest: Mapped[str | None] = mapped_column(String(300))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    original_filename: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="IMPORTING", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    upload_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LabTemplate(Base):
    __tablename__ = "lab_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="Web 安全")
    difficulty: Mapped[str] = mapped_column(String(20), default="BEGINNER")
    target_image_id: Mapped[str] = mapped_column(ForeignKey("target_images.id"), index=True)
    target_port: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120)
    cpu_limit: Mapped[float] = mapped_column(Float, default=1)
    memory_limit: Mapped[int] = mapped_column(Integer, default=512)
    flag: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


ACTIVE_STATUSES = ("CREATING", "STARTING", "READY", "RESETTING", "STOPPING", "FINISHED")


class LabSession(Base):
    __tablename__ = "lab_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    lab_template_id: Mapped[str] = mapped_column(ForeignKey("lab_templates.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="CREATING", index=True)
    network_id: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    generation: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        Index("uq_one_active_session_per_user", "user_id", unique=True,
              postgresql_where=text("status IN ('CREATING','STARTING','READY','RESETTING','STOPPING','FINISHED')"),
              sqlite_where=text("status IN ('CREATING','STARTING','READY','RESETTING','STOPPING','FINISHED')")),
    )


class LabInstance(Base):
    __tablename__ = "lab_instances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("lab_sessions.id", ondelete="CASCADE"), index=True)
    instance_type: Mapped[str] = mapped_column(String(16))
    runtime_id: Mapped[str] = mapped_column(String(100), unique=True)
    container_name: Mapped[str] = mapped_column(String(100))
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    image: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("lab_sessions.id"), index=True)
    lab_template_id: Mapped[str] = mapped_column(ForeignKey("lab_templates.id"), index=True)
    submitted_flag: Mapped[str] = mapped_column(String(512))
    correct: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)
