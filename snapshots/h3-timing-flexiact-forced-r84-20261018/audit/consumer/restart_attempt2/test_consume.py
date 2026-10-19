import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('r84_consumer', Path(__file__).with_name('consume.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class ConsumerContract(unittest.TestCase):
    def fixture(self):
        case = next(v['case'] for v in m.registry()[0].values() if v['source_id'] == m.SOURCES[0])
        checks = {k: True for k in ('Native_prefix_0_5_equal', 'actual_initial_AV_noise_equal',
            'prompt_equal', 'input_video_equal', 'native_vae_calls_equal', 'qwen_presentation_equal',
            'tokenization_before_vision_expansion_equal', 'conditioning_embedding_equal',
            'token_tags_equal', 'target_latent_shapes_equal', 'packed_layout_equal')}
        gate = dict(schema='r84-historical-native-paired-runtime-gate-v1', source_id=m.SOURCES[0],
                    passed=True, checks=checks, runs={})
        for arm in ('native', 'forced'):
            name = case['baseline_run'] if arm == 'native' else case['run_id']
            root = Path(case['baseline_root']) if arm == 'native' else m.REMOTE
            gate['runs'][arm] = dict(run_id=name, valid_frames=147, NFE=20, Euler_updates=20,
                routed_blocks=0 if arm == 'native' else 450,
                video=dict(file=str(root/'output'/(name+'_00001_.mp4')), sha256='unused'))
        return case, gate

    def test_actual_gate_accepts_registered_pair(self):
        c, g = self.fixture(); self.assertEqual(m.checked_gate(g, m.SOURCES[0]), c)

    def test_false_missing_or_non_boolean_check_rejected(self):
        for operation in ('false', 'missing', 'truthy'):
            c, g = self.fixture()
            if operation == 'missing': del g['checks']['prompt_equal']
            else: g['checks']['prompt_equal'] = False if operation == 'false' else 'True'
            with self.subTest(operation=operation), self.assertRaises(ValueError): m.checked_gate(g, m.SOURCES[0])

    def test_wrong_identity_or_count_rejected(self):
        for key, val in (('run_id', 'unrelated'), ('routed_blocks', 0), ('valid_frames', 158), ('NFE', 8)):
            c, g = self.fixture(); g['runs']['forced'][key] = val
            with self.subTest(key=key), self.assertRaises(ValueError): m.checked_gate(g, m.SOURCES[0])

    def test_wrong_run_output_path_rejected(self):
        c, g = self.fixture(); g['runs']['forced']['video']['file'] = str(m.REMOTE/'output/other_00001_.mp4')
        with self.assertRaises(ValueError): m.checked_gate(g, m.SOURCES[0])

    def test_input_hash_failure_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for i in range(3):
                p=Path(tmp)/str(i); p.write_bytes(bytes([i])); paths.append(p)
            c, g=self.fixture(); c=copy.deepcopy(c)
            c['video_sha256']=m.sha(paths[0]); g['runs']['native']['video']['sha256']=m.sha(paths[1]); g['runs']['forced']['video']['sha256']=m.sha(paths[2])
            m.checked_media_inputs(g,c,paths)
            paths[1].write_bytes(b'altered')
            with self.assertRaises(ValueError): m.checked_media_inputs(g,c,paths)

    def probe(self):
        return dict(streams=[dict(width=1152,height=768,nb_read_frames='158',avg_frame_rate='24/1')],
                    frames=[dict(best_effort_timestamp_time=f'{i/24:.6f}') for i in range(158)])

    def test_exact_physical_timeline(self):
        data=self.probe()
        with patch.object(m.subprocess,'check_output',return_value=json.dumps(data).encode()):
            self.assertEqual(m.properties(Path('unopened.mp4'))['nb_read_frames'],'158')

    def test_shifted_or_changed_frame_geometry_rejected(self):
        for operation in ('start', 'missing', 'fps'):
            data=self.probe()
            if operation=='start': data['frames'][0]['best_effort_timestamp_time']='0.041667'
            elif operation=='missing': data['frames'].pop()
            else: data['streams'][0]['avg_frame_rate']='25/1'
            with self.subTest(operation=operation), patch.object(m.subprocess,'check_output',return_value=json.dumps(data).encode()), self.assertRaises(ValueError):
                m.properties(Path('unopened.mp4'))


if __name__=='__main__': unittest.main()
