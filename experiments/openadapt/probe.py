"""Exercise real applications with XTest input in an isolated pilot container.

This is automated native desktop recording, not a student/human recording.
Never run this against a live student's desktop.
"""

import argparse
import faulthandler
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import threading
import time
import traceback


def run(*args):
    return subprocess.check_output(args, text=True, timeout=20).strip()


def session_environment():
    pid = run("pgrep", "-x", "xfce4-session").splitlines()[0]
    for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
        if item.startswith(b"DBUS_SESSION_BUS_ADDRESS="):
            key, value = item.decode().split("=", 1)
            os.environ[key] = value
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
        raise RuntimeError("No XFCE session bus; refusing an unrelated accessibility session")
    os.environ.update(DISPLAY=":1", XDG_RUNTIME_DIR="/tmp/runtime-student",
                      NO_AT_BRIDGE="0", MOZ_ACCESSIBILITY_ATSPI_ENABLED="1")


def resources():
    cpu = dict(line.split() for line in Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())
    return {"timestamp": time.time(), "cpu_usage_usec": int(cpu["usage_usec"]),
            "memory_bytes": int(Path("/sys/fs/cgroup/memory.current").read_text()),
            "pids": int(Path("/sys/fs/cgroup/pids.current").read_text())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app", choices=["terminal", "firefox", "burp"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    session_environment()
    # Python 3.14 defaults to forkserver on Linux. Preload once instead of
    # importing the recorder independently in four writers on a small VM.
    multiprocessing.set_forkserver_preload(["openadapt_capture.recorder"])
    os.environ.setdefault("LOGURU_LEVEL", "WARNING")
    from openadapt_capture import Recorder
    import openadapt_capture.recorder as recorder_module
    # The pilot VM has slow cold starts. Keep a finite startup deadline without
    # changing the recorder's evidence, validation or shutdown requirements.
    recorder_module._wait_for_tasks_started.__kwdefaults__["timeout"] = 120.0
    original_task_runner = recorder_module._run_task_fail_loud
    def diagnostic_task_runner(task_name, target, task_args, terminate, errors):
        def traced_target(*call_args):
            try:
                return target(*call_args)
            except BaseException:
                print("NATIVE_TASK_FAILED", task_name, flush=True)
                traceback.print_exc()
                raise
        return original_task_runner(task_name, traced_target, task_args, terminate, errors)
    recorder_module._run_task_fail_loud = diagnostic_task_runner
    faulthandler.dump_traceback_later(120, repeat=True)

    processes = []
    logfile = (args.output / "application.log").open("w")
    if args.app == "terminal":
        command = ["xfce4-terminal", "--disable-server", "--title=Capture Terminal Pilot"]
        title = "Capture Terminal Pilot"
    elif args.app == "firefox":
        profile = args.output / "firefox-profile"
        profile.mkdir()
        (profile / "user.js").write_text('user_pref("browser.shell.checkDefaultBrowser", false);\n'
            'user_pref("browser.aboutwelcome.enabled", false);\n'
            'user_pref("datareporting.policy.dataSubmissionEnabled", false);\n'
            'user_pref("accessibility.force_disabled", -1);\n')
        page = args.output / "page"
        page.mkdir()
        (page / "index.html").write_text('''<!doctype html><meta charset="utf-8">
<title>CyberLab Capture Pilot</title><style>body{font:24px sans-serif;margin:60px}
input,button{font:24px sans-serif;padding:12px;display:block;margin:20px 0}</style>
<h1>CyberLab Capture Pilot</h1><label for="answer">Lab answer</label>
<input id="answer" aria-label="Lab answer" autofocus><button id="check"
onclick="document.getElementById('result').textContent='Result: '+document.getElementById('answer').value">Validate answer</button>
<p id="result">Waiting for input</p>''')
        processes.append(subprocess.Popen(["python3", "-m", "http.server", "8765", "--bind",
            "127.0.0.1", "--directory", str(page)], stdout=logfile, stderr=logfile))
        command = ["firefox-esr", "--no-remote", "--profile", str(profile), "http://127.0.0.1:8765/"]
        title = "CyberLab Capture Pilot"
    else:
        command = ["java", "-Xmx512m", "-jar", "/usr/share/burpsuite/burpsuite.jar",
                   "--suppress-jre-check", "--disable-check-for-updates-dialog"]
        title = "Burp Suite"
    processes.append(subprocess.Popen(command, stdout=logfile, stderr=logfile))
    try:
        deadline = time.monotonic() + 60
        window = None
        while time.monotonic() < deadline:
            found = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", title],
                                   text=True, capture_output=True)
            if found.returncode == 0:
                window = found.stdout.strip().splitlines()[-1]
                break
            time.sleep(0.5)
        if not window:
            raise RuntimeError(f"No visible {args.app} window")
        run("xdotool", "windowactivate", "--sync", window)
        run("xdotool", "windowmove", window, "60", "60")
        run("xdotool", "windowsize", window, "1100", "700")
        time.sleep(4)
        baseline = resources()
        samples = []
        done = threading.Event()
        def sample():
            while not done.wait(0.5):
                samples.append(resources())
        thread = threading.Thread(target=sample, daemon=True)
        thread.start()
        try:
            with Recorder(str(args.output / "capture"),
                          task_description=f"Automated native UI pilot: {args.app}; XTest input, no student data",
                          capture_audio=False, capture_video=True,
                          capture_images=True, video_encoding="mpeg4",
                          video_pixel_format="yuv420p",
                          capture_structural_observations=False, screen_capture_fps=5,
                          plot_performance=False) as recorder:
                if not recorder.wait_for_ready(timeout=180):
                    raise RuntimeError("Recorder did not become ready")
                (args.output / "ready.json").write_text(json.dumps({"session_id": recorder.control_session_id}))
                print("RECORDER_READY", recorder.control_session_id, flush=True)
                time.sleep(2)
                if args.app == "terminal":
                    run("xdotool", "mousemove", "280", "230", "click", "1")
                    run("xdotool", "type", "--clearmodifiers", "--delay", "80",
                        "printf 'CYBERLAB_CAPTURE_OK\\n'; uname -s")
                    run("xdotool", "key", "Return")
                elif args.app == "firefox":
                    run("xdotool", "type", "--clearmodifiers", "--delay", "120", "pilot-answer-42")
                    run("xdotool", "key", "Tab")
                    time.sleep(1)
                    run("xdotool", "key", "Return")
                    time.sleep(2)
                    run("xdotool", "mousemove", "300", "450", "click", "1")
                else:
                    # Navigation within Burp's first-run UI, not attack traffic.
                    run("xdotool", "mousemove", "350", "280", "click", "1")
                    run("xdotool", "key", "Tab")
                    run("xdotool", "key", "Tab")
                print("INPUT_SENT", flush=True)
                time.sleep(5)
                recorder.check_health()
                import mss
                with mss.mss() as screen:
                    screen.shot(output=str(args.output / "result.png"))
        finally:
            done.set()
            thread.join(timeout=3)
            (args.output / "resources.json").write_text(json.dumps({"baseline": baseline,
                "samples": samples, "end": resources()}, indent=2))
        print("RECORDING_FINISHED", flush=True)
        faulthandler.cancel_dump_traceback_later()
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        logfile.close()


if __name__ == "__main__":
    main()
