import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_operator as run


class RootGateTest(unittest.TestCase):
    def exchange(self, change):
        with tempfile.TemporaryDirectory() as folder:
            control = Path(folder) / 'gate'
            ident = {'pid': 1, 'uid': 1000, 'start_ticks': '123', 'cmdline_sha256': 'abc'}
            config = {'input_sha256': {'inputs/x0_step006.pt': 'x0', 'inputs/OFFLINE_DEVELOPMENT_MAPPING.json': 'phi'},
                      'required_free_mib': 16384}
            def authorize():
                for _ in range(200):
                    if (control / 'ready.json').exists():
                        ready = json.loads((control / 'ready.json').read_text())
                        if change:
                            ready['identity']['start_ticks'] = 'different'
                        run.write(control / 'go.json', ready)
                        return
                    time.sleep(.005)
                raise TimeoutError('test ready missing')
            thread = threading.Thread(target=authorize)
            thread.start()
            try:
                with patch.object(run, 'process_identity', return_value=ident):
                    return run.root_gate(control, 'GPU-test', config, Path(folder) / 'out')
            finally:
                thread.join()

    def test_matching_identity_and_inputs(self):
        result = self.exchange(False)
        self.assertFalse(result['CUDA_started'])
        self.assertEqual(result['input_snapshot_sha256'], 'x0')

    def test_replayed_process_generation_rejected(self):
        with self.assertRaisesRegex(ValueError, 'root exact ready/go binding'):
            self.exchange(True)


if __name__ == '__main__':
    unittest.main()
