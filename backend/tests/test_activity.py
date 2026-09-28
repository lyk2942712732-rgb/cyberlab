import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import Mock
import pytest
from app.core.config import settings
from app.core.db import utcnow
from app.models import LabSession
from app.orchestrator.activity import state, events


@pytest.fixture(autouse=True)
def _no_warm_slot_lookup(monkeypatch):
    # Journal pagination is filesystem-only; warm-slot resolution needs a DB.
    @contextmanager
    def factory():
        class _Stub:
            def scalars(self, *_args, **_kwargs):
                return []
        yield _Stub()
    monkeypatch.setattr("app.orchestrator.activity.SessionLocal", factory)


def test_journal_generations_pagination_and_stale_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(settings(), 'activity_dir', str(tmp_path))
    session = str(uuid.uuid4())
    for generation in (1, 2):
        root = tmp_path / session / str(generation); root.mkdir(parents=True)
        (root / 'state.json').write_text(json.dumps({'status': 'running', 'heartbeat_at': time.time() - 30, 'generation': generation}))
        with sqlite3.connect(root / 'events.sqlite3') as db:
            db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,timestamp REAL,source TEXT,type TEXT,data TEXT)')
            db.executemany('INSERT INTO events VALUES(?,?,?,?,?)', [(i, time.time(), 'shell', 'terminal.submit', json.dumps({'command': str(i)})) for i in range(1, 105)])
    assert state(session)['status'] == 'interrupted'
    first = events(session)
    assert first['state']['generation'] == 2 and first['generations'] == [1, 2]
    assert len(first['events']) == 100 and first['next'] == 100
    second = events(session, after=100)
    assert len(second['events']) == 4 and second['next'] is None
    assert events(session, generation=1)['state']['generation'] == 1
    with pytest.raises(ValueError):
        events('../elsewhere')


def test_only_admin_can_read_operation_contents(client, db, users, headers, lab, monkeypatch):
    session = LabSession(user_id=users['student01'].id, lab_template_id=lab.id, expires_at=utcnow() + timedelta(hours=1))
    db.add(session); db.commit()
    fetch = Mock(return_value={'events': []})
    monkeypatch.setattr('app.api.admin.OrchestratorClient.session_activity', fetch)
    path = f'/api/admin/lab-sessions/{session.id}/activity'
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers['student01']).status_code == 403
    assert client.get(path, headers=headers['student02']).status_code == 403
    fetch.assert_not_called()
    assert client.get(path, headers=headers['admin']).status_code == 200
    assert client.get(path + '?after=-1', headers=headers['admin']).status_code == 422
