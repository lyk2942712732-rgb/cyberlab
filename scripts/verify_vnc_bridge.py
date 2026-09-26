"""Loopback-only QA bridge to an explicitly labelled disposable Kali desktop.

Uses SSH and Docker exec, never publishes a container's VNC port.
Run with the project's Python environment (websockets dependency).
"""
import argparse
import asyncio
import base64
import json
import shlex
import subprocess
import websockets

RELAY = """
import os,select,socket,sys
s=socket.create_connection(('127.0.0.1',5901),timeout=10)
s.settimeout(None)
while True:
 ready,_,_=select.select([s,sys.stdin.buffer],[],[])
 if s in ready:
  data=s.recv(65536)
  if not data:break
  sys.stdout.buffer.write(data);sys.stdout.buffer.flush()
 if sys.stdin.buffer in ready:
  data=os.read(0,65536)
  if not data:break
  s.sendall(data)
"""


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--port', type=int, default=18999)
    args = parser.parse_args()
    ssh = ['ssh', '-T', '-i', args.key, '-o', 'BatchMode=yes', args.host]
    inspect = json.loads(subprocess.check_output(ssh + [shlex.join(['docker', 'inspect', args.container])]))[0]
    assert inspect['Config']['Labels'].get('cyberlab.qa') == 'activity', 'Only explicitly labelled QA containers'
    program = f"import base64;exec(base64.b64decode({base64.b64encode(RELAY.encode()).decode()!r}))"
    command = shlex.join(['docker', 'exec', '-i', args.container, 'python3', '-u', '-c', program])

    async def connect(ws):
        process = await asyncio.create_subprocess_exec(*ssh, command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        async def read():
            while data := await process.stdout.read(65536):
                await ws.send(data)
        async def write():
            async for data in ws:
                if not isinstance(data, bytes):
                    raise ValueError('binary VNC messages required')
                process.stdin.write(data)
                await process.stdin.drain()
        tasks = [asyncio.create_task(read()), asyncio.create_task(write())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

    async with websockets.serve(connect, '127.0.0.1', args.port, origins=['http://localhost:5174'], compression=None):
        print(f'QA VNC bridge ready on loopback:{args.port}', flush=True)
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
