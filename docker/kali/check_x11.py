"""Require a window manager, XFCE desktop and panel, not just a VNC socket."""
import ctypes
from ctypes import c_char_p, c_int, c_long, c_ulong, c_void_p, POINTER


def check_shell_ready(require_shell=True, settings_only=False):
    x11 = ctypes.CDLL("libX11.so.6")
    x11.XOpenDisplay.argtypes = [c_char_p]
    x11.XOpenDisplay.restype = c_void_p
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XInternAtom.argtypes = [c_void_p, c_char_p, c_int]
    x11.XInternAtom.restype = c_ulong
    x11.XGetSelectionOwner.argtypes = [c_void_p, c_ulong]
    x11.XGetSelectionOwner.restype = c_ulong
    x11.XGetWindowProperty.argtypes = [c_void_p, c_ulong, c_ulong, c_long, c_long,
                                     c_int, c_ulong, POINTER(c_ulong), POINTER(c_int),
                                     POINTER(c_ulong), POINTER(c_ulong), POINTER(c_void_p)]
    x11.XFree.argtypes = [c_void_p]
    x11.XCloseDisplay.argtypes = [c_void_p]
    display = x11.XOpenDisplay(None)
    if not display:
        raise OSError("X display is not ready")
    try:
        def atom(name):
            return x11.XInternAtom(display, name.encode(), 0)

        def property_values(window, name):
            kind, count, remaining = c_ulong(), c_ulong(), c_ulong()
            fmt, data = c_int(), c_void_p()
            result = x11.XGetWindowProperty(display, window, atom(name), 0, 4096, 0, 0,
                                           ctypes.byref(kind), ctypes.byref(fmt),
                                           ctypes.byref(count), ctypes.byref(remaining),
                                           ctypes.byref(data))
            try:
                if result or fmt.value != 32 or not data:
                    return []
                return list(ctypes.cast(data, POINTER(c_ulong))[:count.value])
            finally:
                if data:
                    x11.XFree(data)

        root = x11.XDefaultRootWindow(display)
        if settings_only:
            if not x11.XGetSelectionOwner(display, atom('_XSETTINGS_S0')):
                raise OSError('XFCE settings are still starting')
            return
        if not property_values(root, "_NET_SUPPORTING_WM_CHECK"):
            raise OSError("Desktop window manager is still starting")
        if not require_shell:
            return
        types = set()
        for window in property_values(root, "_NET_CLIENT_LIST"):
            types.update(property_values(window, "_NET_WM_WINDOW_TYPE"))
        require_shell_windows(types, atom("_NET_WM_WINDOW_TYPE_DESKTOP"),
                              atom("_NET_WM_WINDOW_TYPE_DOCK"))
    finally:
        x11.XCloseDisplay(display)


def require_shell_windows(types, desktop, panel):
    if not {desktop, panel}.issubset(types):
        raise OSError("XFCE desktop and panel are still starting")
