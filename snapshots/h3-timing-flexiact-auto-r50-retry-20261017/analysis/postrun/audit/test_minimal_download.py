import unittest
from minimal_download import original_selected, derived_selected


class MinimalDownloadTests(unittest.TestCase):
    def test_tensors_stay_remote(self):
        for name in ['audit/x0/run/x0_step000.pt', 'final/run/anything.pt', 'output/a.pt']:
            self.assertFalse(original_selected(name))
            self.assertFalse(derived_selected(name))

    def test_source_and_parent_assets_stay_remote(self):
        for name in ['inputs/source.mp4', 'input/source.mp4', 'configs/parents/source/source.pose.json']:
            self.assertFalse(original_selected(name))
        self.assertFalse(derived_selected('final/run/source_score.mp4'))

    def test_step_media_and_raw_observer_stay_remote(self):
        for name in ['audit/observations/step001/observer.json', 'audit/observations/step001/native.mp4',
                     'audit/counterfactual/run.json']:
            self.assertFalse(original_selected(name))

    def test_final_media_and_proofs_remain_local(self):
        self.assertTrue(original_selected('output/run_00001_.mp4'))
        for name in ['final/run/edited_score.mp4', 'final/run/DECISION_LEDGER.json',
                     'final/run/METRIC_INPUTS.json', 'CASE_RUNTIME_GATE.json']:
            self.assertTrue(derived_selected(name))


if __name__ == '__main__':
    unittest.main()
