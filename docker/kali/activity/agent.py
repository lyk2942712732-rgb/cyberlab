#!/usr/bin/python3
"""Bounded, local operation journal. No screen capture or keyboard recording."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import resource
import signal
import socket
import sqlite3
import struct
import subprocess
import sys
import time
import uuid

RUNTIME = Path('/tmp/cyberlab-activity')
SOCKET = RUNTIME / 'events.sock'
META = RUNTIME / 'owner.json'
MAX_MESSAGE = 65536
MAX_TEXT = 16384
SOURCES = {'shell', 'browser', 'desktop'}
TYPES = {'terminal.submit', 'web.click', 'web.change', 'web.submit', 'web.navigate', 'ui.click', 'ui.change'}


def atomic(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return fields[19] if fields[0] != 'Z' else None
    except (OSError, IndexError):
        return None


def request(message):
    payload = json.dumps(message, ensure_ascii=False).encode()
    if len(payload) > MAX_MESSAGE:
        raise ValueError('event exceeds 64 KiB')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        client.connect(str(SOCKET))
        client.sendall(payload + b'\n')
        reply = bytearray()
        while b'\n' not in reply:
            chunk = client.recv(4096)
            if not chunk:
                raise RuntimeError('collector disconnected before acknowledgement')
            reply.extend(chunk)
            if len(reply) > MAX_MESSAGE:
                raise RuntimeError('invalid collector response')
        result = json.loads(reply)
        if not result.get('ok'):
            raise RuntimeError(result.get('error', 'write failed'))
        return result


def validate(event):
    if not isinstance(event, dict) or event.get('source') not in SOURCES or event.get('type') not in TYPES:
        raise ValueError('invalid event source/type')
    prefix = {'shell': 'terminal.', 'browser': 'web.', 'desktop': 'ui.'}[event['source']]
    if not event['type'].startswith(prefix):
        raise ValueError('source/type mismatch')
    data = event.get('data')
    if not isinstance(data, dict):
        raise ValueError('event data must be an object')
    # Bound nested input before it enters SQLite. Do not truncate silently.
    if len(json.dumps(data, ensure_ascii=False).encode()) > MAX_TEXT:
        raise ValueError('event content exceeds 16 KiB')
    identifier = str(uuid.UUID(event['id']))
    return identifier, event['source'], event['type'], data


class Journal:
    def __init__(self, root, session, generation, max_bytes):
        self.root, self.max_bytes = root, max_bytes
        self.db = sqlite3.connect(root / 'events.sqlite3')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA cache_size=-1024')
        self.db.execute('PRAGMA wal_autocheckpoint=64')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, timestamp REAL NOT NULL, source TEXT NOT NULL, type TEXT NOT NULL, data TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS deliveries (event_id TEXT PRIMARY KEY, seq INTEGER NOT NULL)')
        self.state = dict(schema=1, session_id=session, generation=generation,
                          status='starting', started_at=time.time(), heartbeat_at=time.time(),
                          pid=os.getpid(), process_identity=identity(os.getpid()), events=0,
                          complete=False, error=None, providers={})
        self.save()

    def save(self):
        self.state['heartbeat_at'] = time.time()
        atomic(self.root / 'state.json', self.state)

    def provider(self, source, status):
        if source not in SOURCES or status not in ('ready', 'idle', 'partial'):
            raise ValueError('invalid provider state')
        previous = self.state['providers'].get(source, {})
        # Recovery/normal browser shutdown cannot erase an earlier coverage gap.
        if previous.get('status') == 'partial':
            status = 'partial'
        self.state['providers'][source] = {'status': status, 'at': time.time()}

    def accept(self, event):
        identifier, source, kind, data = validate(event)
        existing = self.db.execute('SELECT seq FROM events WHERE event_id=?', (identifier,)).fetchone()
        if not existing:
            existing = self.db.execute('SELECT seq FROM deliveries WHERE event_id=?', (identifier,)).fetchone()
        if existing:
            return existing[0]
        # Browser DOM and X11 see the same physical click. Prefer the DOM target,
        # regardless of delivery order; unrelated/repeated clicks stay distinct.
        if kind in ('ui.click', 'web.click'):
            other = 'web.click' if kind == 'ui.click' else 'ui.click'
            rows = self.db.execute('SELECT seq,data FROM events WHERE type=? AND timestamp>? ORDER BY seq DESC LIMIT 4', (other, time.time() - .75)).fetchall()
            for seq, raw in rows:
                previous = json.loads(raw)
                native = data if kind == 'ui.click' else previous
                web = previous if kind == 'ui.click' else data
                if 'firefox' not in (str(native.get('app', '')) + str(native.get('window', ''))).lower():
                    continue
                if not all(isinstance(d.get(k), (int, float)) for d in (native, web) for k in ('x', 'y', 'button')):
                    continue
                if native['x'] != web['x'] or native['y'] != web['y'] or native['button'] != web['button'] + 1:
                    continue
                # Each physical click can have at most one paired native delivery.
                if self.db.execute('SELECT 1 FROM deliveries WHERE seq=?', (seq,)).fetchone():
                    continue
                if kind == 'web.click':
                    self.db.execute('UPDATE events SET source=?,type=?,data=? WHERE seq=?', ('browser', kind, json.dumps(data, ensure_ascii=False), seq))
                self.db.execute('INSERT INTO deliveries VALUES(?,?)', (identifier, seq))
                self.db.commit()
                return seq
        size = sum(p.stat().st_size for p in self.root.glob('events.sqlite3*'))
        if size + MAX_MESSAGE > self.max_bytes:
            raise RuntimeError('操作日志已达到容量上限')
        row = self.db.execute('INSERT INTO events(event_id,timestamp,source,type,data) VALUES(?,?,?,?,?)',
                              (identifier, time.time(), source, kind, json.dumps(data, ensure_ascii=False)))
        self.db.commit()
        self.state['events'] += 1
        self.state['last_event_at'] = time.time()
        return row.lastrowid

    def close(self, complete):
        self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        valid = self.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        self.db.close()
        self.state.update(status='finished' if complete and valid else 'interrupted',
                          complete=complete and valid, ended_at=time.time())
        self.save()


def serve(root, session, generation, max_bytes):
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_AS, (128 * 1024**2, 128 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    root.mkdir(parents=True, exist_ok=False)
    journal = Journal(root, session, generation, max_bytes)
    stopping = False
    desktop = None
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(SOCKET))
            listener.listen(16)
            listener.settimeout(.5)
            atomic(META, {'pid': os.getpid(), 'process_identity': identity(os.getpid()), 'root': str(root)})
            desktop = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('desktop.py'))])
            journal.state['status'] = 'running'
            last_save = 0
            cpu_sample = None
            overloaded = 0
            while not stopping:
                if desktop.poll() is not None:
                    raise RuntimeError('桌面操作采集进程退出')
                desktop_state = journal.state['providers'].get('desktop')
                if desktop_state and time.time() - desktop_state['at'] > 10:
                    raise RuntimeError('桌面操作采集心跳超时')
                if time.monotonic() - last_save >= 2:
                    # Bound a malfunctioning desktop observer independently of Firefox.
                    fields = Path(f'/proc/{desktop.pid}/stat').read_text().rsplit(')', 1)[1].split()
                    ticks = int(fields[11]) + int(fields[12])
                    now = time.monotonic()
                    if cpu_sample:
                        seconds = (ticks - cpu_sample[1]) / os.sysconf('SC_CLK_TCK')
                        overloaded = overloaded + 1 if seconds / (now - cpu_sample[0]) > .25 else 0
                        if overloaded >= 5:
                            raise RuntimeError('桌面操作采集持续超出 CPU 预算，已停止该采集进程')
                    cpu_sample = (now, ticks)
                    journal.save()
                    last_save = time.monotonic()
                try:
                    connection, _ = listener.accept()
                except TimeoutError:
                    continue
                with connection:
                    connection.settimeout(.5)
                    response = {'ok': False}
                    try:
                        _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                        if uid != os.getuid():
                            raise ValueError('unexpected client uid')
                        raw = bytearray()
                        while b'\n' not in raw:
                            chunk = connection.recv(4096)
                            if not chunk:
                                raise ValueError('incomplete message')
                            raw.extend(chunk)
                            if len(raw) > MAX_MESSAGE:
                                raise ValueError('message too large')
                        message = json.loads(raw.split(b'\n', 1)[0])
                        if message.get('control') == 'stop':
                            stopping = True
                            response = {'ok': True}
                        elif message.get('control') == 'status':
                            response = {'ok': True, 'state': journal.state}
                        elif message.get('control') == 'provider' and message.get('source') in SOURCES:
                            journal.provider(message['source'], message.get('status', 'ready'))
                            response = {'ok': True}
                        else:
                            response = {'ok': True, 'seq': journal.accept(message)}
                    except (ValueError, KeyError, TypeError, TimeoutError) as exc:
                        response = {'ok': False, 'error': str(exc)}
                        journal.state['rejected_events'] = journal.state.get('rejected_events', 0) + 1
                    except Exception as exc:
                        journal.state['error'] = str(exc)
                        stopping = True
                        response = {'ok': False, 'error': str(exc)}
                    with contextlib.suppress(OSError):
                        connection.sendall(json.dumps(response).encode() + b'\n')
    except BaseException as exc:
        journal.state['error'] = str(exc)
    finally:
        if desktop is not None and desktop.poll() is None:
            desktop.terminate()
            try:
                desktop.wait(timeout=3)
            except subprocess.TimeoutExpired:
                desktop.kill()
                desktop.wait()
        with contextlib.suppress(Exception):
            journal.close(not journal.state.get('error') and not journal.state.get('rejected_events') and not any(p['status'] == 'partial' for p in journal.state['providers'].values()))
        SOCKET.unlink(missing_ok=True)


def start(session, generation, max_mb):
    uuid.UUID(session)
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    if META.exists():
        old = json.loads(META.read_text())
        if identity(old['pid']) == old['process_identity']:
            raise RuntimeError('activity collector already running')
    SOCKET.unlink(missing_ok=True)
    root = Path(os.environ.get('CYBERLAB_ACTIVITY_ROOT', '/var/lib/cyberlab/activity')) / session / str(generation)
    env = os.environ.copy()
    pids = subprocess.check_output(['pgrep', '-x', 'xfce4-session'], text=True).splitlines()
    values = Path(f'/proc/{pids[0]}/environ').read_bytes().split(b'\0')
    for value in values:
        if value.startswith(b'DBUS_SESSION_BUS_ADDRESS='):
            env['DBUS_SESSION_BUS_ADDRESS'] = value.decode().split('=', 1)[1]
    log = RUNTIME / 'agent.log'
    with log.open('w') as stream:
        process = subprocess.Popen(['/usr/bin/python3', __file__, 'serve', session, str(generation), str(max_mb)],
                                   env=env, start_new_session=True, stdout=stream, stderr=stream)
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError('activity collector startup failed: ' + log.read_text()[-1000:])
        try:
            status = request({'control': 'status'})['state']
            if status['providers'].get('desktop', {}).get('status') == 'ready':
                return
        except (OSError, RuntimeError):
            pass
        time.sleep(.1)
    process.terminate()
    raise RuntimeError('activity collector startup timeout')


def status():
    if not META.exists():
        return {'status': 'unavailable', 'error': '采集器尚未启动'}
    meta = json.loads(META.read_text())
    state = json.loads((Path(meta['root']) / 'state.json').read_text())
    if state['status'] in ('starting', 'running') and (identity(meta['pid']) != meta['process_identity'] or time.time() - state['heartbeat_at'] > 10):
        state.update(status='interrupted', complete=False, error='操作采集进程退出或心跳超时')
        atomic(Path(meta['root']) / 'state.json', state)
    return state


def stop():
    if not META.exists():
        return
    meta = json.loads(META.read_text())
    if identity(meta['pid']) != meta['process_identity']:
        status()
        return
    with contextlib.suppress(OSError, RuntimeError):
        request({'control': 'stop'})
    for _ in range(50):
        if identity(meta['pid']) != meta['process_identity']:
            return
        time.sleep(.1)
    os.killpg(meta['pid'], signal.SIGTERM)
    time.sleep(.5)
    if identity(meta['pid']) == meta['process_identity']:
        os.killpg(meta['pid'], signal.SIGKILL)
    status()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['start', 'serve', 'stop', 'status'])
    parser.add_argument('session', nargs='?')
    parser.add_argument('generation', nargs='?', type=int)
    parser.add_argument('max_mb', nargs='?', type=int, default=64)
    args = parser.parse_args()
    if args.operation == 'start':
        start(args.session, args.generation, args.max_mb)
    elif args.operation == 'serve':
        serve(Path(os.environ.get('CYBERLAB_ACTIVITY_ROOT', '/var/lib/cyberlab/activity')) / args.session / str(args.generation), args.session, args.generation, args.max_mb * 1024**2)
    elif args.operation == 'stop':
        stop()
    else:
        print(json.dumps(status(), ensure_ascii=False))
