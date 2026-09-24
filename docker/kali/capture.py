"""Start and stop one OpenAdapt recorder for the current Kali desktop."""
import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

PID = Path("/tmp/cyberlab-capture.pid")
META = Path("/tmp/cyberlab-capture.json")

RECORDER = r'''
import json, signal, sys, time
from pathlib import Path
from threading import Event
from openadapt_capture import Recorder

root = sys.argv[1]
stop = Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())
with Recorder(root, task_description="CyberLab desktop activity capture",
              capture_audio=False, capture_video=True, capture_images=True,
              video_encoding="mpeg4", video_pixel_format="yuv420p",
              capture_structural_observations=False, screen_capture_fps=5,
              plot_performance=False) as recorder:
    if not recorder.wait_for_ready(timeout=180):
        raise RuntimeError("recorder did not become ready")
    Path(root, "ready.json").write_text(json.dumps({"session_id": recorder.control_session_id}))
    while not stop.wait(1):
        recorder.check_health()
'''

def start(session: str, generation: int) -> None:
    root = Path(os.environ.get("CYBERLAB_CAPTURE_ROOT", "/var/lib/cyberlab/captures")) / session / str(generation)
    root.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    pgrep = subprocess.run(["pgrep", "-x", "xfce4-session"], text=True, capture_output=True, check=True)
    xfce_pid = pgrep.stdout.splitlines()[0]
    values = Path(f"/proc/{xfce_pid}/environ").read_bytes().split(b"\0")
    bus = next((v.decode().split("=", 1)[1] for v in values if v.startswith(b"DBUS_SESSION_BUS_ADDRESS=")), None)
    if not bus:
        raise RuntimeError("XFCE session has no D-Bus address")
    env["DBUS_SESSION_BUS_ADDRESS"] = bus
    env.update(DISPLAY=":1", XDG_RUNTIME_DIR="/tmp/runtime-student", NO_AT_BRIDGE="0", MOZ_ACCESSIBILITY_ATSPI_ENABLED="1")
    proc = subprocess.Popen(["/opt/openadapt/bin/python", "-c", RECORDER, str(root)], env=env, start_new_session=True)
    PID.write_text(str(proc.pid))
    META.write_text(json.dumps({"session_id": session, "generation": generation, "root": str(root), "pid": proc.pid}))

def stop() -> None:
    if not PID.exists():
        return
    try:
        pid = int(PID.read_text())
        os.killpg(pid, signal.SIGINT)
    except (ProcessLookupError, ValueError):
        PID.unlink(missing_ok=True)
        return
    deadline = time.time() + 45
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, ValueError):
            break
        time.sleep(.5)
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
            time.sleep(5)
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    PID.unlink(missing_ok=True)

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="operation", required=True)
start_parser = sub.add_parser("start")
start_parser.add_argument("session")
start_parser.add_argument("generation", type=int)
sub.add_parser("stop")
args = parser.parse_args()
start(args.session, args.generation) if args.operation == "start" else stop()
