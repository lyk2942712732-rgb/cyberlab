#!/usr/bin/python3
"""Bash and Firefox native-messaging transport; no persistent input buffers."""
import json
import os
import struct
import sys
import uuid
from agent import MAX_MESSAGE, request


def send(source, kind, data):
    return request({'id': str(uuid.uuid4()), 'source': source, 'type': kind, 'data': data})


def native():
    stream = sys.stdin.buffer
    while header := stream.read(4):
        if len(header) != 4:
            raise ValueError('incomplete native message header')
        size = struct.unpack('<I', header)[0]
        if size > MAX_MESSAGE:
            raise ValueError('native message too large')
        raw = stream.read(size)
        if len(raw) != size:
            raise ValueError('incomplete native message')
        try:
            message = json.loads(raw)
            if message.get('control') == 'provider':
                result = request({'control': 'provider', 'source': 'browser', 'status': message.get('status', 'ready')})
            else:
                message['source'] = 'browser'
                result = request(message)
        except Exception as exc:
            result = {'ok': False, 'error': str(exc)}
        payload = json.dumps(result).encode()
        sys.stdout.buffer.write(struct.pack('<I', len(payload)) + payload)
        sys.stdout.buffer.flush()
    try:
        request({'control': 'provider', 'source': 'browser', 'status': 'idle'})
    except (OSError, RuntimeError):
        pass


if __name__ == '__main__':
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'shell':
            raw = sys.stdin.buffer.read(MAX_MESSAGE + 1)
            if len(raw) > MAX_MESSAGE:
                raise ValueError('command too long to record')
            command = raw.decode('utf-8', errors='replace')
            send('shell', 'terminal.submit', {'command': command, 'cwd': os.getcwd(), 'shell_pid': sys.argv[2], 'semantics': 'submitted_not_verified_success'})
        elif len(sys.argv) > 1 and sys.argv[1] == 'shell-ready':
            request({'control': 'provider', 'source': 'shell', 'status': 'ready'})
        else:
            native()
    except Exception as exc:
        if len(sys.argv) > 1 and sys.argv[1] == 'shell':
            try:
                request({'control': 'provider', 'source': 'shell', 'status': 'partial'})
            except Exception:
                pass
        print('CyberLab 操作记录未保存: ' + str(exc), file=sys.stderr)
        sys.exit(1)
