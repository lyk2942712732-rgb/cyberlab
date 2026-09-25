from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import SessionStopRequest


def stop_requested(db: Session, session_id: str) -> bool:
    # Query the column each time, avoiding stale objects in the identity map.
    return db.scalar(select(SessionStopRequest.session_id).where(
        SessionStopRequest.session_id == session_id)) is not None
