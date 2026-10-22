import copy, json, shutil, struct, sys, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
from media import check_time, VALID, TOTAL, ROLES
from review import evaluate_event, checked_interval, validate_completed

class Contract(unittest.TestCase):
    def setUp(self):
        self.cfg = c.read(c.ROOT/'configs/contract.json')
        runtime = c.read(c.ROOT/'configs/producer_runtime.json')
        self.owner = {'pid': 12345, 'identity': {'uid': runtime['uid'], 'start_ticks': '123', 'cmdline_sha256': 'fixture'},
                      'gpu_uuid': runtime['gpu_uuid'], 'port': runtime['port']}
        self.pairs = {}
        for seed in c.SEEDS:
            runs = {}
            for arm in c.ARMS:
                run = self.cfg['runs'][str(seed)][arm]
                runs[arm] = {'run_id': run, 'seed': seed, 'solver': 'euler', 'sampler_function': 'sample_euler',
                    'NFE': 20, 'solver_updates': 20, 'routed_blocks': 450 if arm == 'fixed' else 0,
                    'valid_frames': 98, 'evaluation_indices': list(range(98)),
                    'video': {'file': self.cfg['producer_remote']+'/output/'+run+'_00001_.mp4', 'sha256': 'fixture',
                              'properties': {'width': 1312, 'height': 736, 'avg_frame_rate': '24/1', 'nb_read_frames': '107'}}}
            self.pairs[str(seed)] = {'schema': 'r113-fresh-seed-pair-runtime-gate-v1', 'passed': True,
                 'source_id': 'short_0252', 'seed': seed, 'runs': runs, 'valid_frames': 98, 'frame_rate': 24,
                 'evaluation_crop_xywh': [16, 8, 1280, 720], 'checks': dict.fromkeys(c.pair_required_checks(), True),
                 'equal_normalized_prediction_steps': list(range(6)), 'equal_raw_prefix_steps': [0, 1],
                 'service_owner': self.owner, 'noise_cache': {'tensor_signatures': [{'sha256': str(seed)+'video'}, {'sha256': str(seed)+'audio'}]}}
        self.aggregate = {'schema': 'r113-two-seed-runtime-gate-v1', 'passed': True, 'source_id': 'short_0252',
             'seeds': list(c.SEEDS), 'jobs': self.cfg['jobs'], 'report_all_seeds': True, 'service_owner': self.owner,
             'checks': dict.fromkeys(['producer_seal', 'actual_runtime_device', 'distinct_seed_noise_video_and_audio',
                                     *[f'seed{s}_actual_pair' for s in c.SEEDS]], True),
             'producer_seal_sha256': self.cfg['producer_seal_sha256'], 'runtime_profile_sha256': self.cfg['producer_runtime_sha256'],
             'preregistered_events_sha256': self.cfg['events_sha256'], 'runtime_profile': runtime,
             'valid_frames': 98, 'frame_rate': 24, 'evaluation_crop_xywh': [16, 8, 1280, 720],
             'pair_gate_receipts': [{'seed': seed, 'file': self.cfg['producer_remote']+f'/analysis/postrun/seed{seed}/PAIR_RUNTIME_GATE.json',
                                    'sha256': 'fixture'} for seed in c.SEEDS]}
        self.complete = {'passed': True, 'GPU_released': True, 'jobs': self.cfg['jobs'], 'remaining': [], 'runtime_gate_sha256': 'fixture'}
        self.release = {'passed': True, 'process_absent': True, 'CUDA_allocation_absent': True, 'owner': self.owner}
        self.started = {'owner': self.owner}
        self.cleanup = {'pid': self.owner['pid'], 'process_absent': True, 'own_compute_absent': True}

    def test_registered_two_pairs_pass(self):
        c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_missing_one_seed_rejected(self):
        self.aggregate['seeds'] = [c.SEEDS[0]]
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_old_native_rejected(self):
        self.pairs[str(c.SEEDS[0])]['runs']['native']['run_id'] = 'r73_oxygen_native'
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_seed_swap_rejected(self):
        self.pairs[str(c.SEEDS[0])]['seed'] = c.SEEDS[1]
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_missing_prefix_equality_rejected(self):
        del self.pairs[str(c.SEEDS[0])]['checks']['step5_normalized_audio']
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_failed_route_check_rejected(self):
        self.pairs[str(c.SEEDS[0])]['checks']['fixed_actual_routes'] = False
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_wrong_call_count_rejected(self):
        self.pairs[str(c.SEEDS[0])]['runs']['fixed']['routed_blocks'] = 400
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_repeated_seed_noise_rejected(self):
        self.pairs[str(c.SEEDS[1])]['noise_cache'] = self.pairs[str(c.SEEDS[0])]['noise_cache']
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_padding_evaluation_rejected(self):
        self.pairs[str(c.SEEDS[0])]['runs']['fixed']['evaluation_indices'].append(98)
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_changed_events_rejected(self):
        self.aggregate['preregistered_events_sha256'] = 'changed'
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_unsafe_video_path_rejected(self):
        self.pairs[str(c.SEEDS[0])]['runs']['native']['video']['file'] = self.cfg['producer_remote']+'/output/../unrelated.mp4'
        with self.assertRaises(ValueError): c.verify_aggregate(self.aggregate, self.pairs, self.cfg)

    def test_release_requires_all_four(self):
        c.verify_release(self.aggregate, self.complete, self.release, self.started, self.cleanup, 'fixture', self.cfg)
        self.complete['jobs'] = self.complete['jobs'][:2]
        with self.assertRaises(ValueError): c.verify_release(self.aggregate, self.complete, self.release, self.started, self.cleanup, 'fixture', self.cfg)

    def test_service_generation_rejected(self):
        self.started = {'owner': {**self.owner, 'pid': 4567}}
        with self.assertRaises(ValueError): c.verify_release(self.aggregate, self.complete, self.release, self.started, self.cleanup, 'fixture', self.cfg)

    def test_missing_release_rejected(self):
        self.release['CUDA_allocation_absent'] = False
        with self.assertRaises(ValueError): c.verify_release(self.aggregate, self.complete, self.release, self.started, self.cleanup, 'fixture', self.cfg)

    def test_complete_gate_hash_rejected(self):
        self.complete['runtime_gate_sha256'] = 'other'
        with self.assertRaises(ValueError): c.verify_release(self.aggregate, self.complete, self.release, self.started, self.cleanup, 'fixture', self.cfg)

    def test_actual_graph_pair_only_mode_changes(self):
        seed = c.SEEDS[0]
        graphs = [c.read(c.ROOT/'configs/graphs'/(self.cfg['runs'][str(seed)][arm]+'.json')) for arm in c.ARMS]
        c.verify_graph_pair(graphs, seed, self.cfg)
        graphs[1]['5']['inputs']['prompt'] += 'changed'
        with self.assertRaises(ValueError): c.verify_graph_pair(graphs, seed, self.cfg)

    def test_geometry_and_physical_timestamps(self):
        value = {'width': 1312, 'height': 736, 'avg_frame_rate': '24/1', 'pts_s': [i/24 for i in range(107)]}
        check_time(value, 107, 1312, 736)
        self.assertEqual((VALID, TOTAL, len(ROLES)), (98, 107, 3))
        value['pts_s'][44] += 1/24
        with self.assertRaises(ValueError): check_time(value, 107, 1312, 736)

    def test_crop_comparison_geometry(self):
        value = {'width': 3840, 'height': 808, 'avg_frame_rate': '24/1', 'pts_s': [i/24 for i in range(98)]}
        check_time(value, 98, 3840, 808)
        value['avg_frame_rate'] = '8/1'
        with self.assertRaises(ValueError): check_time(value, 98, 3840, 808)

    def build_collection_fixture(self, root):
        """Synthetic receipt unit fixture; it contains no generated experimental video."""
        shutil.copytree(c.ROOT/'configs', root/'configs')
        incoming = root/'incoming'
        incoming.mkdir()
        def put(name, value):
            (incoming/name).write_text(json.dumps(value, indent=2))
        for seed in c.SEEDS:
            for arm in c.ARMS:
                run = self.cfg['runs'][str(seed)][arm]
                graph = c.read(root/'configs/graphs'/(run+'.json'))
                put(run+'_graph.json', graph)
                job = {'status': 'success', 'name': run, 'graph_sha256': c.sha(incoming/(run+'_graph.json')),
                       'service_pid': self.owner['pid'], 'service_identity': self.owner['identity'], 'prompt_id': 'synthetic_fixture'}
                history = {'status': {'completed': True, 'status_str': 'success'}, 'prompt': [None, 'synthetic_fixture', graph],
                           'outputs': {'14': {'images': [{'filename': run+'_00001_.mp4', 'subfolder': '', 'type': 'output'}]}}}
                fixed = arm == 'fixed'
                router = {'run_id': run, 'mode': 'mass_preserve' if fixed else 'native', 'alpha': 1., 'radius': 0, 'time_offset': 0,
                    'block_interval_half_open': [0,50], 'step_interval_half_open': [6,15], 'pixel_interval_inclusive': [0,97],
                    'started_calls': 1000, 'completed_calls': 1000, 'completed_forward_calls': 20, 'native_override_calls': 1000,
                    'routed_calls': 450 if fixed else 0, 'calls_by_forward': [50]*20, 'calls_by_block': [20]*50,
                    'routed_by_forward': [0]*6+[50 if fixed else 0]*9+[0]*5, 'routed_by_block': [9 if fixed else 0]*50,
                    'sample_sigmas': [struct.unpack('f',struct.pack('f',float(x)))[0] for x in graph['9']['inputs']['sigmas'].split(',')]}
                condition = {'run_id': run, 'pair_snapshot': {'verified': True}, 'prompt': graph['5']['inputs']['prompt']}
                noise = {'run_id': run, 'signature': {'seed': seed}, 'actual_noise_streams': self.pairs[str(seed)]['noise_cache']['tensor_signatures']}
                for kind, value in [('job',job),('history',history),('router',router),('conditioning',condition),('noise',noise)]:
                    put(run+'_'+kind+'.json', value)
                    self.pairs[str(seed)]['runs'][arm][kind+'_sha256'] = c.sha(incoming/(run+'_'+kind+'.json'))
                (incoming/(run+'.mp4')).write_bytes(b'SYNTHETIC UNIT TEST RECEIPT MEDIA '+run.encode())
                self.pairs[str(seed)]['runs'][arm]['video']['sha256'] = c.sha(incoming/(run+'.mp4'))
            put(f'seed{seed}_PAIR_GATE.json', self.pairs[str(seed)])
            self.aggregate['pair_gate_receipts'][list(c.SEEDS).index(seed)]['sha256'] = c.sha(incoming/f'seed{seed}_PAIR_GATE.json')
        put('AGGREGATE_GATE.json', self.aggregate)
        self.complete['runtime_gate_sha256'] = c.sha(incoming/'AGGREGATE_GATE.json')
        for name,value in [('COMPLETE.json',self.complete),('ROOT_EXIT_RECEIPT.json',self.release),('STARTED.json',self.started),('cleanup.json',self.cleanup),('service.json',self.owner)]: put(name,value)
        shutil.copy2(root/'configs/producer_deploy_manifest.json', incoming/'deploy_manifest.json')
        shutil.copy2(self.cfg['source']['file'], incoming/'source.mp4')
        (root/'CONSUMER_FREEZE.json').write_text(json.dumps({'files':{str(p.relative_to(root)):c.sha(p) for p in (root/'configs').rglob('*') if p.is_file()}}))
        put('COLLECTION.json', {'passed':True,'consumer_freeze_sha256':c.sha(root/'CONSUMER_FREEZE.json'),
                                'files':{p.name:c.sha(p) for p in incoming.iterdir() if p.is_file()}, 'fixture_only':True,
                                'all_four_retained':True,'seeds':list(c.SEEDS),'valid_frames':98,'fps':24})
        return incoming

    def test_end_to_end_collection_and_mutation_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            incoming = self.build_collection_fixture(root)
            with patch.object(c, 'ROOT', root):
                c.verify_collection(incoming)
                (incoming/'source.mp4').write_bytes(b'corrupted')
                with self.assertRaises(ValueError): c.verify_collection(incoming)

    def test_pair_receipt_hash_rejected_even_if_collection_rehashed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            incoming = self.build_collection_fixture(root)
            changed = incoming/f'seed{c.SEEDS[0]}_PAIR_GATE.json'
            changed.write_text(changed.read_text()+'\n')
            receipt = c.read(incoming/'COLLECTION.json')
            receipt['files'][changed.name] = c.sha(changed)
            (incoming/'COLLECTION.json').write_text(json.dumps(receipt))
            with patch.object(c, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'pair gate SHA'):
                    c.verify_collection(incoming)

