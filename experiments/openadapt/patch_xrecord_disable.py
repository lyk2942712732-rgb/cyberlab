"""Flush the RECORD disable request before draining its other X11 connection."""
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
old = '''            if disabled:
                attempt(
                    "while draining the X RECORD shutdown tail",
                    self._drain_record_tail,
                )
'''
new = '''            if disabled:
                # Control and data are distinct X11 connections. Ensure the
                # server processed DisableContext before looking for EndOfData.
                attempt(
                    "while synchronizing the X RECORD disable request",
                    lambda: self._x11.XSync(self._control_display, False),
                )
                attempt(
                    "while draining the X RECORD shutdown tail",
                    self._drain_record_tail,
                )
'''
if source.count(old) != 1:
    raise SystemExit("Pinned XRecord disable source differs; patch refused")
path.write_text(source.replace(old, new))
print("Applied xrecord-disable-sync-v1")
