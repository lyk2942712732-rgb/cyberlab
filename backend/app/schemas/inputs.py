from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class Register(Login):
    real_name: str = Field(default="", max_length=100)
    student_number: str = Field(min_length=1, max_length=64)


class CourseInput(Input):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    status: Literal["DRAFT", "PUBLISHED", "DISABLED"] = "DRAFT"


class ChapterInput(Input):
    course_id: str
    title: str = Field(min_length=1, max_length=200)
    sort_order: int = Field(default=0, ge=0)


class LessonInput(Input):
    chapter_id: str
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=100000)
    sort_order: int = Field(default=0, ge=0)
    related_lab_id: str | None = None
    status: Literal["DRAFT", "PUBLISHED", "DISABLED"] = "DRAFT"


class LabInput(Input):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    objective: str = Field(default="", max_length=20000)
    steps: str = Field(default="", max_length=50000)
    writeup: str = Field(default="", max_length=100000)
    category: str = Field(default="Web 安全", max_length=64)
    difficulty: Literal["BEGINNER", "INTERMEDIATE", "ADVANCED"] = "BEGINNER"
    target_image_id: str
    target_port: int = Field(ge=1, le=65535)
    duration_minutes: int = Field(default=120, ge=5, le=480)
    cpu_limit: float = Field(default=1, ge=0.25, le=4)
    memory_limit: int = Field(default=512, ge=64, le=4096)
    flag: str = Field(min_length=1, max_length=512)
    status: Literal["DRAFT", "PUBLISHED", "DISABLED"] = "DRAFT"


class FlagInput(Input):
    flag: str = Field(min_length=1, max_length=512)
