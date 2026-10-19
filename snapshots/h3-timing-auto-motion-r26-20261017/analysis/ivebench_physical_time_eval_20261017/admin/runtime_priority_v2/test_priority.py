import tempfile
from pathlib import Path
import unittest
from run_phase import pending_observer


class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def request(self, name):
        folder = self.root / 'audit/observations' / name
        folder.mkdir(parents=True)
        (folder / 'request.json').write_text('{}')
        return folder

    def test_completed_bootstrap_does_not_block(self):
        folder = self.request('known_endpoint_90')
        (folder / 'native.mp4').touch()
        self.assertFalse(pending_observer(self.root))

    def test_decoder_without_video_does_not_take_pose_lock(self):
        self.request('step000_case')
        self.assertFalse(pending_observer(self.root))

    def test_actual_pending_pose_has_priority(self):
        folder = self.request('step000_case')
        (folder / 'native.mp4').touch()
        self.assertTrue(pending_observer(self.root))

    def test_terminal_observations_do_not_block(self):
        for name, receipt in [('step001_case', 'response.json'), ('step002_case', 'failure.json')]:
            folder = self.request(name)
            (folder / 'native.mp4').touch()
            (folder / receipt).write_text('{}')
        self.assertFalse(pending_observer(self.root))


if __name__ == '__main__':
    unittest.main()
