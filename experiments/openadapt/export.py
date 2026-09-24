"""Export a finished pilot using the recorder's verified public reader.

Derived files go outside the sealed capture directory. This does not infer
task success, user intent, shell execution, or missing accessibility fields.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    output = root / "export"
    output.mkdir(exist_ok=True)
    from openadapt_capture import CaptureSession
    with CaptureSession.load_verified(root / "capture") as capture:
        raw = capture.raw_events()
        actions = list(capture.actions())
        with (output / "raw-events.jsonl").open("w") as file:
            for event in raw:
                file.write(event.model_dump_json() + "\n")
        with (output / "actions.jsonl").open("w") as file:
            for index, action in enumerate(actions):
                event = action.event.model_dump(mode="json", exclude={"children"})
                event["derived_action_index"] = index
                event["text"] = action.text
                event["keys"] = action.keys
                file.write(json.dumps(event, ensure_ascii=False) + "\n")
        selected = next((a for a in actions if a.type == "mouse.singleclick"), actions[0] if actions else None)
        if selected is not None:
            frame = selected.screenshot
            if frame is not None:
                frame.save(output / "action-before.png")
        structural = [a.structural_observation for a in actions if a.structural_observation]
        summary = {
            "provenance": "Automated XTest input against real applications in isolated Kali; not human/student activity",
            "integrity_verified": True,
            "platform": capture.platform,
            "screen_size": capture.screen_size,
            "duration_seconds": capture.duration,
            "raw_event_count": len(raw),
            "processed_action_count": len(actions),
            "action_types": dict(Counter(a.type for a in actions)),
            "structural_action_count": len(structural),
            "structural_examples": [s.model_dump(mode="json") for s in structural[:3]],
            "text_sequences": [a.text for a in actions if a.text],
        }
        if capture.video_path:
            video = Path(capture.video_path)
            summary["video_bytes"] = video.stat().st_size
            summary["video_probe"] = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,nb_frames:format=duration",
                "-of", "json", str(video)], text=True))
    conn = sqlite3.connect((root / "capture/recording.db").as_uri() + "?mode=ro", uri=True)
    summary["sqlite_integrity"] = conn.execute("pragma integrity_check").fetchone()[0]
    summary["row_counts"] = {table: conn.execute(f"select count(*) from {table}").fetchone()[0]
                             for table in ("action_event", "screenshot", "window_event", "browser_event")}
    conn.close()
    metrics = json.loads((root / "resources.json").read_text())
    samples = [metrics["baseline"], *metrics["samples"], metrics["end"]]
    elapsed = samples[-1]["timestamp"] - samples[0]["timestamp"]
    cpu_seconds = (samples[-1]["cpu_usage_usec"] - samples[0]["cpu_usage_usec"]) / 1e6
    summary["container_resources"] = {
        "measurement_seconds": elapsed,
        "average_cpu_percent_one_core": 100 * cpu_seconds / elapsed,
        "baseline_memory_mib": samples[0]["memory_bytes"] / 1024**2,
        "peak_sampled_memory_mib": max(s["memory_bytes"] for s in samples) / 1024**2,
        "peak_sampled_pids": max(s["pids"] for s in samples),
        "scope": "whole container including desktop, application, recorder, startup/finalization and filesystem cache",
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "structural_examples"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
