"""Patch the pinned upstream XRecord cross-connection creation race.

CreateContext queues a request on the control Display; EnableContextAsync uses
a different Display. XSync ensures the context exists server-side first.
Fail closed if the pinned source differs; do not apply by fuzzy matching.
"""

from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
old = "        self._record_context = int(context)\n        self._record_callback = _XRecordInterceptProc(self._record_intercept)"
new = """        self._record_context = int(context)
        # CyberLab pilot patch: creation and enable use different connections.
        self._x11.XSync(self._control_display, False)
        self._record_callback = _XRecordInterceptProc(self._record_intercept)"""
api_old = "        self._x11.XCloseDisplay.restype = ctypes.c_int\n"
api_new = api_old + "        self._x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]\n        self._x11.XSync.restype = ctypes.c_int\n"
if source.count(old) != 1 or source.count(api_old) != 1:
    raise SystemExit("Pinned XRecord source differs; patch refused")
path.write_text(source.replace(old, new).replace(api_old, api_new))
print("Applied xrecord-create-sync-v1")
