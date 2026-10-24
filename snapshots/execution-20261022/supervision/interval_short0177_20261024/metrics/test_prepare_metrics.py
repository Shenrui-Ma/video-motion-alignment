import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from prepare_metrics import validate_bindings


class BindingGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.config = json.loads(Path(__file__).with_name('config.json').read_text())
        self.gate = root / 'gate.json'
        self.gate.write_text('{"passed":true}')
        video = root / 'dummy.mp4'
        video.write_bytes(b'CPU-only binding test; never scored')
        self.sha = hashlib.sha256(video.read_bytes()).hexdigest()
        self.config['source_sha256'] = self.sha
        self.binding = {'task_id': 'short_0177', 'completion_gate': str(self.gate),
                        'videos': {method: {'file': str(video), 'sha256': self.sha}
                                   for method in self.config['methods']}}

    def test_exact_seven_verified_bindings(self):
        checked, gate = validate_bindings(self.binding, self.config, probe=False)
        self.assertEqual(len(checked), 7)
        self.assertEqual(len(gate['sha256']), 64)

    def test_missing_arm_rejected(self):
        del self.binding['videos']['late']
        with self.assertRaises(ValueError):
            validate_bindings(self.binding, self.config, probe=False)

    def test_unpassed_completion_gate_rejected(self):
        self.gate.write_text('{"passed":false}')
        with self.assertRaises(ValueError):
            validate_bindings(self.binding, self.config, probe=False)

    def test_changed_video_rejected(self):
        self.binding['videos']['fixed']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            validate_bindings(self.binding, self.config, probe=False)

    def test_wrong_source_rejected(self):
        self.config['source_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            validate_bindings(self.binding, self.config, probe=False)


if __name__ == '__main__':
    unittest.main()
