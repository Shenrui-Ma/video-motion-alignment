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
                'evaluation': {'score_output_indices': P['score_output_indices']}}

    def test_fixed_five_pair_order_and_map(self):
        self.assertTrue(c.check_declared_cases(P, self.producer()))
        for key, value in [('geometry', dict(P['geometry'], frames=141)),
                           ('score_output_indices', list(range(49))),
                           ('cases', P['cases'][::-1])]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.check_declared_cases(dict(P, **{key: value}), self.producer())

    def test_automatic_counts_and_replay(self):
        case = P['cases'][0]
        row = {k: case[k] for k in ('run_id', 'source_id', 'seed', 'identity', 'portrait_sha256')}
        row.update(passed=True, NFE=23, active_denoising_indices=[3, 4, 9],
                   actual_routed_blocks=150, observations_replayed=20,
                   source_video_sha256=case['video_sha256'], padding_evaluated=False,
                   decoded_frame_md5_equal=True, score_output_indices=list(range(0, 147, 3)))
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
        for rel in ('processes/service.json', 'configs/queue.json', 'configs/scientific_contract.json'):
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
            for basename in (case['video'], case['portrait'], case['provenance'],
                             f"source_{case['source_id']}_original.mp4", f"source_{case['source_id']}_official_caption.txt"):
                path = root / 'inputs' / basename
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b'fixture')
                manifest['files'][str(path.relative_to(root))] = {}
            for key in ('video', 'portrait'):
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
            self.assertEqual(sum(x.startswith('inputs/') for x in rows), 25)
            self.assertEqual(sum(x.startswith('input/') for x in rows), 10)
            self.assertEqual(sum('/x0/' in x and x.endswith('.pt') for x in rows), 105)
            self.assertEqual(sum(x.endswith('/request.json') for x in rows), 100)
            self.assertEqual(sum(x.endswith('source.pose.json') for x in rows), 5)

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


if __name__ == '__main__':
    unittest.main()
