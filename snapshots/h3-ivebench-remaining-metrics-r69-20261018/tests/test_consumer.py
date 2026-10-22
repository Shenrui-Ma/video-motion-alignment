import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import common as c
import bindings as b
import collect_pair
import score_one
import track_one
import make_showcase

def fixture_gate(source):
    e=c.entry(source);protocol=e['input_protocol']
    keys=['producer_seal','actual_runtime_device','actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal']
    keys += [m+'_'+suffix for m in c.METHODS for suffix in ('history','service','shared_conditions','actual_execution_counts','actual_layout','sampled_finite','actual_noise_cache')]
    gate={'schema':'r69-paired-runtime-gate-v1','passed':True,'source_id':source,'prompt_version':'P0','checks':{k:True for k in keys},'runtime_profile_sha256':'a'*64,
          'prefix_tensor_comparison':[{'step_zero_based':i,'video':True,'audio':True} for i in range(6)],
          'condition_tensor_files':[{'file':f'blob{i}.pt','sha256':'a'*64,'tensor_signature':{'sha256':'b'*64}} for i in range(6)],'runs':{}}
    for method in c.METHODS:
        gate['runs'][method]={'run_id':f'r69_{source}_seed2026101701_{method}','valid_frames':protocol['effective_frame_count'],'NFE':20,'Euler_updates':20,'routed_blocks':0 if method=='native' else 450,'evaluation_crop_xywh':[16,8,1280,720],
            'video':{'sha256':'a'*64,'properties':{'width':1312,'height':736,'nb_read_frames':str(protocol['h3_frame_count']),'avg_frame_rate':'24/1'}},
            'snapshots':[{'file':name,'bytes':32,'sha256':'a'*64} for name in [f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt']],
            'job_wall_seconds':100.,'router_file_sha256':'a'*64,'history_sha256':'a'*64,'job_sha256':'a'*64}
    return gate

class SourceBindings(unittest.TestCase):
    def test_exact_runtime_inheritance(self):
        c.verify_runtime()
        b.official.verify_vendor()

    def test_fixed_four_sources_and_lengths(self):
        self.assertEqual([(c.entry(source)['input_protocol']['h3_frame_count'], c.entry(source)['input_protocol']['effective_frame_count']) for source in c.PAIRS], [(90, 86), (90, 74), (90, 78), (90, 89)])

    def test_actual_provenance_all_four(self):
        for source in c.PAIRS:
            record = c.read(ROOT / 'inputs' / (source + '_provenance.json'))
            b.validate_provenance(record, c.entry(source), record['video_sha256'], record['input_frame_md5'])

    def test_reject_padding_as_valid(self):
        source = c.PAIRS[0]; record = c.read(ROOT / 'inputs' / (source + '_provenance.json')); record['effective_frame_count'] = 73
        with self.assertRaises(ValueError):
            b.validate_provenance(record, c.entry(source), record['video_sha256'], record['input_frame_md5'])

    def test_reject_changed_source_prompt(self):
        source = c.PAIRS[0]; record = c.read(ROOT / 'inputs' / (source + '_provenance.json')); record['prompt'] += ' wave earlier'
        with self.assertRaises(ValueError):
            b.validate_provenance(record, c.entry(source), record['video_sha256'], record['input_frame_md5'])

    def test_reject_changed_time_map(self):
        source = c.PAIRS[0]; record = c.read(ROOT / 'inputs' / (source + '_provenance.json')); record['input_to_original_frame'][0] = 1
        with self.assertRaises(ValueError):
            b.validate_provenance(record, c.entry(source), record['video_sha256'], record['input_frame_md5'])

    def test_reject_changed_pixel(self):
        source = c.PAIRS[0]; record = c.read(ROOT / 'inputs' / (source + '_provenance.json')); pixels = record['input_frame_md5'].copy(); pixels[0] = 'changed'
        with self.assertRaises(ValueError):
            b.validate_provenance(record, c.entry(source), record['video_sha256'], pixels)

    def test_actual_crop_manifests(self):
        for source in c.PAIRS:
            row = c.source_row(source)
            self.assertEqual(row['score_frame_indices'], list(range(c.entry(source)['input_protocol']['effective_frame_count'])))
            self.assertEqual(row['selection_sha256'], c.sha(c.SELECTION))

    def test_host_manifest_has_root_specific_path(self):
        source = c.PAIRS[0]
        path = c.source_manifest(source)
        self.assertTrue(path.name.startswith('SOURCE_INPUTS_HOST_'))
        self.assertEqual(c.read(path), c.source_row(source))

    def test_full_dynamic_shapes(self):
        for total in (73, 107, 124):
            b.validate_full({'width': 1312, 'height': 736, 'count': total, 'pts_s': [i / 24 for i in range(total)], 'avg_frame_rate': '24/1'}, total)

    def test_full_retiming_rejected(self):
        with self.assertRaises(ValueError):
            b.validate_full({'width': 1312, 'height': 736, 'count': 73, 'pts_s': [.01 + i / 24 for i in range(73)], 'avg_frame_rate': '24/1'}, 73)

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            c.entry('short_0210')

class PairGate(unittest.TestCase):
    def test_reject_missing_or_reordered_actual_captures(self):
        for mutation in ('remove','reorder','bad_hash'):
            gate=fixture_gate(c.PAIRS[0]);rows=gate['runs']['forced']['snapshots']
            if mutation=='remove':rows.pop()
            elif mutation=='reorder':rows[0],rows[1]=rows[1],rows[0]
            else:rows[0]['sha256']='bad'
            with self.assertRaises(ValueError):collect_pair.validate_gate(gate,c.PAIRS[0])

    def test_reject_unverified_condition_blob_or_prefix_detail(self):
        for mutation in ('blob','prefix','count_check'):
            gate=fixture_gate(c.PAIRS[0])
            if mutation=='blob':gate['condition_tensor_files'].pop()
            elif mutation=='prefix':gate['prefix_tensor_comparison'][2]['audio']=False
            else:del gate['checks']['forced_actual_execution_counts']
            with self.assertRaises(ValueError):collect_pair.validate_gate(gate,c.PAIRS[0])

    def test_reject_bad_nfe_or_efficiency(self):
        for key,value in [('NFE',19),('Euler_updates',21),('job_wall_seconds',float('nan'))]:
            gate=fixture_gate(c.PAIRS[0]);gate['runs']['native'][key]=value
            with self.assertRaises(ValueError):collect_pair.validate_gate(gate,c.PAIRS[0])

    def test_actual_router_schedule_required(self):
        router={'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450,
                'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':[50 if 6<=i<15 else 0 for i in range(20)],'routed_by_block':[9]*50,
                'expected_sampling_steps':20,'pixel_interval_inclusive':[0,89],'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],
                'alpha':1.,'radius':0,'time_offset':0,'mode':'mass_preserve',
                'validated_layout':{'latent_interval_half_open':[0,27],'frame_rows':943,'query_interval_half_open':[1,2],'target_video_segment':[1,2],'key_interval_half_open':[3,4],'reference_video_segment':[3,4]}}
        collect_pair.validate_router(router,'forced')
        router['routed_by_forward'][6]=0
        with self.assertRaises(ValueError):collect_pair.validate_router(router,'forced')

    def test_all_dynamic_pair_gates(self):
        for source in c.PAIRS:
            collect_pair.validate_gate(fixture_gate(source), source)

    def test_reject_failed_actual_condition(self):
        gate = fixture_gate(c.PAIRS[0]); gate['checks']['actual_clean_conditions_equal'] = False
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_missing_actual_noise(self):
        gate = fixture_gate(c.PAIRS[0]); del gate['checks']['actual_initial_AV_noise_equal']
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_failed_prefix(self):
        gate = fixture_gate(c.PAIRS[0]); gate['checks']['Native_prefix_0_5_equal'] = False
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_wrong_total(self):
        gate = fixture_gate(c.PAIRS[0]); gate['runs']['native']['video']['properties']['nb_read_frames'] = '89'
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_wrong_valid(self):
        gate = fixture_gate(c.PAIRS[0]); gate['runs']['native']['valid_frames'] = 73
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_wrong_method_route(self):
        gate = fixture_gate(c.PAIRS[0]); gate['runs']['forced']['routed_blocks'] = 0
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_old_five_task_gate(self):
        gate = fixture_gate(c.PAIRS[0]); gate['schema'] = 'r63-paired-runtime-gate-v1'
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

class RuntimeAndReporting(unittest.TestCase):
    def test_foreign_many_cards_ignored_for_own_cap(self):
        rows = [{'uid': 7, 'gpu_uuid': 'GPU-' + str(i)} for i in range(5)] + [{'uid': 4, 'gpu_uuid': 'GPU-own1'}]
        track_one.check_owned_cap(rows, 'GPU-own2', 4)

    def test_own_third_card_rejected(self):
        with self.assertRaises(track_one.ResourceUnavailable):
            track_one.check_owned_cap([{'uid': 4, 'gpu_uuid': 'GPU-1'}, {'uid': 4, 'gpu_uuid': 'GPU-2'}], 'GPU-3', 4)

    def test_same_runtime_and_hardware_required(self):
        keys = ['torch_version', 'cuda_version', 'official_commit', 'tracker', 'checkpoint_sha256', 'selection_sha256', 'source_prepared_sha256', 'source_score_sha256', 'effective_frame_count', 'score_frame_indices']
        source = {key: 'same' for key in keys}; source['admission_before_cuda'] = {'hostname': 'host41', 'gpu_name': 'RTX'}
        score_one.check_runtime_pair(source, copy.deepcopy(source))
        for key in keys:
            target = copy.deepcopy(source); target[key] = 'different'
            with self.assertRaises(ValueError): score_one.check_runtime_pair(source, target)
        for key in ('hostname', 'gpu_name'):
            target = copy.deepcopy(source); target['admission_before_cuda'][key] = 'different'
            with self.assertRaises(ValueError): score_one.check_runtime_pair(source, target)

    def test_tracker_numerical_entry_unchanged(self):
        import run_tracks
        original = run_tracks.main
        for source in c.PAIRS:
            tracker = b.configure_tracker(source)
            self.assertIs(tracker.main, original)
            self.assertEqual(tracker.SELECTION_SHA, c.sha(c.SELECTION))

    def test_score_numerical_entry_unchanged(self):
        import score_cached_tracks
        original = score_cached_tracks.score
        self.assertIs(b.configure_score().score, original)

    def test_pending_keeps_four_denominator(self):
        report = make_showcase.summary()
        self.assertEqual(report['fixed_denominator'], 5)
        self.assertEqual([row['source'] for row in report['rows']], ['short_0210']+list(c.PAIRS))
        for method in c.METHODS:
            self.assertIsNone(report['means'][method]['mean_if_all_five_valid'])

if __name__ == '__main__':
    unittest.main()
