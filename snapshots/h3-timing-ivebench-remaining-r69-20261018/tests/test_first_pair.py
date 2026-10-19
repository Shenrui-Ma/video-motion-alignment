import ast,copy,json,math,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import execution_gate as gate,preflight
from r69_contract import registry,read,sha

class ContractTests(unittest.TestCase):
 def test_graph_static(self):self.assertTrue(preflight.check(ROOT)['passed'])
 def test_same_prompt_and_numerical_input(self):
  jobs,order=registry(ROOT)
  for n,f in zip(order[::2],order[1::2]):
   a=read(ROOT/'configs/graphs'/(n+'.json'));b=read(ROOT/'configs/graphs'/(f+'.json'))
   for node in ('6','50','51','52'):
    a[node]['inputs']['run_id']='RUN';b[node]['inputs']['run_id']='RUN'
   a['14']['inputs']['filename_prefix']=b['14']['inputs']['filename_prefix']='RUN'
   for k in ('mode','step_start','step_end'):a['50']['inputs'][k]=b['50']['inputs'][k]
   self.assertEqual(a,b)
 def test_no_duplicate_top_functions(self):
  for p in (ROOT/'scripts').glob('*.py'):
   names=[n.name for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
   self.assertEqual(len(names),len(set(names)),str(p))
 def test_binding_all_launches(self):
  for name in ('service','launch_remote','start_controller'):
   text=(ROOT/'scripts'/f'{name}.py').read_text();self.assertIn('bind_child',text)
  self.assertIn('bind_or_reap',(ROOT/'scripts/process_identity.py').read_text())
 def test_gate_refusal_and_scope(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'configs').mkdir();(root/'audit').mkdir();(root/'configs/runtime.json').write_text(json.dumps({'gpu_uuid':'GPU-test'}))
   order=['native0','forced0','native1','forced1']
   with patch.object(gate,'registry',return_value=({},order)):
    with self.assertRaises(FileNotFoundError):gate.admitted_job('native0',root)
    a={'schema':'r69-first-pair-capacity-trial-v1','root_approved':True,'runtime_profile_sha256':sha(root/'configs/runtime.json'),'main_gpu_uuid':'GPU-test','allowed_runs':order[:2],'required_free_bytes':20*1024**3,'reserve_vram_gib':8,'capacity_status':'ACTUAL_FULL_TRAJECTORY_PENDING'}
    gate.atomic(root/'audit/ROOT_FIRST_PAIR_APPROVAL.json',a)
    self.assertTrue(gate.admitted_job('native0',root));self.assertTrue(gate.admitted_job('forced0',root));self.assertFalse(gate.admitted_job('native1',root))
    receipt=root/'analysis/postrun/short_0230/PAIR_RUNTIME_GATE.json';gate.atomic(receipt,{'passed':True,'runtime_profile_sha256':a['runtime_profile_sha256'],'source_id':'short_0230'})
    c={'schema':'r69-continue-after-first-pair-v1','root_approved':True,'runtime_profile_sha256':a['runtime_profile_sha256'],'pair_gate_sha256':sha(receipt),'allowed_runs':order[2:]};gate.atomic(root/'audit/CONTINUE_AFTER_FIRST_PAIR.json',c)
    self.assertTrue(gate.admitted_job('native1',root));receipt.write_text('{}')
    with self.assertRaises(ValueError):gate.admitted_job('forced1',root)
 def test_runtime_change_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'configs').mkdir();(root/'audit').mkdir();(root/'configs/runtime.json').write_text('{}')
   gate.atomic(root/'audit/ROOT_FIRST_PAIR_APPROVAL.json',{'schema':'r69-first-pair-capacity-trial-v1','root_approved':True,'runtime_profile_sha256':'old','main_gpu_uuid':'GPU-test'})
   with patch.object(gate,'registry',return_value=({},['a','b'])):
    with self.assertRaises(ValueError):gate.approval(root)

class MathematicsTests(unittest.TestCase):
 @staticmethod
 def functions(path):
  tree=ast.parse(path.read_text());names={'temporal_neighborhood','flash_attention_lse','_aligned_attention','reference_value_component','route_attention','_bounded_stats','_value_split_stats'}
  nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
  env={'math':math,'MODES':('native','diagnostic','mass_preserve','hard_route','dynamic_residual','static_component'),'VALUE_SPLIT_MODES':('dynamic_residual','static_component')};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env);return env
 def test_direct_route_equals_previous_full_math(self):
  a=ast.parse((ROOT/'extensions/H3TemporalRouter/core.py').read_text());b=ast.parse((ROOT/'source_snapshot/r59/sealed_r3_core.py').read_text())
  get=lambda t:ast.dump(next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='route_attention'),include_attributes=False)
  self.assertEqual(get(a),get(b))
 def test_actual_dense_oracle_group_mass_and_aligned_values(self):
  import torch
  torch.set_num_threads(1);torch.manual_seed(123)
  q,k,v=[torch.randn(1,2,15,4) for _ in range(3)]
  def attention(q,k,v):
   logits=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1]);return logits.softmax(-1)@v,logits.logsumexp(-1)
  plan={'query_interval_half_open':[0,6],'reference_video_segment':[6,12],'latent_interval_half_open':[0,3],'frame_rows':2}
  f=self.functions(ROOT/'extensions/H3TemporalRouter/core.py')['route_attention'];got=f(q,k,v,2,plan,mode='mass_preserve',attention=attention)
  logits=q@k.transpose(-1,-2)/2;prob=logits.softmax(-1);updated=prob.clone()
  for t in range(3):
   sl=slice(t*2,(t+1)*2);mass=prob[:,:,sl,6:12].sum(-1,keepdim=True);local=logits[:,:,sl,6+2*t:8+2*t].softmax(-1)
   updated[:,:,sl,6:12]=0;updated[:,:,sl,6+2*t:8+2*t]=mass*local
  expected=(updated@v).transpose(1,2).reshape(1,15,8)
  torch.testing.assert_close(got,expected,rtol=1e-5,atol=1e-6)
  torch.testing.assert_close(updated.sum(-1),prob.sum(-1));torch.testing.assert_close(updated[:,:,:6,6:12].sum(-1),prob[:,:,:6,6:12].sum(-1))

if __name__=='__main__':unittest.main(verbosity=2)
