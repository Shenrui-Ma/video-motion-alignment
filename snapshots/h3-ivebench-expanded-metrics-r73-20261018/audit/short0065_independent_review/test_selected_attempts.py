import copy
import tempfile
import unittest
from pathlib import Path
import json
import build_selected_attempts as build


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.value = {'pair_id': 'short_0065', 'method': 'native', 'device': 'cpu',
                      'cuda_initialized': False, 'motion_fidelity': .8}
        for kind, role, attempt in [('source', 'source', 1), ('target', 'native', 2)]:
            relative = f'tracks/{role}/short_0065/attempt{attempt}/REPORT.json'
            p = self.root / relative; p.parent.mkdir(parents=True); p.write_text('{"passed":true}')
            self.value[kind + '_report'] = {'file': '/remote/' + relative, 'sha256': build.sha(p)}
        self.path = self.root / 'results/short_0065/native_source1_target2.json'
        self.path.parent.mkdir(parents=True); self.commit()

    def commit(self):
        self.path.write_text(json.dumps(self.value))
        self.selection = {'source_attempt': 1, 'target_attempt': 2, 'score_sha256': build.sha(self.path)}

    def run_score(self):
        return build.selected_score(self.root, 'short_0065', 'native', self.selection)

    def test_real_attempt2(self):
        self.assertEqual(self.run_score(), .8)

    def test_wrong_attempt_path_rejected(self):
        self.value['target_report']['file'] = self.value['target_report']['file'].replace('attempt2', 'attempt1')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'attempt differs'): self.run_score()

    def test_failed_tracker_rejected(self):
        p = self.root / 'tracks/native/short_0065/attempt2/REPORT.json'; p.write_text('{"passed":false}')
        self.value['target_report']['sha256'] = build.sha(p); self.commit()
        with self.assertRaisesRegex(ValueError, 'did not pass'): self.run_score()

    def test_changed_score_rejected(self):
        self.path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'score changed'): self.run_score()


if __name__ == '__main__': unittest.main()
