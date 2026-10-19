"""CPU contracts for migration, actual-parent refusal and three-arm verification."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'extensions')]
from execution_contract import read, sha, verify_parent_anchors, verify_candidate, write_new
import preflight
import r59_contract
import verify_decisions
import service
from observer_import import t
from test_visible_feedback import measurement, G
from H3AutomaticWindowRouter.selector import Controller


def decision_audit(arm, kind='unknown'):
    case = next(case for case in r59_contract.cases() if case['source_id'] == 'short_0263' and case['arm'] == arm)
    controller = Controller(G, arm=arm)
    steps, measurements, branches, summaries, prefix, mask = [], [], [], [], [], []
    first = None
    for index in range(20):
        value = measurement(index, kind) if controller.needs_observation else None
        decision = controller.select(index, value)
        if value is not None:
            measurements.append(value)
        decision['native_nfe_index'] = len(branches)
        if decision['chosen_full']:
            mask.append(index)
            if first is None:
                first = index
        current = []
        for branch in ('native', 'full') if decision['chosen_full'] else ('native',):
            nfe = len(branches)
            record = {'physical_index': index, 'branch': branch, 'nfe_index': nfe, 'seed': case['seed'],
                'file': '/synthetic/' + str(nfe), 'raw_stream_signatures': ['v' + str(nfe), 'a' + str(nfe)],
                'same_input': 'x' + str(index), 'condition_sha256': 'cond', 'reference_sha256': 'ref',
                'sigma': 1 - index / 20, 'sigma_next': 1 - (index + 1) / 20,
                'global_rng_unchanged': True, 'condition_unchanged': True, 'full_grid_unchanged': True}
            branches.append(record)
            current.append(record)
            summaries.append({'physical_index': index, 'branch': branch, 'nfe_index': nfe,
                'route_alpha': decision['route_alpha'] if branch == 'full' else 0.0,
                'latent_bins': decision['latent_bins'] if branch == 'full' else [], 'control_state': decision['control_state']})
            eligible = branch == 'native' and (first is None or index <= first)
            prefix.append({'gate': 'native_prefix', 'physical_index': index, 'branch': branch,
                           'status': 'pass' if eligible else 'not_applicable', 'tensor_equal': eligible})
        chosen = current[-1]
        steps.append({'physical_index': index, 'callback_observed_once': True,
            'decision': decision, 'selected_branch': chosen['branch'], 'chosen_file': chosen['file'],
            'chosen_raw_stream_signatures': chosen['raw_stream_signatures'], 'nfe_indices': [row['nfe_index'] for row in current]})
    counter = {'policy': arm, 'weak_schedule': {'indices': list(range(6, 15)), 'alpha': .25, 'all_bins': 27},
        'observer_descriptor_version': 'r56-arm-bone-unit-v1', 'full_physical_indices': mask,
        'actual_model_nfe': len(branches), 'actual_euler_updates': 20, 'callback_count': 20,
        'steps': steps, 'branches': branches, 'measurements': measurements,
        'pair_gates': [{'gate': 'initial_binding', 'pass': True, 'seed': case['seed'],
            'actual_noise_and_producer_clean_inputs_exact': True, 'archived_embedding_tensor': {'actual_tensor_equal': True}}] + prefix}
    return case, {'status': 'complete', 'counterfactual': counter, 'completed_forward_calls': len(branches),
        'completed_calls': len(branches) * 50, 'routed_calls': len(mask) * 50,
        'calls_by_forward': [50] * len(branches), 'forward_summaries': summaries}


class Registry(unittest.TestCase):
    def test_candidate_and_fifteen_jobs(self):
        self.assertEqual(len(verify_candidate()['cases']), 20)
        jobs, order = r59_contract.registry()
        self.assertEqual(len(order), 15)
        self.assertEqual({arm: sum(row['arm'] == arm for row in jobs.values()) for arm in ('visible_only', 'visible_fallback', 'weak_only')}, {'visible_only': 5, 'visible_fallback': 5, 'weak_only': 5})
        for run in order:
            r59_contract.validate_job(run, inputs=False)
    def test_native_reuse_cannot_be_submitted(self):
        with self.assertRaisesRegex(ValueError, 'Native is reused'):
            r59_contract.validate_job('r59_short_0210_seed2026101701_native', inputs=False)
    def test_actual_parent_pending_blocks_input_validation(self):
        with self.assertRaisesRegex(ValueError, 'actual R57 parent pending'):
            r59_contract.validate_job(r59_contract.registry()[1][0])
    def test_preparation_passes_but_formal_preflight_refuses(self):
        self.assertEqual(preflight.prepared()['jobs'], 15)
        with self.assertRaisesRegex(ValueError, 'WAITING_R57'):
            preflight.check(metadata_only=True)
    def test_relocation_changes_only_administrative_paths(self):
        case = r59_contract.executable_cases()[0]
        graph = r59_contract.derive_graph(case)
        original = read(ROOT / 'candidate/configs/graphs' / (case['run_id'] + '.json'))
        for node, field in (('5', 'audit_dir'), ('6', 'audit_dir'), ('50', 'audit_dir'), ('51', 'source_audit_dir'), ('52', 'output_dir')):
            graph[node]['inputs'][field] = original[node]['inputs'][field]
        self.assertEqual(graph, original)


class ParentAnchors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runs = ['r57_' + source + '_seed2026101701_native' for source in r59_contract.SOURCES]
        write_new(self.root / 'deploy_manifest.json', {'files': {}})
        write_new(self.root / 'FILE_INVENTORY.json', {})
        checks = {run + '_actual_' + key: True for run in self.runs for key in ('reference_equal_P0', 'initial_AV_noise_equal_P0')}
        write_new(self.root / 'RUNTIME_GATE.json', {'passed': True, 'checks': checks,
            'runs': {run: {'NFE': 20, 'Euler_updates': 20, 'callback_count': 20} for run in self.runs}})
        self.update_gate()
    def tearDown(self):
        self.tmp.cleanup()
    def update_gate(self):
        (self.root / 'RUN_GATE.json').write_text(json.dumps({'passed': True, 'run_id': 'batch', 'runs': self.runs,
            'file_inventory_sha256': sha(self.root / 'FILE_INVENTORY.json'), 'runtime_gate_sha256': sha(self.root / 'RUNTIME_GATE.json')}))
    def check(self):
        return verify_parent_anchors(self.root, sha(self.root / 'deploy_manifest.json'), self.runs)
    def test_synthetic_complete_anchor(self):
        self.assertTrue(self.check()[0]['passed'])
    def test_missing_actual_parent_refused(self):
        (self.root / 'RUNTIME_GATE.json').unlink()
        with self.assertRaisesRegex(ValueError, 'pending'):
            self.check()
    def test_wrong_external_manifest_anchor_refused(self):
        with self.assertRaisesRegex(ValueError, 'deployment anchor'):
            verify_parent_anchors(self.root, '0' * 64, self.runs)
    def test_changed_runtime_bytes_refused(self):
        (self.root / 'RUNTIME_GATE.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'anchors changed'):
            self.check()
    def test_missing_actual_noise_pairing_refused_even_all_declared_checks_true(self):
        path = self.root / 'RUNTIME_GATE.json'
        value = read(path)
        del value['checks'][self.runs[0] + '_actual_initial_AV_noise_equal_P0']
        path.write_text(json.dumps(value)); self.update_gate()
        with self.assertRaisesRegex(ValueError, 'pairing to P0'):
            self.check()
    def test_parent_extra_Euler_updates_refused(self):
        path = self.root / 'RUNTIME_GATE.json'; value = read(path)
        value['runs'][self.runs[0]]['Euler_updates'] = 21
        path.write_text(json.dumps(value)); self.update_gate()
        with self.assertRaisesRegex(ValueError, 'Euler'):
            self.check()


class Transactions(unittest.TestCase):
    def test_all_three_arm_histories(self):
        for arm, kind, nfe, observations in [('visible_only', 'unknown', 20, 20), ('visible_fallback', 'unknown', 29, 20), ('weak_only', 'unknown', 29, 0), ('visible_only', 'candidate', 39, 20)]:
            with self.subTest(arm=arm, kind=kind):
                case, audit = decision_audit(arm, kind)
                result = verify_decisions.check(audit, case)
                self.assertEqual((result['NFE'], result['observations']), (nfe, observations))
                self.assertFalse(result['runtime_payloads_verified'])
    def reject(self, edit, arm='visible_fallback', kind='unknown'):
        case, audit = decision_audit(arm, kind)
        edit(audit)
        with self.assertRaises(ValueError):
            verify_decisions.check(audit, case)
    def test_wrong_strength_refused(self):
        self.reject(lambda audit: audit['forward_summaries'][7].__setitem__('route_alpha', 1))
    def test_missing_observer_is_not_scientific_unknown(self):
        self.reject(lambda audit: audit['counterfactual']['measurements'].pop())
    def test_weak_arm_observer_rejected(self):
        self.reject(lambda audit: audit['counterfactual']['measurements'].append(measurement(0)), 'weak_only')
    def test_extra_euler_update_refused(self):
        self.reject(lambda audit: audit['counterfactual'].__setitem__('actual_euler_updates', 21))
    def test_full_branch_different_state_refused(self):
        self.reject(lambda audit: audit['counterfactual']['branches'][7].__setitem__('same_input', 'different'))
    def test_wrong_chosen_endpoint_refused(self):
        self.reject(lambda audit: audit['counterfactual']['steps'][6].__setitem__('selected_branch', 'native'))
    def test_reusing_old_parent_after_first_intervention_refused(self):
        def edit(audit):
            row = next(row for row in audit['counterfactual']['pair_gates'] if row['gate'] == 'native_prefix' and row['physical_index'] == 7 and row['branch'] == 'native')
            row.update(status='pass', tensor_equal=True)
        self.reject(edit)
    def test_real_candidate_not_overridden_by_fallback(self):
        self.reject(lambda audit: audit['counterfactual']['steps'][6]['decision'].__setitem__('route_alpha', .25), kind='candidate')


class Resources(unittest.TestCase):
    def test_foreign_compute_allowed_with_own_identity_registry(self):
        admission = {'permitted_compute_processes': []}
        with patch.object(t, 'admission_document'), patch.object(service, 'proc_uid', return_value=os.getuid() + 1):
            service.check_admission(admission, [{'pid': 123, 'gpu_uuid': service.GPU}], {'queue_running': [], 'queue_pending': []})
    def test_unregistered_own_compute_refused(self):
        with patch.object(t, 'admission_document'), patch.object(service, 'proc_uid', return_value=os.getuid()), patch.object(service, 'external_identity', return_value={'uid': os.getuid()}):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected own'):
                service.check_admission({'permitted_compute_processes': []}, [{'pid': 123, 'gpu_uuid': service.GPU}], {'queue_running': [], 'queue_pending': []})
    def test_third_own_card_refused(self):
        identity = {'uid': os.getuid(), 'start_ticks': '11', 'cmdline_sha256': 'a' * 64}
        with patch.object(t, 'admission_document'), patch.object(service, 'proc_uid', return_value=os.getuid()), patch.object(service, 'external_identity', return_value=identity):
            with self.assertRaises(t.ResourceUnavailable):
                service.check_admission({'permitted_compute_processes': [{'pid': 123, 'identity': identity}]}, [{'pid': 123, 'gpu_uuid': 'third-GPU'}], {'queue_running': [], 'queue_pending': []})
    def test_unmeasured_capacity_refused(self):
        with self.assertRaisesRegex(ValueError, 'pending'):
            service.main_memory_profile()
    def test_actual_launch_refused_on_Mac_without_any_process_creation(self):
        with patch.object(service.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(RuntimeError, 'exact remote'):
                service.start()
        popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
