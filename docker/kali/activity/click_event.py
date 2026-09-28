"""Keep the click even when its window disappears during metadata lookup."""
from Xlib.error import BadWindow


def record_click(x, y, button, read_target, read_title, emit):
    details = {'target': None, 'target_source': 'coordinates_only'}
    try:
        details = read_target(x, y)
    except Exception:
        # Missing accessibility metadata must not discard the physical click.
        pass
    try:
        title = read_title()
    except BadWindow:
        # Closing a window/menu can invalidate its XID between the two reads.
        # Keep coordinates and any target already resolved; do not flag loss.
        title = ''
    emit('ui.click', {**details, 'x': x, 'y': y, 'button': button, 'window': title})
