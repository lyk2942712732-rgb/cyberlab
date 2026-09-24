"""Avoid TigerVNC blocking forever inside XCloseDisplay on the RECORD data link.

The recorder runs in its own short-lived process. After disabling/draining and
freeing the context, let process exit close this one data socket instead of
blocking its mandatory integrity finalization inside Xlib.
"""
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
old = '''        if self._data_display and self._x11 is not None:
            attempt(
                "while closing the X RECORD data display",
                lambda: self._x11.XCloseDisplay(self._data_display),
            )
'''
new = '''        if self._data_display and self._x11 is not None:
            # CyberLab/TigerVNC: this RECORD data connection can block forever
            # in XCloseDisplay even after EndOfData. The dedicated recorder
            # process closes its remaining socket on exit after finalization.
            pass
'''
if source.count(old) != 1:
    raise SystemExit("Pinned XRecord close source differs; patch refused")
path.write_text(source.replace(old, new))
print("Applied xrecord-data-close-v1")
