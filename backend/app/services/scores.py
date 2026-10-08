from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import aware, utcnow
from app.models import Chapter, Course, LabAssessment, LabSession, LabTemplate, LearningProgress, Lesson, Submission, User, ACTIVE_STATUSES
from app.grading import published_score
from app.repositories.catalog import Repository, public


class ScoreService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = Repository(db)

    def scores(self, user_id: str) -> list[dict]:
        submissions = self.repo.list(Submission, Submission.user_id == user_id, order=Submission.created_at)
        sessions = self.repo.list(LabSession, LabSession.user_id == user_id)
        lab_ids = {s.lab_template_id for s in sessions}
        grades = {}
        rows = self.db.execute(select(LabSession.lab_template_id, LabAssessment)
            .join(LabAssessment, LabAssessment.session_id == LabSession.id)
            .where(LabSession.user_id == user_id, LabAssessment.status == "COMPLETED")
            .order_by(LabAssessment.completed_at))
        for lab_id, job in rows:
            score = published_score(job.report)
            if score is not None and (lab_id not in grades or score > grades[lab_id][0]):
                grades[lab_id] = (score, job.session_id)
        labs = self.repo.list(LabTemplate)
        result = []
        for lab in labs:
            if lab.status != "PUBLISHED" and lab.id not in lab_ids:
                continue
            attempts = [s for s in submissions if s.lab_template_id == lab.id]
            correct = next((s for s in attempts if s.correct), None)
            result.append({"lab_id": lab.id, "lab_name": lab.name, "score": grades.get(lab.id, (None, None))[0], "score_session_id": grades.get(lab.id, (None, None))[1], "flag_score": 100 if correct else 0, "completed": bool(correct), "completed_at": correct.created_at if correct else None, "submissions_count": len(attempts), "attempted": lab.id in lab_ids})
        return result

    def students(self) -> list[dict]:
        result = []
        for user in self.repo.list(User, User.role == "STUDENT", order=User.created_at.desc()):
            scores = self.scores(user.id)
            graded = [s for s in scores if s["score"] is not None]
            completed = [s for s in scores if s["completed"]]
            result.append({**public(user), "completed_labs": len(completed), "average_score": round(sum(s["score"] for s in graded) / len(graded), 1) if graded else None, "last_completed_at": max((s["completed_at"] for s in completed), default=None)})
        return result

    def student(self, identifier: str) -> dict:
        user = self.repo.get(User, identifier)
        progress = []
        rows = self.db.execute(select(LearningProgress, Lesson, Chapter, Course).join(Lesson, LearningProgress.lesson_id == Lesson.id).join(Chapter, Lesson.chapter_id == Chapter.id).join(Course, Chapter.course_id == Course.id).where(LearningProgress.user_id == identifier))
        for record, lesson, chapter, course in rows:
            progress.append({**public(record), "lesson_title": lesson.title, "chapter_title": chapter.title, "course_name": course.name})
        return {"user": public(user), "scores": self.scores(identifier), "progress": progress}

    def dashboard(self) -> dict:
        today = utcnow().date()
        sessions = self.repo.list(LabSession)
        first_completions = self.db.scalars(select(func.min(Submission.created_at)).where(Submission.correct.is_(True)).group_by(Submission.user_id, Submission.lab_template_id))
        completed_today = sum(aware(completed_at).date() == today for completed_at in first_completions)
        return {"students": len(self.repo.list(User, User.role == "STUDENT")), "published_courses": len(self.repo.list(Course, Course.status == "PUBLISHED")), "published_labs": len(self.repo.list(LabTemplate, LabTemplate.status == "PUBLISHED")), "running_sessions": sum(s.status in ACTIVE_STATUSES for s in sessions), "completed_today": completed_today}
