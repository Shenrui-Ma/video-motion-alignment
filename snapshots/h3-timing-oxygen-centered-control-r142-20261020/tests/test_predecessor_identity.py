import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('predecessor_identity', ROOT / 'scripts/predecessor.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProcessGenerationTests(unittest.TestCase):
    def setUp(self):
        self.saved = {'uid': 1016, 'start_ticks': '2649851739', 'cmdline': 'owned service'}

    def test_absent_process(self):
        self.assertFalse(module.same_generation(self.saved, None))

    def test_original_process_alive(self):
        self.assertTrue(module.same_generation(self.saved, dict(self.saved)))

    def test_reused_pid_other_owner(self):
        self.assertFalse(module.same_generation(self.saved, {'uid': 1025, 'start_ticks': '2650348172'}))

    def test_reused_pid_same_owner(self):
        self.assertFalse(module.same_generation(self.saved, {'uid': 1016, 'start_ticks': '2650348172'}))

    def test_changed_command_same_process_still_alive(self):
        self.assertTrue(module.same_generation(self.saved, {**self.saved, 'cmdline': 'exec replacement'}))


if __name__ == '__main__':
    unittest.main()
