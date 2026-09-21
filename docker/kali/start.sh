#!/bin/sh
set -eu
export XDG_RUNTIME_DIR="/tmp/runtime-student"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
cleanup() {
  for pid in ${xfce_pid:-} ${web_pid:-} ${vnc_pid:-}; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM
# VNC listens only inside this container. The trusted controller uses a fixed
# Docker exec transport; no VNC/noVNC port is published on the host/network.
Xtigervnc :1 -geometry 1440x900 -depth 24 -localhost yes -SecurityTypes None -rfbport 5901 &
vnc_pid=$!
python3 - <<'PY'
import socket, time
for _ in range(100):
    try:
        with socket.create_connection(('127.0.0.1', 5901), 1):
            break
    except OSError:
        time.sleep(.1)
else:
    raise SystemExit('VNC did not start')
PY
dbus-run-session -- xfce4-session &
xfce_pid=$!
websockify --web=/usr/share/novnc 127.0.0.1:6080 127.0.0.1:5901 &
web_pid=$!
wait "$vnc_pid"
