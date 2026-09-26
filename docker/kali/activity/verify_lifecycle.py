"""Destructive collector lifecycle QA; run only in a disposable desktop."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
import uuid
from agent import META, identity, request, status

AGENT = str(Path(__file__).with_name('agent.py'))


def run(*args):
    subprocess.run(['python3', AGENT, *args], check=True)


def wait(predicate):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError('lifecycle condition timed out')


def event(value):
    return {'id': str(uuid.uuid4()), 'source': 'shell', 'type': 'terminal.submit', 'data': {'command': value}}


def main():
    report = {}
    run('stop')
    before = status()
    assert before['complete'] and before['status'] == 'finished', before
    report['normal_stop_complete'] = True
    session = str(uuid.uuid4())
    run('start', session, '1', '1')
    request(event('first-committed-before-quota'))
    count = 1
    for _ in range(200):
        try:
            request(event('x' * 15000))
            count += 1
        except RuntimeError:
            break
    else:
        raise AssertionError('quota was not enforced')
    wait(lambda: status()['status'] == 'interrupted')
    meta = json.loads(META.read_text())
    state = status()
    assert '容量上限' in state['error'], state
    with sqlite3.connect(Path(meta['root']) / 'events.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM events').fetchone()[0] == count
        assert json.loads(db.execute('SELECT data FROM events ORDER BY seq LIMIT 1').fetchone()[0])['command'] == 'first-committed-before-quota'
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    report['quota_preserves_committed_events'] = count
    run('start', session, '2', '64')
    meta = json.loads(META.read_text())
    parent = meta['pid']
    child = int(subprocess.check_output(['pgrep', '-P', str(parent)], text=True).strip())
    child_identity = identity(child)
    os.kill(parent, signal.SIGKILL)
    wait(lambda: identity(child) != child_identity)
    assert status()['status'] == 'interrupted'
    report['parent_death_reaps_observer'] = True
    run('start', session, '3', '64')
    parent = json.loads(META.read_text())['pid']
    child = int(subprocess.check_output(['pgrep', '-P', str(parent)], text=True).strip())
    os.kill(child, signal.SIGKILL)
    wait(lambda: status()['status'] == 'interrupted')
    report['observer_death_reported'] = True
    run('start', session, '4', '64')
    request({'control': 'provider', 'source': 'browser', 'status': 'partial'})
    request({'control': 'provider', 'source': 'browser', 'status': 'idle'})
    run('stop')
    assert status()['status'] == 'interrupted' and not status()['complete']
    report['partial_shutdown_not_claimed_complete'] = True
    Path('/tmp/activity-lifecycle-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
