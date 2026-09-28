import unittest
from unittest.mock import Mock
from Xlib.error import BadWindow
from click_event import record_click


class ClickEventTests(unittest.TestCase):
    def setUp(self):
        self.target = Mock(return_value={'target': 'Close', 'target_source': 'accessibility'})
        self.title = Mock(return_value='Terminal')
        self.emit = Mock()

    def click(self):
        record_click(120, 80, 1, self.target, self.title, self.emit)

    def test_destroyed_window_keeps_click_and_next_click_still_records(self):
        # Xlib normally constructs this exception from a server error packet.
        self.title.side_effect = [BadWindow.__new__(BadWindow), 'Next window']
        self.click()
        self.click()
        self.assertEqual(self.emit.call_count, 2)
        first = self.emit.call_args_list[0].args
        self.assertEqual(first, ('ui.click', {'target': 'Close', 'target_source': 'accessibility',
                                            'x': 120, 'y': 80, 'button': 1, 'window': ''}))
        self.assertEqual(self.emit.call_args_list[1].args[1]['window'], 'Next window')

    def test_destroyed_target_and_title_preserve_coordinates(self):
        self.target.side_effect = BadWindow.__new__(BadWindow)
        self.title.side_effect = BadWindow.__new__(BadWindow)
        self.click()
        self.assertEqual(self.emit.call_args.args, ('ui.click', {
            'target': None, 'target_source': 'coordinates_only',
            'x': 120, 'y': 80, 'button': 1, 'window': ''}))

    def test_other_display_errors_are_not_hidden(self):
        self.title.side_effect = OSError('display disconnected')
        with self.assertRaises(OSError):
            self.click()
        self.emit.assert_not_called()

    def test_journal_failure_is_not_hidden(self):
        self.emit.side_effect = RuntimeError('journal unavailable')
        with self.assertRaises(RuntimeError):
            self.click()


if __name__ == '__main__':
    unittest.main()
