import base64
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import narration


class NarrationTests(unittest.TestCase):
    def test_invalid_text(self):
        for text in (None, '', 'a' * 701):
            with self.assertRaises(ValueError):
                narration.synthesize(text)

    @patch.object(narration.os, 'name', 'nt')
    def test_voice_is_validated_and_text_is_not_code(self):
        wav = b'RIFF' + b'0' * 50
        output = SimpleNamespace(stdout=base64.b64encode(wav).decode(), returncode=0)
        with patch.object(narration.subprocess, 'run', return_value=output) as run:
            self.assertEqual(base64.b64decode(narration.synthesize('Produto; $(teste)')['audio']), wav)
            self.assertNotIn('$(teste)', ' '.join(run.call_args.args[0]))

    @patch.object(narration.os, 'name', 'nt')
    def test_missing_portuguese_voice(self):
        with patch.object(narration.subprocess, 'run', return_value=SimpleNamespace(stdout='NO_PT_VOICE', returncode=2)):
            with self.assertRaisesRegex(ValueError, 'português'):
                narration.synthesize('Texto')

    @patch.object(narration.os, 'name', 'nt')
    def test_timeout_releases_lock(self):
        with patch.object(narration.subprocess, 'run', side_effect=subprocess.TimeoutExpired('powershell', 60)):
            with self.assertRaises(ValueError):
                narration.synthesize('Texto')
        self.assertFalse(narration.BUSY.locked())


if __name__ == '__main__':
    unittest.main()
