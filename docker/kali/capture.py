"""Start and stop one OpenAdapt recorder for the current Kali desktop."""
import argparse
import json
import os
import signal
import subprocess
import time
import traceback
from pathlib import Path

PID = Path("/tmp/cyberlab-capture.pid")
META = Path("/tmp/cyberlab-capture.json")

RECORDER = r'''
import json, os, signal, sys, time, traceback
from functools import partial
from pathlib import Path
from threading import Event
root = sys.argv[1]
stop = Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())
# The launcher redirects stdout/stderr to a private per-session log, so
# detached workers retain startup diagnostics without writing to a closed pipe.
try:
    from openadapt_capture import Recorder
    import openadapt_capture.recorder as recorder_module

    # The pinned build's 30s worker barrier is too short for cold VM imports.
    # Keep this below wait_for_ready and the controller's 180s budget.
    recorder_module._wait_for_tasks_started = partial(
        recorder_module._wait_for_tasks_started, timeout=90.0)
    with Recorder(root, task_description="CyberLab desktop activity capture",
                  capture_audio=False, capture_video=True, capture_images=True,
                  video_encoding="mpeg4", video_pixel_format="yuv420p",
                  capture_structural_observations=False, screen_capture_fps=5,
                  plot_performance=False) as recorder:
        try:
            if not recorder.wait_for_ready(timeout=120):
                raise RuntimeError("recorder did not become ready within 120 seconds")
            if stop.is_set():
                raise RuntimeError("recorder startup cancelled")
            Path(root, "ready.json").write_text(json.dumps({"session_id": recorder.control_session_id}))
            while not stop.wait(1):
                recorder.check_health()
        except BaseException:
            # Persist the reason before __exit__ attempts potentially slow cleanup.
            Path(root, "recorder-error.log").write_text(traceback.format_exc())
            raise
        finally:
            Path(root, "ready.json").unlink(missing_ok=True)
except BaseException:
    Path(root, "recorder-error.log").write_text(traceback.format_exc())
    raise
finally:
    Path(root, "ready.json").unlink(missing_ok=True)
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
    env.update(DISPLAY=":1", XDG_RUNTIME_DIR="/tmp/runtime-student", NO_AT_BRIDGE="0", MOZ_ACCESSIBILITY_ATSPI_ENABLED="1",
               LOGURU_LEVEL="WARNING")
    log_fd = os.open(root / "recorder.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(log_fd, "a") as log:
        proc = subprocess.Popen(["/opt/openadapt/bin/python", "-c", RECORDER, str(root)],
                                env=env, start_new_session=True,
                                stdout=log, stderr=subprocess.STDOUT)
    PID.write_text(str(proc.pid))
    META.write_text(json.dumps({"session_id": session, "generation": generation, "root": str(root), "pid": proc.pid}))

def stop() -> None:
    if not PID.exists():
        return
    try:
        pid = int(PID.read_text())
        # Signal only the recorder supervisor first.  Its OpenAdapt worker
        # processes must remain alive while Recorder.stop() drains writers,
        # seals the database, and publishes the verified terminal state.
        # Broadcasting SIGINT to the whole process group interrupts those
        # workers and turns an otherwise recoverable stop into a startup
        # failure.
        os.kill(pid, signal.SIGINT)
    except (ProcessLookupError, ValueError):
        PID.unlink(missing_ok=True)
        return
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
            # A zombie has already exited; kill(pid, 0) alone still succeeds.
            if Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
                break
        except (ProcessLookupError, FileNotFoundError, ValueError):
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
try:
    start(args.session, args.generation) if args.operation == "start" else stop()
except Exception:
    if args.operation == "start":
        root = Path(os.environ.get("CYBERLAB_CAPTURE_ROOT", "/var/lib/cyberlab/captures")) / args.session / str(args.generation)
        if root.is_dir():
            (root / "recorder-error.log").write_text(traceback.format_exc())
    raise
