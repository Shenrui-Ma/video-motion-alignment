import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import r89_contract as c
import service


class OriginalR87Copy(unittest.TestCase):
    def test_original_snapshot_retains_its_seal(self):
        old = ROOT/'source_snapshot/r87_capacity'
        seal = c.read(old/'deploy_manifest.json')
        for p in (old/'configs').rglob('*'):
            if p.is_file():
                self.assertEqual(c.sha(p), seal['files'][str(p.relative_to(old))]['sha256'])

    def test_all14_graphs_preserve_r87_scientific_values(self):
        old = ROOT/'source_snapshot/r87_capacity'
        before = c.read(old/'configs/runtime.json')['remote_root']
        after = c.read(ROOT/'configs/runtime.json')['remote_root']
        cases = c.read(ROOT/'configs/scientific_contract.json')['cases']
        self.assertEqual(len(cases), 14)
        for case in cases:
            new = ROOT/'configs/graphs'/(case['run_id']+'.json')
            previous = old/'configs/graphs'/(case['run_id'].replace('r89_', 'r87_', 1)+'.json')
            normalized = json.loads(new.read_text().replace(after, before).replace('r89_', 'r87_'))
            self.assertEqual(normalized, c.read(previous))

    def test_capacity_choice_preserves_normal_device_policy(self):
        runtime = c.read(ROOT/'configs/runtime.json')
        self.assertEqual((runtime['expected_gpu_index'], runtime['port']), (0, 8554))
        self.assertEqual(runtime['memory_mode'], 'normal')
        command = service.command()
        self.assertNotIn('--lowvram', command)
        self.assertNotIn('--novram', command)
        self.assertEqual(command[command.index('--reserve-vram')+1], '8')
        self.assertIn("'--free-mib','29696'", (ROOT/'audit/root_run_batch.py').read_text())


if __name__ == '__main__': unittest.main()
