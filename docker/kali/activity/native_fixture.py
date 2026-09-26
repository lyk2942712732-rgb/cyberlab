"""Disposable GTK test window using installed native libraries, no extra packages."""
import ctypes as c

gtk = c.CDLL('libgtk-3.so.0')
gdk = c.CDLL('libgdk-3.so.0')
atk = c.CDLL('libatk-1.0.so.0')
gobject = c.CDLL('libgobject-2.0.so.0')
pointer = c.c_void_p


def bind(lib, name, result, *args):
    fn = getattr(lib, name); fn.restype = result; fn.argtypes = list(args)
    return fn


bind(gtk, 'gtk_init', None, pointer, pointer)(None, None)
window = bind(gtk, 'gtk_window_new', pointer, c.c_int)(0)
bind(gtk, 'gtk_window_set_title', None, pointer, c.c_char_p)(window, b'CyberLab Native QA')
bind(gtk, 'gtk_window_set_default_size', None, pointer, c.c_int, c.c_int)(window, 500, 200)
box = bind(gtk, 'gtk_box_new', pointer, c.c_int, c.c_int)(1, 20)
bind(gtk, 'gtk_container_set_border_width', None, pointer, c.c_uint)(box, 20)
bind(gtk, 'gtk_container_add', None, pointer, pointer)(window, box)
entry = bind(gtk, 'gtk_entry_new', pointer)()
accessible = bind(gtk, 'gtk_widget_get_accessible', pointer, pointer)(entry)
bind(atk, 'atk_object_set_name', None, pointer, c.c_char_p)(accessible, '实验答案'.encode())
pack = bind(gtk, 'gtk_box_pack_start', None, pointer, pointer, c.c_int, c.c_int, c.c_uint)
pack(box, entry, 0, 0, 0)
button = bind(gtk, 'gtk_button_new_with_label', pointer, c.c_char_p)('保存答案'.encode())
pack(box, button, 0, 0, 0)
callback_type = c.CFUNCTYPE(None, pointer, pointer)
clicked = callback_type(lambda *_: gtk.gtk_window_set_title(window, b'CyberLab Native QA Saved'))
destroyed = callback_type(lambda *_: gtk.gtk_main_quit())
connect = bind(gobject, 'g_signal_connect_data', c.c_ulong, pointer, c.c_char_p, callback_type, pointer, pointer, c.c_int)
connect(button, b'clicked', clicked, None, None, 0)
connect(window, b'destroy', destroyed, None, None, 0)
atom = bind(gdk, 'gdk_atom_intern_static_string', pointer, c.c_char_p)(b'CLIPBOARD')
clipboard = bind(gtk, 'gtk_clipboard_get', pointer, pointer)(atom)
bind(gtk, 'gtk_clipboard_set_text', None, pointer, c.c_char_p, c.c_int)(clipboard, '中文粘贴_FINAL'.encode(), -1)
bind(gtk, 'gtk_widget_show_all', None, pointer)(window)
gtk.gtk_main()
