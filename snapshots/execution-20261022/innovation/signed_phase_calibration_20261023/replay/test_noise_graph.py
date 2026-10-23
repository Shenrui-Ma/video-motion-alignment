import copy,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
import torch
from noise import HistoricalNoise
from reconstruct import file_sha,pack,tensor_info
from build_graph import build

torch.set_num_threads(1)
class NoiseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        aux=json.loads((Path(__file__).parent/'sources/HOST41_AV_AUX_SOURCE.json').read_text())
        source=next(n['source'] for f in aux['files'] for n in f.get('nodes',[]) if n['name']=='NestedTensor')
        scope={'torch':torch};exec(source,scope);self.N=scope['NestedTensor']
        self.old={k:sys.modules.get(k) for k in ('comfy','comfy.nested_tensor')}
        module=SimpleNamespace(NestedTensor=self.N);sys.modules['comfy']=SimpleNamespace(nested_tensor=module);sys.modules['comfy.nested_tensor']=module
        self.ts=[torch.randn(1,24,4,4,8),torch.randn(1,32,2,5)]
        torch.save({'signature':{'nested':True,'seed':44},'tensors':self.ts},self.root/'noise.pt')
        self.target={'samples':self.N([torch.zeros_like(x) for x in self.ts])}
    def tearDown(self):
        for k,v in self.old.items():
            if v is None:sys.modules.pop(k,None)
            else:sys.modules[k]=v
        self.tmp.cleanup()
    def test_original_nested_noise_value_and_noalias(self):
        n=HistoricalNoise(self.root/'noise.pt',file_sha(self.root/'noise.pt'),44)
        a=n.generate_noise(self.target);b=n.generate_noise(self.target)
        self.assertTrue(torch.equal(pack(a.unbind()),pack(self.ts)))
        a.tensors[0].zero_();self.assertTrue(torch.equal(pack(b.unbind()),pack(self.ts)))
        self.assertEqual(n.signature,tensor_info(pack(self.ts)))
    def test_bad_file_or_seed_rejected(self):
        for sha,seed in [('wrong',44),(file_sha(self.root/'noise.pt'),45)]:
            with self.assertRaises(ValueError):HistoricalNoise(self.root/'noise.pt',sha,seed)
    def test_nonzero_or_geometry_changed_target_rejected(self):
        n=HistoricalNoise(self.root/'noise.pt',file_sha(self.root/'noise.pt'),44)
        self.target['samples'].tensors[0][0,0,0,0,0]=1
        with self.assertRaises(ValueError):n.generate_noise(self.target)
        self.target['samples'].tensors[0]=torch.zeros(1,24,1,4,8)
        with self.assertRaises(ValueError):n.generate_noise(self.target)

class GraphTests(unittest.TestCase):
    def setUp(self):
        self.g={'1':{'class_type':'UNETLoader','inputs':{'unet_name':'frozen','weight_dtype':'default'}},'41':{'class_type':'MiniMaxH3SigmaShift','inputs':{'model':['1',0],'shift_video':12.,'shift_audio':3.}},'7':{'class_type':'BasicGuider','inputs':{}},'9':{'class_type':'ManualSigmas','inputs':{'sigmas':'exact historical value'}},'50':{'class_type':'H3TemporalRouter','inputs':{'mode':'native','alpha':1.,'radius':0,'time_offset':0,'start_frame':0,'end_frame':104,'block_start':0,'block_end':50,'step_start':6,'step_end':15}},'52':{'class_type':'H3X0Readout','inputs':{}},'6':{'inputs':{'noise_seed':2026101701}}}
        self.p={'case':'short_0358','method':'native','assets_verified':True,'source_identity_verified':True,'source_identity_evidence':{'cache_manifest_sha256':'cache'}}
        self.c={'task_root':'/task','cache_manifest':'/cache/manifest.json','cache_manifest_sha256':'cache'}
        self.c.update({k:'/task/inputs/'+k for k in ('state_file','historical_x0_file','noise_file','provenance_file')})
        self.c.update({k:'sha' for k in ('state_sha256','historical_x0_sha256','noise_sha256','provenance_sha256')})
    def test_science_exact_and_no_original_writer(self):
        before=copy.deepcopy(self.g);g,diff=build(self.g,self.p,self.c)
        self.assertEqual(self.g,before)
        for n in ('1','41','9'):self.assertEqual(g[n],before[n])
        self.assertEqual(g['50']['inputs']['schedule'],'fixed');self.assertEqual(g['50']['inputs']['alpha'],1.)
        self.assertEqual(g['7']['inputs']['model'],['50',0])
        self.assertFalse(any('X0Readout' in n['class_type'] or 'Timing' in n['class_type'] or 'VAE' in n['class_type'] for n in g.values()))
        self.assertEqual(diff['physical_model_calls'],2)
        self.assertTrue(all(p.startswith('/task/') for p in diff['all_new_writer_paths']))
    def test_drift_or_nonisolated_path_rejected(self):
        for k,value in [('alpha',.25),('end_frame',106),('step_start',0)]:
            g=copy.deepcopy(self.g);g['50']['inputs'][k]=value
            with self.assertRaises(ValueError):build(g,self.p,self.c)
        c={**self.c,'noise_file':'/old/noise.pt'}
        with self.assertRaises(ValueError):build(self.g,self.p,c)
    def test_wrong_cache_binding_rejected(self):
        with self.assertRaises(ValueError):build(self.g,self.p,{**self.c,'cache_manifest_sha256':'wrong'})

if __name__=='__main__':unittest.main()
