#!/usr/bin/python3
"""Click targets and completed accessible edits. Never subscribes to keys/motion."""
import ctypes
import os
import queue
import signal
import threading
import time
import traceback
import uuid

import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, GLib
from Xlib import X, display
from Xlib.ext import record
from Xlib.protocol import rq

from agent import request
from click_event import record_click
from edit_event import CompletedEdit

# A killed supervisor must not leave this observer running.
parent = os.getppid()
ctypes.CDLL(None).prctl(1, signal.SIGTERM)
if parent == 1 or os.getppid() != parent:
    raise SystemExit('collector parent gone')

Atspi.init()
Atspi.set_timeout(300, 600)
clicks = queue.Queue(maxsize=32)
failed = False
control = display.Display()
connection = display.Display()
root = control.screen().root


def report_failure():
    global failed
    if not failed:
        traceback.print_exc()
    failed = True


def emit(kind, data):
    request({'id': str(uuid.uuid4()), 'source': 'desktop', 'type': kind, 'data': data})


def info(accessible):
    return {'target': accessible.get_name()[:512], 'role': accessible.get_role_name(),
            'app': accessible.get_application().get_name()[:256], 'target_source': 'accessibility'}


def text(accessible):
    states = accessible.get_state_set()
    if accessible.get_role() == Atspi.Role.PASSWORD_TEXT:
        return '[隐藏]'
    if not states.contains(Atspi.StateType.EDITABLE):
        return None
    interface = accessible.get_text_iface()
    if interface is None:
        return None
    count = interface.get_character_count()
    if count > 8192:
        raise ValueError('控件文本超出记录上限')
    return Atspi.Text.get_text(interface, 0, count)


def describe_edit(accessible):
    # Terminal output is not an edit; Firefox fields belong to the DOM adapter.
    # Decide while the widget is alive, avoiding lookups after its app closes.
    if not accessible.get_state_set().contains(Atspi.StateType.EDITABLE):
        return None
    details = info(accessible)
    return None if 'firefox' in details['app'].lower() else details


edits = CompletedEdit(describe_edit, text, emit)


def on_event(event):
    try:
        if event.type.startswith('object:state-changed:focused') and event.detail1:
            edits.focus(event.source)
        elif event.type.startswith('object:text-changed'):
            edits.changed(event.source)
    except Exception:
        # Accessibility failures are reported as partial coverage, never guessed.
        report_failure()


listener = Atspi.EventListener.new(on_event)
listener.register('object:state-changed:focused')
listener.register('object:text-changed')


def window_title():
    prop = root.get_full_property(control.intern_atom('_NET_ACTIVE_WINDOW'), X.AnyPropertyType)
    if prop is None or not len(prop.value):
        return ''
    win = control.create_resource_object('window', int(prop.value[0]))
    title = win.get_full_property(control.intern_atom('_NET_WM_NAME'), control.intern_atom('UTF8_STRING'))
    return title.value.decode(errors='replace')[:512] if title else (win.get_wm_name() or '')[:512]


def target_at(x, y):
    desktop = Atspi.get_desktop(0)
    active = root.get_full_property(control.intern_atom('_NET_ACTIVE_WINDOW'), X.AnyPropertyType)
    active_pid = None
    if active is not None and len(active.value):
        window = control.create_resource_object('window', int(active.value[0]))
        prop = window.get_full_property(control.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
        active_pid = int(prop.value[0]) if prop is not None and len(prop.value) else None
    deadline = time.monotonic() + 1
    best = None
    visited = 0
    # Some Java wrappers expose -1 bounds for the top-level frame. Search its
    # bounded visible subtree instead of treating that as an off-screen app.
    for app_index in range(min(desktop.get_child_count(), 64)):
        app = desktop.get_child_at_index(app_index)
        if active_pid and app.get_process_id() != active_pid:
            continue
        # Prefer the toolkit's hit test: traversing every sibling costs several
        # D-Bus round trips per widget and can exhaust the budget before reaching
        # the clicked button on a small VM. Bounds keep other windows excluded.
        for index in range(min(app.get_child_count(), 64)):
            item = app.get_child_at_index(index)
            seen = set()
            depth = 0
            while item is not None and depth < 16 and time.monotonic() < deadline:
                marker = hash(item)
                if marker in seen:
                    break
                seen.add(marker)
                component = item.get_component_iface()
                if not component:
                    break
                box = component.get_extents(Atspi.CoordType.SCREEN)
                if not (box.width > 0 and box.height > 0 and
                        box.x <= x < box.x + box.width and box.y <= y < box.y + box.height):
                    break
                candidate = info(item)
                if candidate['target'] and (best is None or depth > best[0]):
                    best = (depth, candidate)
                item = component.get_accessible_at_point(x, y, Atspi.CoordType.SCREEN)
                depth += 1
        if best and best[1]['role'] not in ('frame', 'window', 'panel', 'application'):
            return best[1]
        stack = [(app, 0)]
        while stack and visited < 192 and time.monotonic() < deadline:
            item, depth = stack.pop()
            visited += 1
            component = item.get_component_iface()
            if component:
                box = component.get_extents(Atspi.CoordType.SCREEN)
                if box.width > 0 and box.height > 0:
                    if not (box.x <= x < box.x + box.width and box.y <= y < box.y + box.height):
                        continue
                    candidate = info(item)
                    if candidate['target'] and (best is None or depth > best[0]):
                        best = (depth, candidate)
            if depth < 16:
                for index in range(min(item.get_child_count(), 64)):
                    child = item.get_child_at_index(index)
                    if child is not None:
                        stack.append((child, depth + 1))
    return best[1] if best else {'target': None, 'target_source': 'coordinates_only'}


def poll():
    global failed
    try:
        for _ in range(8):
            try:
                x, y, button = clicks.get_nowait()
            except queue.Empty:
                break
            edits.flush()
            record_click(x, y, button, target_at, window_title, emit)
    except Exception:
        report_failure()
    return True


def heartbeat():
    request({'control': 'provider', 'source': 'desktop', 'status': 'partial' if failed else 'ready'})
    if not reader.is_alive():
        raise SystemExit('mouse observer exited')
    return True


def callback(reply):
    global failed
    if reply.category != record.FromServer or reply.client_swapped:
        return
    data = reply.data
    while data:
        event, data = rq.EventField(None).parse_binary_value(data, connection.display, None, None)
        if event.type == X.ButtonRelease and event.detail in (1, 2, 3):
            try:
                clicks.put_nowait((event.root_x, event.root_y, event.detail))
            except queue.Full:
                failed = True


context = control.record_create_context(0, [record.AllClients], [{'core_requests': (0, 0), 'core_replies': (0, 0), 'ext_requests': (0, 0, 0, 0), 'ext_replies': (0, 0, 0, 0), 'delivered_events': (0, 0), 'device_events': (X.ButtonRelease, X.ButtonRelease), 'errors': (0, 0), 'client_started': False, 'client_died': False}])
control.sync()
reader = threading.Thread(target=connection.record_enable_context, args=(context, callback), daemon=True)
reader.start()
request({'control': 'provider', 'source': 'desktop', 'status': 'ready'})
GLib.timeout_add(50, poll)
GLib.timeout_add_seconds(3, heartbeat)
GLib.MainLoop().run()
