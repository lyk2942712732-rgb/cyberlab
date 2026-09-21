from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class Base(DeclarativeBase):
    pass


pool_options = {} if settings().database_url.startswith("sqlite") else {"pool_size": settings().max_active_sessions + 5, "max_overflow": 5, "pool_timeout": 10}
engine = create_engine(settings().database_url, pool_pre_ping=True, **pool_options)
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def sqlite_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
