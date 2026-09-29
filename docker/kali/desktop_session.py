"""Supervise a fresh XFCE desktop without login/session-restore delays."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from check_desktop import check_desktop
from check_x11 import check_shell_ready


def main():
    children = []
    started = time.monotonic()
    runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    env_path = runtime / 'desktop-env.json'
    env_path.unlink(missing_ok=True)

    def log(stage):
        print(f'DESKTOP_STARTUP stage={stage} elapsed={time.monotonic() - started:.3f}', flush=True)

    def launch(*command):
        children.append(subprocess.Popen(command))

    def alive():
        for child in children:
            if child.poll() is not None:
                raise RuntimeError(f'Desktop process exited: {child.args[0]} ({child.returncode})')

    def wait_ready(check):
        deadline = time.monotonic() + 60
        while True:
            alive()
            try:
                check()
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.1)

    def stop(_signal, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        log('begin')
        launch('Xtigervnc', ':1', '-geometry', '1440x900', '-depth', '24', '-s', '0',
               '-localhost', 'yes', '-SecurityTypes', 'None', '-rfbport', '5901')
        launch('websockify', '--web=/usr/share/novnc', '0.0.0.0:6080', '127.0.0.1:5901')
        wait_ready(check_desktop)
        log('vnc')
        # Publish settings first, avoiding a second GTK theme/icon reload in
        # every shell process. Panel and desktop perform their own WM wait.
        launch('xfsettingsd', '--sm-client-disable', '--disable-wm-check')
        wait_ready(lambda: check_shell_ready(settings_only=True))
        log('settings')
        launch('openbox', '--sm-disable')
        launch('xfce4-panel', '--sm-client-disable')
        launch('xfdesktop', '--sm-client-disable')
        wait_ready(check_shell_ready)
        env_path.write_text(json.dumps({key: os.environ[key] for key in
                                       ('DBUS_SESSION_BUS_ADDRESS', 'DISPLAY', 'XDG_RUNTIME_DIR')}))
        env_path.chmod(0o600)
        log('shell-ready')
        while True:
            alive()
            time.sleep(.5)
    finally:
        env_path.unlink(missing_ok=True)
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 3
        for child in children:
            try:
                child.wait(timeout=max(.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    main()
