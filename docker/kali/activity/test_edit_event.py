import unittest
from unittest.mock import Mock
from edit_event import CompletedEdit


class CompletedEditTests(unittest.TestCase):
    def test_excluded_widgets_do_not_read_text_even_after_close(self):
        read = Mock(side_effect=RuntimeError('application no longer exists'))
        emit = Mock()
        tracker = CompletedEdit(lambda _: None, read, emit)
        tracker.focus('terminal-output-or-browser')
        tracker.changed('terminal-output-or-browser')
        tracker.focus('next-window')
        read.assert_not_called()
        emit.assert_not_called()

    def test_only_completed_value_is_read_and_saved(self):
        read, emit = Mock(return_value='final value'), Mock()
        tracker = CompletedEdit(lambda _: {'target': 'Answer'}, read, emit)
        tracker.focus('input')
        for _ in range(5):
            tracker.changed('input')
        read.assert_not_called()
        tracker.flush()
        tracker.changed('input')
        tracker.flush()
        emit.assert_called_once_with('ui.change', {'target': 'Answer', 'value': 'final value',
                                                 'completion': 'focus_left_or_clicked'})

    def test_destroyed_edit_is_reported_but_next_edit_still_records(self):
        read = Mock(side_effect=[RuntimeError('application no longer exists'), 'next value'])
        emit = Mock()
        tracker = CompletedEdit(lambda widget: {'target': widget}, read, emit)
        tracker.focus('old')
        tracker.changed('old')
        with self.assertRaises(RuntimeError):
            tracker.focus('new')
        tracker.changed('new')
        tracker.flush()
        self.assertEqual(emit.call_args.args[1]['target'], 'new')
        self.assertEqual(emit.call_args.args[1]['value'], 'next value')
