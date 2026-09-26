"""Run on Linux: python3 -m unittest discover -s docker/kali/activity."""
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from agent import Journal, validate


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.journal = Journal(self.root, str(uuid.uuid4()), 1, 1024 * 1024)

    def tearDown(self):
        self.journal.close(True)
        self.temp.cleanup()

    def event(self, command='echo 中文'):
        return {'id': str(uuid.uuid4()), 'source': 'shell', 'type': 'terminal.submit', 'data': {'command': command}}

    def test_final_text_survives_and_retry_is_idempotent(self):
        event = self.event('printf "粘贴文本\\n"\nprintf done')
        seq = self.journal.accept(event)
        self.assertEqual(self.journal.accept(event), seq)
        row = self.journal.db.execute('SELECT data FROM events').fetchone()
        self.assertEqual(json.loads(row[0]), event['data'])
        self.assertEqual(self.journal.state['events'], 1)

    def test_two_actual_submissions_are_not_deduplicated(self):
        self.journal.accept(self.event())
        self.journal.accept(self.event())
        self.assertEqual(self.journal.state['events'], 2)

    def test_oversize_event_and_wrong_source_rejected(self):
        with self.assertRaises(ValueError):
            self.journal.accept(self.event('a' * 20000))
        event = self.event(); event['source'] = 'browser'
        with self.assertRaises(ValueError):
            validate(event)
        self.assertEqual(self.journal.state['events'], 0)

    def test_browser_native_clicks_merge_in_either_delivery_order(self):
        for order in ((0, 1), (1, 0)):
            native = {'id': str(uuid.uuid4()), 'source': 'desktop', 'type': 'ui.click', 'data': {'app': 'Firefox', 'x': order[0] + 10, 'y': 20, 'button': 1}}
            web = {'id': str(uuid.uuid4()), 'source': 'browser', 'type': 'web.click', 'data': {'target': {'label': '发送'}, 'x': order[0] + 10, 'y': 20, 'button': 0}}
            pair = (native, web)
            first = self.journal.accept(pair[order[0]])
            self.assertEqual(self.journal.accept(pair[order[1]]), first)
            self.assertEqual(self.journal.accept(pair[order[1]]), first)
            row = self.journal.db.execute('SELECT type,data FROM events WHERE seq=?', (first,)).fetchone()
            self.assertEqual(row[0], 'web.click')
            self.assertEqual(json.loads(row[1])['target']['label'], '发送')
        self.assertEqual(self.journal.state['events'], 2)

    def test_quota_stops_accepting_without_losing_committed_events(self):
        self.journal.accept(self.event('first'))
        self.journal.max_bytes = 1
        with self.assertRaises(RuntimeError):
            self.journal.accept(self.event('second'))
        self.assertEqual(self.journal.db.execute('SELECT count(*) FROM events').fetchone()[0], 1)

    def test_provider_recovery_and_shutdown_do_not_hide_coverage_gap(self):
        self.journal.provider('browser', 'partial')
        self.journal.provider('browser', 'ready')
        self.journal.provider('browser', 'idle')
        self.assertEqual(self.journal.state['providers']['browser']['status'], 'partial')
        with self.assertRaises(ValueError):
            self.journal.provider('browser', 'unknown')


if __name__ == '__main__':
    unittest.main()
