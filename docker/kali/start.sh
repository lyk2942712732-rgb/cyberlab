#!/bin/sh
set -eu
export XDG_RUNTIME_DIR="/tmp/runtime-student"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
exec dbus-run-session -- python3 /usr/local/bin/desktop-session.py
