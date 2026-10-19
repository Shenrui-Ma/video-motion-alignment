import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import contract as c
import consume
import one_phase
import remote_consume

P = c.read(c.HERE / 'PROTOCOL.json')


class ContractTests(unittest.TestCase):
    def producer(self):
        return {'cases': copy.deepcopy(P['cases']),
                'case_order': [x['run_id'] for x in P['cases']],
                'geometry': P['geometry'],
                'evaluation': {}}

    def test_fixed_five_pair_order_and_map(self):
        self.assertTrue(c.check_declared_cases(P, self.producer()))
        for key, value in [('geometry', dict(P['geometry'], frames=141)),
                           ('cases', [dict(P['cases'][0],valid_frame_count=90)]+P['cases'][1:]),
                           ('cases', P['cases'][::-1])]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.check_declared_cases(dict(P, **{key: value}), self.producer())

    def test_automatic_counts_and_replay(self):
        case = P['cases'][0]
        row = {k: case[k] for k in ('run_id', 'source_id', 'seed')}
        row.update(passed=True, NFE=23, active_denoising_indices=[3, 4, 9],
                   actual_routed_blocks=150, observations_replayed=20,
                   source_video_sha256=case['video_sha256'], padding_evaluated=False,
                   decoded_frame_md5_equal=True, score_frame_indices=list(range(case['valid_frame_count'])))
        self.assertTrue(c.check_case_summary(row, case))
        for key, value in [('NFE', 20), ('actual_routed_blocks', 100),
                           ('observations_replayed', 19), ('active_denoising_indices', [0, 3, 4]),
                           ('active_denoising_indices', [3, 3, 9]),
                           ('padding_evaluated', True), ('decoded_frame_md5_equal', False)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                c.check_case_summary(dict(row, **{key: value}), case)
        self.assertTrue(c.check_case_summary(dict(row, NFE=20, actual_routed_blocks=0,
                                                active_denoising_indices=[]), case))

    def test_stability_is_required(self):
        snap = {'status': 'success_files_present', 'token': 'a'}
        mode, state = one_phase.readiness(snap, None, 0, 60)
        self.assertEqual(mode, 'stabilizing')
        self.assertEqual(one_phase.readiness(snap, state, 59, 60)[0], 'stabilizing')
        self.assertEqual(one_phase.readiness(snap, state, 60, 60)[0], 'ready')
        self.assertEqual(one_phase.readiness(dict(snap, token='b'), state, 61, 60)[0], 'stabilizing')

    def test_pending_binding_cannot_execute(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c.save(root / 'PROTOCOL.json', {})
            c.save(root / 'FREEZE.json', {'files': {}})
            c.save(root / 'BINDING.json', {'approved_for_consumer_start': False})
            with patch.object(one_phase, 'HERE', root), patch.object(one_phase.subprocess, 'run') as call:
                with self.assertRaises((ValueError, KeyError)):
                    one_phase.prepare()
                call.assert_not_called()

    def test_case_release_waits_for_exact_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            arc = root / 'archive'
            arc.mkdir()
            owner = {'pid': 123, 'identity': {'start_ticks': 'fixed'}}
            with patch.object(remote_consume, 'ROOT', root), patch.object(remote_consume, 'ARC', arc), \
                    patch.object(remote_consume, 'checked_archive', return_value=owner):
                self.assertEqual(remote_consume.status()['phase'], 'awaiting_root_release')
                c.save(root / 'processes/cleanup.json', {'service_record': {'pid': 456},
                       'process_absent': True, 'own_compute_absent': True, 'child_compute_absent': True})
                with self.assertRaises(ValueError):
                    remote_consume.status()
                c.save(root / 'processes/cleanup.json', {'service_record': owner,
                       'process_absent': True, 'own_compute_absent': True, 'child_compute_absent': True})
                self.assertEqual(remote_consume.status(), {'phase': 'case', 'run': P['cases'][0]['run_id']})


class InventoryTests(unittest.TestCase):
    def fixture(self, root):
        manifest = {'files': {}}
        for rel in ('processes/service.json', 'configs/queue.json', 'configs/scientific_contract.json', 'audit/gpu_dynamic_union_gate.json', 'audit/known_endpoint_90_gate.json', 'audit/resource_admission.json'):
            c.save(root / rel, {})
        producer_cases = []
        for case in P['cases']:
            run = case['run_id']
            c.save(root / f'configs/graphs/{run}.json', {'5': {'inputs': {'run_id': run + '_shared'}}})
            c.save(root / f'logs/{run}_history.json', {'status': {'completed': True, 'status_str': 'success'},
                   'outputs': {'14': {'images': [{'type': 'output', 'filename': run + '_00001_.mp4', 'subfolder': ''}]}}})
            c.save(root / f'logs/{run}_job.json', {'status': 'success'})
            for rel in (f'audit/{run}_conditioning.json', f'audit/{run}_shared_conditioning.json'):
                c.save(root / rel, {})
            noise = root / f'audit/{run}_pair_noise.pt'
            c.save(root / f'audit/{run}_noise.json', {'cache_file': str(noise)})
            names = [f'x0_step{i:03d}.pt' for i in range(20)] + ['sampler_final.pt']
            c.save(root / f'audit/x0/{run}/manifest.json', {'status': 'complete',
                   'captures': [{'file': x} for x in names[:-1]], 'final_sampler_result': {'file': names[-1]}})
            for rel in [f'audit/x0/{run}/' + x for x in names] + [str(noise.relative_to(root)), f'output/{run}_00001_.mp4']:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
            folder = root / 'audit/counterfactual' / (run + '_snapshots')
            folder.mkdir(parents=True)
            (folder / 'sampler_final_raw.pt').write_bytes(b'fixture')
            measurements = []
            for i in range(20):
                request = root / 'audit/observations' / f'step_{run}_{i}' / 'request.json'
                c.save(request, {'run_id': run})
                measurements.append({'request_file': str(request)})
            c.save(root / f'audit/counterfactual/{run}.json', {'status': 'complete',
                   'counterfactual': {'steps': [{}] * 20, 'measurements': measurements, 'branches': [], 'inputs': []}})
            source_pose = root / 'configs/parents' / case['source_id'] / 'source.pose.json'
            c.save(source_pose, {})
            producer_cases.append(dict(case, source_pose_path=str(source_pose)))
            for basename in (case['video'], case['provenance'], case['original_source'], case['source_id']+'_prompt.txt'):
                path = root / 'inputs' / basename
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b'fixture')
                manifest['files'][str(path.relative_to(root))] = {}
            for key in ('video',):
                path = root / 'input' / case[key]
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b'fixture')
        c.save(root / 'configs/protocol.json', {'cases': producer_cases})
        c.save(root / 'deploy_manifest.json', manifest)

    def test_all_inputs_observations_and_snapshots_archived(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            with patch.object(remote_consume, 'ROOT', root):
                rows = [str(x.relative_to(root)) for x in remote_consume.inventory()]
            self.assertEqual(sum(x.startswith('inputs/') for x in rows), 20)
            self.assertEqual(sum(x.startswith('input/') for x in rows), 5)
            self.assertEqual(sum('/x0/' in x and x.endswith('.pt') for x in rows), 105)
            self.assertEqual(sum(x.endswith('/request.json') for x in rows), 100)
            self.assertEqual(sum(x.endswith('source.pose.json') for x in rows), 5)

    def test_resource_profiles_and_decode_gate_evidence_archived(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            paths = ('configs/decoder_memory_profile.json', 'configs/main_memory_profile.json',
                     'configs/decoder_memory_evidence/full90_gate.json', 'configs/retry/resource_v4/REVIEW.json')
            manifest = c.read(root / 'deploy_manifest.json')
            for name in paths:
                c.save(root / name, {})
                manifest['files'][name] = {}
            c.save(root / 'deploy_manifest.json', manifest)
            evidence = 'audit/observations/known_endpoint_90/bootstrap_observer_bindings.json'
            c.save(root / evidence, {})
            with patch.object(remote_consume, 'ROOT', root):
                rows = {str(x.relative_to(root)) for x in remote_consume.inventory()}
            self.assertTrue(set(paths) | {evidence} <= rows)

    def test_missing_snapshot_and_cross_case_observation_fail(self):
        for mode in ('missing', 'cross_case', 'duplicate'):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                self.fixture(root)
                run = P['cases'][0]['run_id']
                if mode == 'missing':
                    (root / f'audit/x0/{run}/x0_step000.pt').unlink()
                else:
                    audit = root / f'audit/counterfactual/{run}.json'
                    value = c.read(audit)
                    if mode == 'duplicate':
                        value['counterfactual']['measurements'][1] = value['counterfactual']['measurements'][0]
                    else:
                        c.save(Path(value['counterfactual']['measurements'][0]['request_file']), {'run_id': 'wrong'})
                    c.save(audit, value)
                with patch.object(remote_consume, 'ROOT', root), self.assertRaises(ValueError):
                    remote_consume.inventory()

    def test_capacity_certificate_evidence_is_bound_and_archived(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            evidence = root / 'audit/main_capacity_probe/run_reserve8_002/audit/resources.jsonl'
            evidence.parent.mkdir(parents=True)
            evidence.write_text('{"memory": 123}\n')
            c.save(root / 'audit/resource_admission.json', {'evidence': [
                {'file': str(evidence), 'sha256': c.sha(evidence)}]})
            with patch.object(remote_consume, 'ROOT', root):
                self.assertIn(evidence, remote_consume.inventory())
                evidence.write_text('{"memory": 456}\n')
                with self.assertRaisesRegex(ValueError, 'resource evidence changed'):
                    remote_consume.inventory()




class DomainTests(unittest.TestCase):
    def observer(self,case):
        n=case['valid_frame_count'];rows=[]
        for length in (16,32):
            for start in sorted(set(range(0,n-length+1,4))|{n-length}):
                for feature in ('arm_direction','left_arm_direction','right_arm_direction'):
                    d={'curve':[None]*49,'status':'unknown','reliable_lag_frames':None,'same_frame':None}
                    rows.append({'window':[start,start+length-1],'feature':feature,'baseline':'unknown','measurements':{'0.3':d,'0.5':d}})
        return {'status':'measured','windows':rows}
    def test_five_valid_domains_and_padding_rejection(self):
        expected=[102,102,84,90,108]
        for case,count in zip(P['cases'],expected):
            ob=self.observer(case);summary=c.observer_summary(ob,case)
            self.assertEqual(summary['rows'],count)
            self.assertEqual(summary['baseline_counts']['unknown'],count)
            wrong=copy.deepcopy(ob);wrong['windows'][-1]['window'][1]=89
            with self.assertRaises(ValueError):c.observer_summary(wrong,case)
    def test_visibility_unknown_is_separate(self):
        case=P['cases'][0]
        self.assertEqual(c.observer_summary({'status':'unknown_visibility','windows':[]},case)['rows'],0)
        for value in ({'status':'technical_error','windows':[]}, {'status':'unknown_visibility','windows':[{}]}):
            with self.assertRaises(ValueError):c.observer_summary(value,case)

if __name__ == '__main__':
    unittest.main()
