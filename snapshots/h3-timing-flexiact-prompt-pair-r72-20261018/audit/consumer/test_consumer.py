"""CPU-only contract tests with temporary synthetic records, never real outputs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from common import *
from presentation import filters

def gate_fixture(pair=PAIRS[0]):
    checks = {k: True for k in ('producer_seal', 'actual_runtime_device', 'input_video_equal', 'native_vae_calls_equal', 'qwen_presentation_equal', 'target_latent_shapes_equal', 'actual_initial_AV_noise_equal', 'independent_prompt_conditioning')}
    runs = {a: {'run_id': run_id(pair, a), 'valid_frames': 147, 'NFE': 20, 'Euler_updates': 20, 'routed_blocks': 0, 'evaluation_crop_xywh': [0, 0, 1152, 768], 'evaluation_indices': list(range(0, 147, 3)), 'evaluation_fps': 8, 'video': {'properties': {'width': 1152, 'height': 768, 'nb_read_frames': '158', 'avg_frame_rate': '24/1'}}} for a in ARMS}
    return {'schema': 'r72-paired-runtime-gate-v1', 'passed': True, 'source_id': pair, 'prompt_versions': ['P0', 'P1'], 'checks': checks, 'runs': runs}

class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'logs').mkdir()
    def tearDown(self):
        self.temp.cleanup()
    def completed(self, arm):
        run = run_id(PAIRS[0], arm)
        save(self.root / 'logs' / (run + '_job.json'), {'status': 'success'})
        save(self.root / 'logs' / (run + '_history.json'), {'status': {'status_str': 'success', 'completed': True}})
    def test_empty_pending(self):
        self.assertEqual(readiness(self.root, PAIRS[0]), 'PENDING')
    def test_one_arm_not_ready(self):
        self.completed('p0')
        self.assertEqual(readiness(self.root, PAIRS[0]), 'PENDING')
    def test_partial_json_pending(self):
        (self.root / 'logs' / (run_id(PAIRS[0], 'p0') + '_job.json')).write_text('{')
        self.assertEqual(readiness(self.root, PAIRS[0]), 'PENDING_WRITING')
    def test_actual_failure_retained(self):
        save(self.root / 'logs' / (run_id(PAIRS[0], 'p0') + '_job.json'), {'status': 'error'})
        self.assertEqual(readiness(self.root, PAIRS[0]), 'PRODUCER_FAILED')
    def test_success_without_history_pending(self):
        save(self.root / 'logs' / (run_id(PAIRS[0], 'p0') + '_job.json'), {'status': 'success'})
        self.assertEqual(readiness(self.root, PAIRS[0]), 'PENDING')
    def test_complete_needs_real_gate(self):
        for arm in ARMS: self.completed(arm)
        self.assertEqual(readiness(self.root, PAIRS[0]), 'READY')
        save(self.root / 'analysis/postrun' / PAIRS[0] / 'PAIR_RUNTIME_GATE.json', gate_fixture())
        self.assertEqual(readiness(self.root, PAIRS[0]), 'PASSED')
    def test_gate_without_histories_not_ready(self):
        save(self.root / 'analysis/postrun' / PAIRS[0] / 'PAIR_RUNTIME_GATE.json', gate_fixture())
        self.assertEqual(readiness(self.root, PAIRS[0]), 'PENDING')
    def test_schema_and_pair(self):
        for key, value in [('schema', 'r71-paired-runtime-gate-v1'), ('source_id', PAIRS[1]), ('passed', False)]:
            gate = gate_fixture();gate[key] = value
            with self.assertRaises(ValueError):validate_gate(gate, PAIRS[0])
    def test_required_actual_checks(self):
        for key in gate_fixture()['checks']:
            gate = gate_fixture();del gate['checks'][key]
            with self.assertRaises(ValueError):validate_gate(gate, PAIRS[0])
    def test_any_failed_check(self):
        gate = gate_fixture();gate['checks']['actual_capture'] = False
        with self.assertRaises(ValueError):validate_gate(gate, PAIRS[0])
    def test_wrong_nfe_route_or_valid_prefix(self):
        for key, value in [('NFE', 19), ('routed_blocks', 450), ('valid_frames', 158), ('run_id', run_id(PAIRS[1], 'p0'))]:
            gate = gate_fixture();gate['runs']['p0'][key] = value
            with self.assertRaises(ValueError):validate_gate(gate, PAIRS[0])
    def test_geometry_and_metric_protocol(self):
        gate = gate_fixture();gate['runs']['p0']['evaluation_indices'][-1] = 145
        with self.assertRaises(ValueError):validate_gate(gate, PAIRS[0])
        gate = gate_fixture();gate['runs']['p0']['video']['properties']['avg_frame_rate'] = '25/1'
        with self.assertRaises(ValueError):validate_gate(gate, PAIRS[0])
    def test_six_times_prefixed_and_same_column_geometry(self):
        self.assertEqual(INDICES, [0, 29, 58, 88, 117, 146])
        text = filters()
        self.assertEqual(text.count('trim=end_frame=147'), 3)
        self.assertEqual(text.count('setpts=PTS-STARTPTS,setsar=1'), 3)
        self.assertNotIn('crop=', text)
        self.assertNotIn('scale=', text)
        self.assertIn('hstack=inputs=3:shortest=1', text)
    def test_static_no_gpu_or_control_entry(self):
        for name in ('watch_remote.py', 'sync_publish.py', 'collect.py', 'presentation.py'):
            text = (HERE / name).read_text()
            for forbidden in ('approve-rest', 'approve-first-pair', 'cuda_gate_go', 'launch_remote.py', 'start_controller.py', '/free', 'torch.cuda', 'nvidia-smi'):
                self.assertNotIn(forbidden, text, (name, forbidden))

if __name__ == '__main__':
    unittest.main()