class Events(unittest.TestCase):
    def complete_review_fixture(self):
        rows = c.read(c.ROOT/'configs/PREREGISTERED_EVENTS.json')['events']
        return {'seed':c.SEEDS[0], 'reviewer':'synthetic_unit_fixture', 'all_valid_frames_inspected':True, 'examined_frames':list(range(98)),
                'task_acceptance':{arm:dict.fromkeys(['status','elderly_woman_identity','cabin_child_mask_retained','action_sequence_retained','framing_and_motion_amplitude'],'PASS') for arm in c.ARMS},
                'events':[{'name':row['name'],'source_frames':row['source_frames'],
                           **{arm:{'status':'UNKNOWN','frames':None,'notes':'synthetic unknown visibility fixture'} for arm in c.ARMS}} for row in rows],
                'terminal_pose_presence':{arm:{'status':'UNKNOWN'} for arm in c.ARMS},
                'whole_clip_quality':{arm:{'status':'UNKNOWN'} for arm in c.ARMS}}

    def test_complete_review_preserves_unknown(self):
        result = validate_completed(self.complete_review_fixture())
        self.assertTrue(all(row['paired_comparison'] is None for row in result['events']))

    def test_incomplete_frame_review_rejected(self):
        value = self.complete_review_fixture();value['examined_frames'].pop()
        with self.assertRaises(ValueError): validate_completed(value)

    def test_registered_source_event_cannot_shift(self):
        value = self.complete_review_fixture();value['events'][0]['source_frames'] = [43,46]
        with self.assertRaises(ValueError): validate_completed(value)

    def test_task_pass_conflict_rejected(self):
        value = self.complete_review_fixture();value['task_acceptance']['native']['elderly_woman_identity'] = 'FAIL'
        with self.assertRaises(ValueError): validate_completed(value)

    def test_visible_shared_source_comparison(self):
        row = evaluate_event([42,45], {'status':'OBSERVED','frames':[60,63]}, {'status':'OBSERVED','frames':[42,45]}, {'native':'PASS','fixed':'PASS'})
        self.assertEqual(row['paired_comparison']['absolute_error_change_frames'], [-21,-12])

    def test_unknown_keeps_null(self):
        row = evaluate_event([42,45], {'status':'OBSERVED','frames':[60,63]}, {'status':'UNKNOWN','frames':None}, {'native':'PASS','fixed':'PASS'})
        self.assertIsNone(row['paired_comparison'])
        self.assertIsNone(row['per_arm_observation']['fixed'])

    def test_task_failure_excludes_primary_comparison(self):
        row = evaluate_event([42,45], {'status':'OBSERVED','frames':[60,63]}, {'status':'OBSERVED','frames':[42,45]}, {'native':'FAIL','fixed':'PASS'})
        self.assertIsNone(row['paired_comparison'])
        self.assertIsNotNone(row['per_arm_observation']['fixed'])

    def test_right_censored_cannot_have_arrival(self):
        with self.assertRaises(ValueError): evaluate_event([42,45], {'status':'OBSERVED','frames':[60,63]}, {'status':'RIGHT_CENSORED','frames':[97,97]}, {'native':'PASS','fixed':'PASS'})

    def test_intervals_exclude_padding(self):
        for value in ([98,99], [-1,2], [5,3], [True,4]):
            with self.assertRaises(ValueError): checked_interval(value)

if __name__ == '__main__': unittest.main()
