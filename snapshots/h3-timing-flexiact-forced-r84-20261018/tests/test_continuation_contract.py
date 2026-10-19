import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import r84_contract as c
import execution_gate as gate
import preflight


class Contracts(unittest.TestCase):
    def test_registry_order_and_numeric_modules(self):
        result = preflight.check()
        self.assertTrue(result['passed'])
        self.assertIn('one_leg', result['jobs'][0])
        self.assertFalse(result['same_service_generation'])
        self.assertTrue(result['actual_prefix_equality_required'])

    def test_only_router_science_changes(self):
        jobs, order = c.registry()
        allowed = {('5', 'audit_dir'), ('5', 'run_id'), ('6', 'audit_dir'), ('6', 'run_id'),
            ('14', 'filename_prefix'), ('50', 'audit_dir'), ('50', 'run_id'), ('50', 'mode'),
            ('50', 'step_start'), ('50', 'step_end'), ('51', 'source_audit_dir'),
            ('51', 'source_run_id'), ('51', 'run_id'), ('52', 'output_dir'), ('52', 'run_id')}
        for run in order:
            case = jobs[run]['case']; before = c.read(ROOT / case['parent_graph'])
            after = c.read(ROOT / 'configs/graphs' / (run + '.json'))
            self.assertEqual(set(before), set(after))
            diff = set()
            for node in before:
                self.assertEqual(before[node]['class_type'], after[node]['class_type'])
                self.assertEqual(set(before[node]['inputs']), set(after[node]['inputs']))
                for key in before[node]['inputs']:
                    if before[node]['inputs'][key] != after[node]['inputs'][key]: diff.add((node, key))
            self.assertLessEqual(diff, allowed)
            self.assertEqual(before['6']['inputs']['pair_id'], after['6']['inputs']['pair_id'])
            self.assertEqual(before['5']['inputs']['prompt'], after['5']['inputs']['prompt'])
            self.assertEqual(after['50']['inputs']['mode'], 'mass_preserve')

    def test_modified_prompt_seed_and_geometry_rejected(self):
        original = c.read
        for mutation in ('prompt', 'seed', 'geometry'):
            def read(path, mutation=mutation):
                value = original(path)
                if Path(path).name == 'scientific_contract.json':
                    value = copy.deepcopy(value)
                    if mutation == 'prompt': value['cases'][0]['prompt'] += 'changed'
                    elif mutation == 'seed': value['cases'][0]['seed'] += 1
                    else: value['cases'][0]['geometry']['frames'] += 17
                return value
            with self.subTest(mutation=mutation), patch.object(c, 'read', side_effect=read):
                with self.assertRaises(ValueError): c.registry()

    def test_failed_old_run_and_future_native_not_registered(self):
        for run in ('r84_chest__game_man_5_seed2026101701_forced', 'r84_one_leg__movie_man_9_seed2026101701_native'):
            with self.assertRaisesRegex(ValueError, 'unknown run'): c.validate_job(run)

    def test_target_generation_replacement_rejected(self):
        run = c.registry()[1][0]; r = {'runtime_profile_sha256': 'runtime'}
        jobs = {run: {'graph_sha256': 'graph'}}
        approved = {'schema': 'r84-individual-job-approval-v1', 'root_approved': True, 'run': run,
            'native_reviewed': True, 'runtime_profile_sha256': 'runtime', 'graph_sha256': 'graph',
            'historical_evidence': {'sha': 'old'}, 'target_service': {'pid': 1, 'identity': {'start': 10}}}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'audit/ROOT_JOB_APPROVALS').mkdir(parents=True)
            (p/'audit/ROOT_JOB_APPROVALS'/f'{run}.json').write_text(json.dumps(approved))
            (p/'processes').mkdir(); (p/'processes/service.json').write_text(json.dumps({'pid': 1, 'identity': {'start': 20}}))
            with patch.object(gate, 'approval', return_value=r), patch.object(gate, 'registry', return_value=(jobs, [run])), patch.object(gate, 'historical_evidence', return_value={'sha':'old'}):
                with self.assertRaisesRegex(ValueError, 'generation changed'): gate.admitted_job(run,p)

    def test_original_pt_not_part_of_portable_download(self):
        self.assertEqual(list((ROOT/'ancestry').rglob('*.pt')), [])

    def test_no_controller_script_or_automatic_queue(self):
        self.assertFalse((ROOT/'scripts/run_queue.py').exists())
        self.assertFalse((ROOT/'scripts/start_controller.py').exists())
        self.assertIn("required=True", (ROOT/'scripts/launch_remote.py').read_text())

    def test_second_job_requires_real_first_gate(self):
        _, order = c.registry()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(gate, 'registry', return_value=({}, order)):
                self.assertIsNone(gate.previous_pair_evidence(order[0], root))
                with self.assertRaises(FileNotFoundError): gate.previous_pair_evidence(order[1], root)
                path=root/'analysis/postrun/one_leg__movie_man_9/PAIR_RUNTIME_GATE.json'
                path.parent.mkdir(parents=True)
                value={'schema':'r84-historical-native-paired-runtime-gate-v1','source_id':'one_leg__movie_man_9',
                    'passed':False,'checks':{'Native_prefix_0_5_equal':False},'runs':{'forced':{'run_id':order[0]}}}
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError,'has not passed'): gate.previous_pair_evidence(order[1],root)
                value.update(passed=True,checks={'Native_prefix_0_5_equal':True});path.write_text(json.dumps(value))
                self.assertEqual(gate.previous_pair_evidence(order[1],root)['sha256'], c.sha(path))

    def test_capacity30_is_trial_not_empirical_bound(self):
        decision=c.read(ROOT/'design/CAPACITY_TRIAL_30GIB.json')
        self.assertEqual(decision['required_free_GiB'],30)
        self.assertFalse(decision['measured_peak_bound'])
        self.assertEqual(decision['geometry'],[158,768,1152])


class ConditionEquality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT/'analysis/postrun'))
        import verify_pair
        cls.verify = verify_pair

    def test_equal_and_changed_actual_signal(self):
        keys=('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion',
              'conditioning_embedding','token_tags','target_latent_shapes','packed_layout')
        a={k:'original' for k in keys}
        self.assertTrue(all(self.verify.equal_condition_fields(a,a).values()))
        for key in keys:
            b=dict(a); b[key]='changed'
            with self.subTest(key=key): self.assertFalse(all(self.verify.equal_condition_fields(a,b).values()))


if __name__ == '__main__': unittest.main()
