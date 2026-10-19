import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from common import verify_gate, verify_release, verify_graph_control
from media import check_time
from review import delay_interval, validate_completed

P = ROOT.parent
OLD = P/'h3-ive-long0174-guidance-metrics-r107-20261019'
PRODUCER = P/'h3-timing-ive-long0174-spatial-marginal-r111-20261019'


class ContractTests(unittest.TestCase):
    def setUp(self):
        prior = json.loads((OLD/'configs/contract.json').read_text())
        oldcase = prior['cases']['long_0174']
        self.cfg = {'producer_remote': '/data4/researcher/h3_runs/timing_ive_long0174_spatial_marginal_r111_20261019',
            'fixed_producer_remote': prior['producer_remote'],
            'run_id': 'r111_long_0174_seed2026101701_forced', 'native_run_id': oldcase['run_id'],
            'historical_media': {'native': oldcase['native_video']},
            'first_six_predictions': oldcase['first_six_predictions'],
            'fixed_binding': json.loads((PRODUCER/'design/R107_FIXED_BINDING.json').read_text()),
            'producer_runtime_sha256': 'test-runtime'}
        self.g = json.loads((OLD/'incoming/long_0174/PAIR_RUNTIME_GATE.json').read_text())
        self.g['schema'] = 'r111-historical-native-paired-runtime-gate-v1'
        self.g['runtime_profile_sha256'] = 'test-runtime'
        self.g['checks']['actual_R107_fixed_comparison'] = True
        self.g['fixed_comparison'] = {'passed': True, 'binding': self.cfg['fixed_binding'],
                                     'checks': {'actual_gate': True, 'fixed_exact_release': True}}
        self.g['runs']['forced']['run_id'] = self.cfg['run_id']
        self.g['runs']['forced']['video']['file'] = self.cfg['producer_remote']+'/output/'+self.cfg['run_id']+'_00001_.mp4'
        self.current = json.loads((PRODUCER/'configs/graphs'/f'{self.cfg["run_id"]}.json').read_text())
        self.fixed = json.loads((PRODUCER/'design/R107_GRAPH.json').read_text())

    def test_expected_gate(self):
        verify_gate(self.g, self.cfg)

    def test_all_independent_execution_rejections(self):
        changes = (
            lambda g: g.update(passed=False),
            lambda g: g.update(source_id='other'),
            lambda g: g.update(runtime_profile_sha256='wrong'),
            lambda g: g.update(valid_frames=158),
            lambda g: g['checks'].pop('actual_raw_AV_noise_equal_Native'),
            lambda g: g['checks'].update(sampled_finite=False),
            lambda g: g['runs']['native']['video'].update(sha256='wrong'),
            lambda g: g['runs']['forced'].update(routed_blocks=0),
            lambda g: g['runs']['forced'].update(run_id='other'),
            lambda g: g['runs']['forced']['video'].update(file='/tmp/other.mp4'),
            lambda g: g['runs']['forced']['video']['properties'].update(nb_read_frames='145'),
            lambda g: g['prefix_tensor_comparison'][0].update(video=False),
            lambda g: g['prefix_tensor_comparison'][0].update(parent_file_sha256='other'),
            lambda g: g['fixed_comparison']['binding'].update(video_sha256='other'),
            lambda g: g['fixed_comparison']['checks'].update(fixed_exact_release=False))
        for change in changes:
            with self.subTest(change=change):
                value = copy.deepcopy(self.g)
                change(value)
                with self.assertRaises(ValueError):
                    verify_gate(value, self.cfg)

    def test_only_registered_routing_graph_diff(self):
        verify_graph_control(self.current, self.fixed, self.cfg)
        for node, key, value in [('5', 'prompt', 'different task'), ('9', 'sigmas', '1,0'),
                                 ('50', 'alpha', 3.0), ('50', 'step_start', 0)]:
            with self.subTest(node=node, key=key):
                graph = copy.deepcopy(self.current)
                graph[node]['inputs'][key] = value
                with self.assertRaises(ValueError):
                    verify_graph_control(graph, self.fixed, self.cfg)

    def test_exact_release(self):
        owner = self.g['service_owner']
        complete = {'passed': True, 'GPU_released': True, 'jobs': [self.cfg['run_id']],
                    'remaining': [], 'gates': {'long_0174': {'sha256': 'gate'}}}
        release = {'passed': True, 'process_absent': True, 'CUDA_allocation_absent': True, 'owner': owner}
        started = {'owner': owner}
        cleanup = {'pid': owner['pid'], 'process_absent': True, 'own_compute_absent': True}
        verify_release(self.g, complete, release, started, cleanup, 'gate', self.cfg)
        for data, key, value in [(complete, 'GPU_released', False), (release, 'process_absent', False),
                                 (cleanup, 'pid', owner['pid']+1), (cleanup, 'own_compute_absent', False)]:
            old = data[key]
            data[key] = value
            with self.assertRaises(ValueError):
                verify_release(self.g, complete, release, started, cleanup, 'gate', self.cfg)
            data[key] = old

    def test_physical_time(self):
        value = {'width': 5120, 'height': 808, 'avg_frame_rate': '24/1',
                 'pts_s': [i/24 for i in range(145)]}
        check_time(value, 145, 5120, 808)
        value['pts_s'][44] += 1/24
        with self.assertRaises(ValueError):
            check_time(value, 145, 5120, 808)

    def test_preregistered_interval_rule(self):
        self.assertEqual(delay_interval([47, 53], [61, 65])['frames'], [8, 18])
        with self.assertRaises(ValueError):
            delay_interval([47, 53], [150, 155])

    def test_review_requires_all_frames_and_same_joint_event(self):
        report = json.loads((ROOT/'configs/PREREGISTERED_EVENTS.json').read_text())
        report.update(all_valid_frames_inspected=True, examined_spatial_frames=list(range(145)))
        for row in report['events']:
            row['spatial_status'] = 'UNKNOWN'
        report['terminal_motion']['spatial_status'] = 'RIGHT_CENSORED'
        self.assertTrue(validate_completed(report))
        report['events'][2]['definition'] = 'arm lift only'
        with self.assertRaises(ValueError):
            validate_completed(report)


if __name__ == '__main__':
    unittest.main()
