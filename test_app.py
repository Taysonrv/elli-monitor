import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.test-', dir=Path(__file__).resolve().parent)
        self.root = patch.object(app, 'ROOT', Path(self.temp.name))
        self.root.start()

    def tearDown(self):
        self.root.stop()
        self.temp.cleanup()

    def test_reimport_updates_without_duplicate_alert(self):
        app.ingest({'records': [{'source': 'shop', 'id': '1', 'revenue': 10}]})
        app.ingest({'records': [{'source': 'shop', 'id': '1', 'revenue': 20}]})
        self.assertEqual(len(app.read('state.json', {})['alerts']), 1)
        self.assertEqual(app.read('data.json', {})['records'][0]['revenue'], 20)

    def test_failed_delivery_keeps_queue(self):
        app.save('config.json', {'telegram_enabled': True})
        app.ingest({'records': [{'source': 'affiliate', 'id': 'a', 'commission': 5}]})
        with patch.object(app, 'telegram', side_effect=ValueError('offline')):
            with self.assertRaises(ValueError):
                app.flush()
        self.assertEqual(len(app.read('state.json', {})['pending']), 1)
        with patch.object(app, 'telegram') as send:
            app.flush()
            send.assert_called_once()
        self.assertEqual(app.read('state.json', {})['pending'], [])

    def test_invalid_import_does_not_write_data(self):
        with self.assertRaises(ValueError):
            app.ingest({'records': [{'source': 'shop', 'id': 'x', 'revenue': -1}]})
        self.assertFalse((app.ROOT / 'data.json').exists())


if __name__ == '__main__':
    unittest.main()
