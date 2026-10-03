"""Read editable text only when an edit completes, never on each keystroke."""


class CompletedEdit:
    def __init__(self, describe, read, emit):
        self.describe, self.read, self.emit = describe, read, emit
        self.focused = self.details = self.last_value = None
        self.dirty = False

    def focus(self, accessible):
        try:
            self.flush()
        finally:
            # A destroyed old widget must not leave all later edits attached to it.
            self.focused = accessible
            self.dirty = False
            self.details = self.last_value = None
            self.details = self.describe(accessible)

    def changed(self, accessible):
        if self.details is not None and accessible == self.focused:
            self.dirty = True

    def flush(self):
        if not self.dirty:
            return
        self.dirty = False
        value = self.read(self.focused)
        if value is not None and value != self.last_value:
            self.emit('ui.change', {**self.details, 'value': value,
                                   'completion': 'focus_left_or_clicked'})
            self.last_value = value
