import copy
import json
from pathlib import Path
import unittest
import reuse_flex_score as reuse

HERE = Path(__file__).resolve().parent

class IdentityBinding(unittest.TestCase):
    def setUp(self):
        self.proof = json.loads((HERE / 'media_identity/chest/edited49.json').read_text())
        p = HERE.parent / 'completed_cases/r50_source_chest_seed2026101701_auto/final/r50_source_chest_seed2026101701_auto/METRIC_INPUTS.json'
        self.auto = json.loads(p.read_text())
        self.native = copy.deepcopy(self.auto)
        self.native['edited49'] = self.proof['left']['file']
        self.native['edited49_sha256'] = self.proof['left']['sha256']

    def check(self):
        reuse.compatible(self.auto, self.native, self.proof, 'edited49')

    def test_valid(self): self.check()
    def test_changed_source(self):
        self.auto['original_source_sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.check()
    def test_changed_frame_mapping(self):
        self.auto['full_output_indices'][2] = 5
        with self.assertRaises(ValueError): self.check()
    def test_changed_reader(self):
        self.proof['runtime_freeze_sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.check()
    def test_changed_frame(self):
        self.proof['comparison']['frames'][1]['right_rgb_sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.check()
    def test_changed_pts(self):
        self.proof['metadata']['right']['timestamps_seconds'][2] += .01
        with self.assertRaises(ValueError): self.check()
    def test_wrong_target(self):
        self.proof['right']['file'] += '.other'
        with self.assertRaises(ValueError): self.check()

if __name__ == '__main__': unittest.main()
