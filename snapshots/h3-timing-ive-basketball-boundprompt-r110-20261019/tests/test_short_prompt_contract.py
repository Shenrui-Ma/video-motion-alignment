import copy, importlib.util, sys, tempfile, unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'scripts'))
import r110_contract as c

class ShortPromptContract(unittest.TestCase):
    def test_r109_actual_comparator_and_numerical_change_rejection(self):
        graph=c.read(R/'configs/graphs'/f'{c.RUN_ID}.json')
        binding=c.validate_r109_comparator(R,graph)
        self.assertEqual(binding['run_id'],'r109_short_0114_seed2026101701_native')
        changed=copy.deepcopy(graph);changed['10']['inputs']['sampler_name']='res_multistep'
        with self.assertRaises(ValueError):c.validate_r109_comparator(R,changed)

    def test_predecessor_and_exact_gpu3_are_frozen(self):
        prior=c.read(R/'configs/predecessor.json');runtime=c.read(R/'configs/runtime.json')
        self.assertEqual((prior['service_pid'],prior['service_start_ticks']),(14789,'2641156049'))
        self.assertEqual((runtime['expected_gpu_index'],runtime['gpu_index'],runtime['port']),(3,3,8574))
        self.assertEqual(prior['gpu_uuid'],runtime['gpu_uuid'])

    def test_exact_prompt_and_same_visual_sampling_graph(self):
        jobs,order=c.registry();case=jobs[order[0]]['case']
        old=c.read(R/case['parent_graph']);new=c.read(R/'configs/graphs'/f'{order[0]}.json')
        def diff(a,b,path=()):
            if isinstance(a,dict) and isinstance(b,dict):
                self.assertEqual(set(a),set(b))
                return sum((diff(a[k],b[k],path+(k,)) for k in a),[])
            return [path] if a!=b else []
        expected={('5','inputs','prompt'),('5','inputs','run_id'),('51','inputs','source_run_id'),('6','inputs','pair_id'),('14','inputs','filename_prefix')}
        expected|={(node,'inputs','run_id') for node in ['6','50','51','52']}
        expected|={(node,'inputs',key) for node,key in [('5','audit_dir'),('6','audit_dir'),('50','audit_dir'),('51','source_audit_dir'),('52','output_dir')]}
        self.assertEqual(set(diff(old,new)),expected)
        self.assertEqual(new['5']['inputs']['prompt'],'Edit <Video 1> by changing only the basketball into a neon-lit basketball. Keep the original player, dribbling actions, camera framing, scene, and timing.')
        self.assertEqual(case['valid_frame_count'],105)

    def test_graph_rejects_unregistered_sampler_change(self):
        jobs,_=c.registry();case=jobs[c.RUN_ID]['case'];g=c.expected_graph(R,case)
        self.assertEqual(g['9'],c.read(R/case['parent_graph'])['9'])
        self.assertEqual(g['50']['inputs']['mode'],'native')
        with self.assertRaises(ValueError):c.validate_router('mass_preserve',1.,0,0,0,104,0,50,6,15,c.RUN_ID,str(c.REMOTE/'audit/router'))

    def test_actual_parent_history_prompt_and_video_binding(self):
        hist=c.read(R/'design/R100_ACTUAL/r100_short_0114_seed2026101701_native_history.json')
        graph=c.read(R/'configs/parent_graphs/r100_actual_native.json')
        self.assertEqual(hist['prompt'][2],graph)
        self.assertTrue(hist['status']['completed'])
        gate=c.read(R/'design/R100_ACTUAL/PAIR_RUNTIME_GATE.json')
        self.assertTrue(gate['passed'])
        self.assertEqual(gate['runs']['native']['video']['sha256'],'464544e0c13a67fcc9c461055215c5da8572a0b4e7b15b0404c3b462aec7a70b')

    def test_video_only_geometry_and_text_change_allowance(self):
        sys.path.insert(0,str(R/'analysis/postrun'))
        import verify_native as v
        current=c.read(R/'design/R100_ACTUAL/r100_short_0114_seed2026101701_native_conditioning.json')
        plan=c.read(R/'design/R100_ACTUAL/router.json')['validated_layout']
        case=c.registry()[0][c.RUN_ID]['case']
        self.assertTrue(v.reference_geometry_matches(current,case,plan))
        changed=copy.deepcopy(current);changed['conditioning_embedding']['sha256']='different text'
        self.assertTrue(all(v.compare_parent_conditions(changed,current).values()))
        changed['native_vae_calls'][0]['latent']['sha256']='changed visual'
        self.assertFalse(v.compare_parent_conditions(changed,current)['actual_prepared_RGB_and_clean_VAE'])

if __name__=='__main__':unittest.main()
