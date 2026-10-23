import copy,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from nodes import validate_contract,H3LivePhaseObservation
from build_graphs import build,contract,sha,ROOT

HERE=Path(__file__).parent
class ContractTests(unittest.TestCase):
    def setUp(self):self.native=json.loads((HERE/'plans/native_contract.json').read_text())
    def test_frozen_pair_valid(self):
        for method in ('native','global_weak'):validate_contract(json.loads((HERE/'plans'/f'{method}_contract.json').read_text()))
    def test_contract_changes_fail(self):
        for key,value in [('method','early'),('seed',1),('frames',105),('valid_frames',107),('steps',[8,19]),('layer',26),('heads',55),('probes',7),('model_checkpoint_sha256','different'),('cache_manifest_sha256','different'),('noise_file_sha256','different'),('noise_tensor_sha256','different'),('calibration_plan_sha256','different'),('output_dir','/tmp'),('trajectory_id','other')]:
            with self.subTest(key=key):
                s=copy.deepcopy(self.native);s[key]=value
                with self.assertRaises(ValueError):validate_contract(s)
    def test_sigma_and_method_cannot_change_together(self):
        s=copy.deepcopy(self.native);s['sigmas_video'][9]+=.001
        with self.assertRaises(ValueError):validate_contract(s)
        s=copy.deepcopy(self.native);s['router']['alpha']=.25
        with self.assertRaises(ValueError):validate_contract(s)
    def test_node_clone_wrapper_only(self):
        class Model:
            def clone(self):self.child=Model();return self.child
            def add_wrapper_with_key(self,*args):self.wrapper=args
        m=Model();fake=SimpleNamespace(WrappersMP=SimpleNamespace(SAMPLER_SAMPLE='SAMPLER_SAMPLE'))
        p=HERE/'plans/native_contract.json'
        with patch.dict(sys.modules,{'comfy.patcher_extension':fake}):result=H3LivePhaseObservation().apply(m,str(p),sha(p))
        self.assertIs(result[0],m.child);self.assertFalse(hasattr(m,'wrapper'));self.assertEqual(m.child.wrapper[0],'SAMPLER_SAMPLE');self.assertFalse(m.child.wrapper[2].used)
    def test_contract_hash_fails_before_clone(self):
        with patch.dict(sys.modules,{'comfy.patcher_extension':SimpleNamespace(WrappersMP=object)}):
            with self.assertRaises(ValueError):H3LivePhaseObservation().apply(None,str(HERE/'plans/native_contract.json'),'wrong')
    def test_graph_frozen_and_only_new_paths(self):
        for method in ('native','global_weak'):
            g=json.loads((HERE/'plans'/f'{method}_graph.json').read_text());d=json.loads((HERE/'plans'/f'{method}_GRAPH_DIFF.json').read_text());c=json.loads((HERE/'plans'/f'{method}_contract.json').read_text())
            self.assertEqual(g['8']['inputs']['sampler_name'],'euler');self.assertEqual(g['10']['class_type'],'SamplerCustomAdvanced');self.assertEqual(g['10']['inputs']['latent_image'],['5',1]);self.assertEqual(g['7']['inputs']['model'],['52',0])
            self.assertEqual(g['52']['inputs']['contract_sha256'],sha(HERE/'plans'/f'{method}_contract.json'))
            self.assertEqual(g['50']['inputs']['mode'],c['router']['mode']);self.assertEqual(g['50']['inputs']['alpha'],c['router']['alpha'])
            self.assertTrue(all(p.startswith(ROOT+'/') for p in d['new_writer_paths']))
            self.assertEqual(d['extra_model_forward_count'],0);self.assertFalse(any(x['class_type'] in d['removed_old_writer_classes'] for x in g.values()))
            self.assertEqual(g['11']['inputs']['samples'],['10',0]);self.assertEqual(g['12']['inputs']['samples'],['10',0])

if __name__=='__main__':unittest.main()
