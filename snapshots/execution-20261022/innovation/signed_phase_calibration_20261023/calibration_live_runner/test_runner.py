"""Synthetic full-shape CPU fixtures; never read live QK or state assets."""
import copy
import hashlib
import math
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import torch

import run as runner

torch.set_num_threads(1)


def fixture(root, env):
    root.mkdir()
    plan = env['plan']
    ann = {'schema': 'h3-live-phase-event-annotations-v1',
           'plan_sha256': env['locked']['files_sha256']['calibration_live/PLAN.json'],
           'case_id': 'short_0358', 'video_provenance': {'source': plan['source_video_provenance']},
           'events': [{'id': e['id'], 'source': e['source_interval_frames'],
                       **{m: {'status': 'observed', 'interval': e['source_interval_frames']}
                          for m in runner.METHODS}} for e in plan['events']]}
    doc = {'schema': 'h3-live-calibration-runner-input-v1', 'annotations': str(root/'annotations.json'), 'methods': {}}
    spans, start = [], 0
    for t in range(32):
        width = (1, 4, 4, 4, 4)[t % 5]
        spans.append([start, start+width-1]); start += width
    # Content shift while every head/probe and all physical bins are retained.
    k = torch.eye(128, dtype=torch.bfloat16)[:32, None, None, :].expand(32, 8, 56, 128).contiguous()
    q_native = k[torch.clamp(torch.arange(32)-2, min=0)].clone()
    for method in runner.METHODS:
        sub = root/method; sub.mkdir()
        science_path = sub/'science.json'
        shutil.copyfile(env['root']/f'replay_live_pair/plans/{method}_contract.json', science_path)
        science = runner.read(science_path); science_sha = runner.sha(science_path)
        trajectory = science['trajectory_id']
        video_path = sub/'synthetic.mp4'; video_path.write_bytes(('not a decoded fixture video '+method).encode())
        video_sha = runner.sha(video_path)
        record = {'schema': 'h3-live-phase-single-video-annotation-v1', 'trajectory_id': trajectory,
                  'case_id': 'short_0358', 'method': method, 'video_sha256': video_sha,
                  'annotation_source': 'new_complete_video', 'frame_count': 107, 'valid_frames': 105,
                  'fps': 24, 'inspected_frames': [0, 104], 'complete_new_video_reviewed': True,
                  'events': [{'id': e['id'], 'source': e['source'], **e[method]} for e in ann['events']]}
        record_path = sub/'annotation.json'; runner.dump(record_path, record)
        ann['video_provenance'][method] = {'sha256': video_sha, 'trajectory_id': trajectory,
            'annotation_source': 'new_complete_video', 'frame_count': 107,
            'annotation_record_sha256': runner.sha(record_path)}
        captures = []; paths = {}
        shapes = science['target_shapes']; packed_shape = [1, 1, sum(math.prod(s[1:]) for s in shapes)]
        for step in runner.STEPS:
            state_path = sub/f'state{step}.pt'; qk_path = sub/f'qk{step}.pt'; num_path = sub/f'numeric{step}.json'
            x = torch.full(packed_shape, step/20, dtype=torch.float32)
            x0 = torch.zeros(packed_shape, dtype=torch.float32)
            state = {'schema': 'h3-live-phase-state-v1', 'step_zero_based': step, 'target_shapes': shapes,
                     'sample_sigmas_video': science['sigmas_video'], 'packed_x': x, 'raw_packed_x0': x0}
            torch.save(state, state_path)
            identity = {'trajectory_id': trajectory, 'case': 'short_0358', 'method': method,
                'science_contract_sha256': science_sha, 'step_zero_based': step, 'layer_zero_based': 25,
                'state_file_sha256': runner.sha(state_path), 'packed_x': env['rec'].tensor_info(x),
                'raw_packed_x0': env['rec'].tensor_info(x0), 'sample_sigmas_video': science['sigmas_video'],
                'noise_sha256': science['noise_tensor_sha256']}
            raw_q = q_native if method == 'native' else k
            norm = lambda z: (z.float()*torch.rsqrt(z.float().square().mean(-1, keepdim=True)+1e-5)).to(z.dtype)
            payload = {'schema': 'h3-passive-qk-capture-v1', 'case': 'short_0358', 'method': method,
                'step_zero_based': step, 'layer_zero_based': 25, 'forward_identity': identity,
                'heads': 56, 'head_dim': 128, 'rot_dim': 96,
                'spatial_ids': [0, 135, 269, 404, 538, 673, 807, 942],
                'physical_frame_spans_inclusive': spans, 'valid_bins': [b < 105 for a, b in spans],
                'time_role': [i % 5 for i in range(32)], 'raw_Q_C': raw_q, 'raw_Q_R': k, 'raw_K_R': k,
                'actual_Q_C': norm(raw_q), 'actual_Q_R': norm(k), 'actual_K_R': norm(k),
                'q_norm_weight': torch.ones(128, dtype=torch.bfloat16), 'k_norm_weight': torch.ones(128, dtype=torch.bfloat16),
                'q_norm_eps': 1e-5, 'k_norm_eps': 1e-5,
                'position_canvas': torch.arange(32), 'position_reference': torch.arange(32),
                'rope_canvas': torch.eye(2).expand(1, 256, 1, 48, 2, 2).clone(),
                'rope_reference': torch.eye(2).expand(1, 256, 1, 48, 2, 2).clone()}
            torch.save(payload, qk_path); qhash = runner.sha(qk_path)
            row = {'step_zero_based': step, 'layer_zero_based': 25, 'qk_sha256': qhash,
                   'state_file_sha256': identity['state_file_sha256'], 'forward_identity': identity}
            captures.append(row)
            numerical = {'schema': 'h3-passive-qk-numerical-diagnostic-v1', 'capture_sha256': qhash,
                         'policy_sha256': env['locked']['files_sha256']['replay_diagnostics/POLICY.json'],
                         'numerical_definition_pass': True, 'forward_identity': identity,
                         **{key: payload[key] for key in ('case', 'method', 'step_zero_based', 'layer_zero_based')},
                         'branches': {b: {'dtype': 'torch.bfloat16', 'shape': [32, 8, 56, 128],
                            'numerical_definition_pass': True, 'full': [{'head': h, 'numerical_definition_pass': True,
                            'nrmse': 0., 'p99_abs_over_actual_rms': 0., 'max_abs_over_actual_rms': 0.} for h in range(56)]}
                            for b in ('Q_C', 'Q_R', 'K_R')}}
            runner.dump(num_path, numerical)
            paths[str(step)] = {'qk': str(qk_path), 'state': str(state_path), 'numerical_check': str(num_path)}
        obs = {'status': 'complete', 'trajectory_id': trajectory, 'case': 'short_0358', 'method': method,
            'science_contract_sha256': science_sha, 'callback_count': 20, 'actual_model_forward_count': 20,
            'completed_blocks': 1000, 'extra_model_forward_calls': 0, 'original_result_returned_without_copy': True,
            'target_shapes': shapes, 'sample_sigmas_video': science['sigmas_video'],
            'noise': {'sha256': science['noise_tensor_sha256']}, 'final_raw_result': env['rec'].tensor_info(x0), 'captures': captures}
        obs_path = sub/'observation.json'; runner.dump(obs_path, obs)
        gate = {'schema': 'h3-live-phase-trajectory-gate-v1', 'passed': True,
                **{key: obs[key] for key in ('trajectory_id','case','method','science_contract_sha256',
                    'callback_count','actual_model_forward_count','completed_blocks','extra_model_forward_calls','captures')},
                'actual_video_sha256': video_sha, 'observation_manifest_sha256': runner.sha(obs_path)}
        gate_path = sub/'gate.json'; runner.dump(gate_path, gate)
        doc['methods'][method] = {'science_contract': str(science_path), 'trajectory_gate': str(gate_path),
            'observation_manifest': str(obs_path), 'video': str(video_path), 'annotation_record': str(record_path), 'captures': paths}
    runner.dump(root/'annotations.json', ann); runner.dump(root/'inputs.json', doc)
    return doc


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = Path(cls.temp.name)
        cls.env = runner.dependencies(); cls.doc = fixture(cls.root/'base', cls.env)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.root)); self.doc = copy.deepcopy(type(self).doc)
        self.input = self.work/'inputs.json'; self.out = self.work/'result'

    def changed_json(self, key, mutate, method='global_weak'):
        path = Path(self.doc['methods'][method][key]); data = runner.read(path); mutate(data)
        dest = self.work/(method+'_'+path.name); runner.dump(dest, data); self.doc['methods'][method][key] = str(dest)
        return data, dest

    def run_doc(self):
        runner.dump(self.input, self.doc)
        return runner.run(self.input, self.out)

    def assert_no_results(self, status):
        with mock.patch.object(runner, 'analyze', side_effect=AssertionError('analysis must not execute')):
            self.assertEqual(self.run_doc()['status'], status)
        self.assertEqual([p.name for p in self.out.iterdir()], ['STATUS.json'])

    def test_missing_weak_is_pending_without_analysis(self):
        del self.doc['methods']['global_weak']; self.assert_no_results('pending')

    def test_unknown_method_is_invalid(self):
        self.doc['methods']['old'] = {}; self.assert_no_results('invalid')

    def test_unknown_step_is_invalid(self):
        self.doc['methods']['native']['captures']['8'] = {}; self.assert_no_results('invalid')

    def test_missing_required_file_is_pending(self):
        self.doc['methods']['global_weak']['trajectory_gate'] = str(self.work/'not_yet.json'); self.assert_no_results('pending')

    def test_failed_gate_is_invalid(self):
        self.changed_json('trajectory_gate', lambda x: x.update(passed=False)); self.assert_no_results('invalid')

    def test_running_observer_is_pending_but_failed_invalid(self):
        _, obs_path = self.changed_json('observation_manifest', lambda x: x.update(status='running'))
        self.changed_json('trajectory_gate', lambda x: x.update(observation_manifest_sha256=runner.sha(obs_path)))
        self.assert_no_results('pending')

    def test_failed_observer_is_invalid(self):
        _, obs_path = self.changed_json('observation_manifest', lambda x: x.update(status='failed'))
        self.changed_json('trajectory_gate', lambda x: x.update(observation_manifest_sha256=runner.sha(obs_path)))
        self.assert_no_results('invalid')

    def test_wrong_video_bytes_invalid(self):
        v = self.work/'other.mp4'; v.write_bytes(b'wrong')
        self.doc['methods']['global_weak']['video'] = str(v); self.assert_no_results('invalid')

    def test_incomplete_trajectory_invalid(self):
        self.changed_json('trajectory_gate', lambda x: x.update(completed_blocks=999)); self.assert_no_results('invalid')

    def test_wrong_actual_state_bytes_invalid(self):
        state = self.work/'wrong.pt'; torch.save({'test': 1}, state)
        self.doc['methods']['global_weak']['captures']['9']['state'] = str(state); self.assert_no_results('invalid')

    def test_numeric_head_failure_cannot_be_hidden_by_global_pass(self):
        path = Path(self.doc['methods']['global_weak']['captures']['9']['numerical_check'])
        data = runner.read(path); data['branches']['K_R']['full'][55]['nrmse'] = .011
        out = self.work/'numeric.json'; runner.dump(out, data)
        self.doc['methods']['global_weak']['captures']['9']['numerical_check'] = str(out); self.assert_no_results('invalid')

    def test_annotation_record_mutation_invalid(self):
        self.changed_json('annotation_record', lambda x: x['events'][0].update(interval=[20, 21])); self.assert_no_results('invalid')

    def test_existing_output_not_overwritten(self):
        self.out.mkdir(); (self.out/'sentinel').write_text('keep')
        with self.assertRaises(FileExistsError): self.run_doc()
        self.assertEqual((self.out/'sentinel').read_text(), 'keep')

    def test_compute_failure_leaves_no_partial_probability_files(self):
        runner.dump(self.input, self.doc)
        with mock.patch.object(runner, 'analyze', side_effect=ValueError('synthetic computation failure')):
            result = runner.run(self.input, self.out)
        self.assertEqual(result['status'], 'invalid'); self.assertEqual([p.name for p in self.out.iterdir()], ['STATUS.json'])

    def test_geometry_and_norm_mismatch_are_not_broadcast(self):
        paths = runner.paths_from_manifest(self.root/'base/inputs.json')
        real_load = torch.load
        def altered(path, **kwargs):
            data = real_load(path, **kwargs)
            if str(path) == self.doc['methods']['global_weak']['captures']['9']['qk']:
                data['q_norm_weight'] = data['q_norm_weight']*2
            return data
        with mock.patch.object(torch, 'load', side_effect=altered):
            with self.assertRaisesRegex(runner.Invalid, 'cross-capture norm/layout'):
                runner.preflight(paths, self.env)
        for key, value in [('spatial_ids', list(range(8))), ('valid_bins', [True]*32), ('time_role', [0]*32)]:
            payload = real_load(paths['native.9.qk'], weights_only=True); payload[key] = value
            with self.assertRaises(runner.Invalid): runner.geometry(payload, torch)

    def test_actual_state_tensor_signature_is_checked_beyond_file_receipt(self):
        paths = runner.paths_from_manifest(self.root/'base/inputs.json')
        real_load = torch.load
        def altered(path, **kwargs):
            data = real_load(path, **kwargs)
            if str(path) == self.doc['methods']['global_weak']['captures']['9']['state']:
                data['raw_packed_x0'][0, 0, -1] = 1
            return data
        with mock.patch.object(torch, 'load', side_effect=altered):
            with self.assertRaisesRegex(runner.Invalid, 'actual AV tensor signature differs'):
                runner.preflight(paths, self.env)

    def test_numerical_receipt_wrong_policy_or_missing_head_rejected(self):
        paths = runner.paths_from_manifest(self.root/'base/inputs.json')
        c = torch.load(paths['native.9.qk'], weights_only=True)
        report = runner.read(paths['native.9.numerical_check'])
        variants = []
        wrong = copy.deepcopy(report); wrong['policy_sha256'] = '0'*64; variants.append(wrong)
        wrong = copy.deepcopy(report); wrong['branches']['Q_C']['full'].pop(); variants.append(wrong)
        wrong = copy.deepcopy(report); wrong['branches']['Q_R']['full'][0]['nrmse'] = float('nan'); variants.append(wrong)
        for wrong in variants:
            with self.assertRaises(runner.Invalid):
                runner.numeric_check(wrong, runner.sha(paths['native.9.qk']), c, self.env)

    def test_wrong_qk_receipt_is_invalid(self):
        self.changed_json('trajectory_gate', lambda x: x['captures'][0].update(qk_sha256='0'*64))
        self.assert_no_results('invalid')

    def test_changed_source_window_is_invalid(self):
        data = runner.read(self.doc['annotations']); data['events'][0]['source'] = [13, 18]
        path = self.work/'annotations.json'; runner.dump(path, data); self.doc['annotations'] = str(path)
        self.assert_no_results('invalid')

    def test_full_pipeline_preserves_all_arrays_and_cross_identity(self):
        result = self.run_doc(); self.assertEqual(result['status'], 'complete')
        summary = runner.read(self.out/'summary.json'); self.assertEqual(len(summary['steps']), 2)
        self.assertFalse(summary['semantic_phase_validated'])
        for step in runner.STEPS:
            arrays = np.load(self.out/f'step{step:03d}_all_probabilities.npz')
            for key in ('qn_kn','qw_kw','qw_kn','qn_kw','qrn_kn','qrw_kw'):
                self.assertEqual(arrays[key].shape, (56,32,8,32))
                self.assertTrue(np.all(arrays[key][:,31] == 0)); self.assertTrue(np.all(arrays[key][...,31] == 0))
            np.testing.assert_allclose(arrays['query_contribution']+arrays['key_contribution'], arrays['paired_total'], atol=1e-12)
            self.assertGreater(arrays['paired_total'][:,3:30].mean(), 5)
            np.testing.assert_allclose(arrays['key_contribution'], 0, atol=1e-12)
        self.assertEqual(set(p.name for p in self.out.iterdir()), {'STATUS.json','summary.json','step009_all_probabilities.npz','step019_all_probabilities.npz'})


if __name__ == '__main__': unittest.main()
