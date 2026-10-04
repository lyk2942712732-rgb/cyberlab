"""Read bounded operation journals from the controller's local data mount."""
import json
from pathlib import Path
import sqlite3
import time
import uuid
from app.core.config import settings


def _bases(identifier):
    root = Path(settings().activity_dir).resolve()
    bases = []
    session = root / identifier
    if session.is_dir() and not session.is_symlink():
        bases.append(session)
    return bases


def generations(identifier):
    found = {}
    for base in _bases(identifier):
        for path in base.iterdir():
            if path.name.isdigit() and path.is_dir() and not path.is_symlink():
                found[int(path.name)] = base
    return found


def directory(identifier, generation=None):
    identifier = str(uuid.UUID(identifier))
    found = generations(identifier)
    chosen = generation if generation is not None else max(found, default=None)
    if chosen not in found:
        return None
    return found[chosen] / str(chosen)


def state(identifier, generation=None):
    folder = directory(identifier, generation)
    if folder is None:
        return {'status': 'unavailable', 'error': '暂无操作记录'}
    path = folder / 'state.json'
    try:
        if path.is_symlink() or path.stat().st_size > 65536:
            raise ValueError('invalid state')
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError('invalid state object')
        if value['status'] in ('starting', 'running') and time.time() - value['heartbeat_at'] > 10:
            value.update(status='interrupted', complete=False, error='操作采集心跳中断')
        # Internal PIDs and file paths are not relevant to the student UI.
        return {key: value.get(key) for key in ('status', 'error', 'complete', 'generation', 'events', 'last_event_at', 'heartbeat_at', 'providers', 'rejected_events')}
    except (OSError, ValueError, KeyError, TypeError):
        return {'status': 'interrupted', 'error': '无法读取操作记录状态'}


def events(identifier, generation=None, after=0, limit=100):
    folder = directory(identifier, generation)
    summary = state(identifier, generation)
    if folder is None:
        return {'state': summary, 'events': [], 'generations': [], 'next': None}
    available = sorted(generations(identifier))
    path = folder / 'events.sqlite3'
    if any((folder / name).is_symlink() for name in ('events.sqlite3', 'events.sqlite3-wal', 'events.sqlite3-shm')):
        raise ValueError('invalid journal path')
    if not path.is_file():
        return {'state': summary, 'events': [], 'generations': available, 'next': None}
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=1) as db:
        deadline = time.monotonic() + 1
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        rows = db.execute('SELECT seq,timestamp,source,type,data FROM events WHERE seq>? ORDER BY seq LIMIT ?', (after, min(limit, 100) + 1)).fetchall()
    records = [dict(seq=row[0], timestamp=row[1], source=row[2], type=row[3], data=json.loads(row[4])) for row in rows[:limit]]
    return {'state': summary, 'events': records, 'generations': available, 'next': records[-1]['seq'] if len(rows) > limit else None}
