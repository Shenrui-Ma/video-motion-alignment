import ast,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('capacity_contract',HERE/'H3MainCapacityProbe/contract.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
s=importlib.util.spec_from_file_location('capacity_runner',HERE/'run_probe.py');runner=importlib.util.module_from_spec(s);s.loader.exec_module(runner)
class Tests(unittest.TestCase):
 def temp(self):return Path(tempfile.mkdtemp(dir=HERE/'test_tmp'))
 def report(self):
  mem={'allocated_bytes':10,'reserved_bytes':20,'driver_free_bytes':30,'driver_total_bytes':50}
  return {'status':'capacity_measured_controlled_stop','inference_complete':False,'model_forward_calls':2,'native_exact':True,'condition_exact':True,'noise_exact':True,'forwards':[{'branch':b,'before':mem,'after':mem,'peak_allocated_bytes':10,'peak_reserved_bytes':20,'completed_blocks':50,'routed_blocks':n} for b,n in [('native',0),('full27',50)]]}
 def test_actual_metadata_selects_0352_blind(self):
  parent=HERE.parents[1].parent/'h3-timing-ivebench-native-r54-20261017'
  # Local downloaded archive contains conditioning metadata; no video/metric read.
  parent=Path('/Users/researcher/DevProjects/h3-timing-ivebench-native-r54-20261017/analysis/postrun/captured/batch')
  cases=c.read(HERE.parents[1]/'configs/protocol.json')['cases'];chosen,rows=c.select_largest(cases,parent)
  self.assertEqual((chosen['source_id'],chosen['seq_len']),('short_0352',55045));self.assertEqual(len(rows),5)
 def test_largest_tie_is_deterministic(self):
  root=self.temp();(root/'audit').mkdir();cases=[]
  for i,n in enumerate([100,110,110,90,95]):
   run='r'+str(i);cases.append({'parent_run':run,'source_id':'s'+str(i)});c.write_new(root/'audit'/(run+'_conditioning.json'),{'packed_layout':{'seq_len':n,'segments':[[0,27*943,'ref_img'],[27*943,54*943,'video']]}})
  self.assertEqual(c.select_largest(cases,root)[0]['source_id'],'s1')
 def test_graph_numerical_inputs_unchanged(self):
  p=HERE.parents[1]/'configs/parent_graphs/r54_short_0352_seed2026101701_native.json';old=c.read(p);new=c.probe_graph(old,Path('/probe'),Path('/probe/config.json'))
  for key in old:
   if key not in ('5','6','50','51','52','14'):self.assertEqual(old[key],new[key])
  for key in ('5','6','50','51'):
   for name,value in old[key]['inputs'].items():
    if name not in ('audit_dir','source_audit_dir','run_id','source_run_id','pair_id'):self.assertEqual(value,new[key]['inputs'][name])
  self.assertEqual(new['9'],old['9']);self.assertEqual(new['8'],old['8']);self.assertEqual(new['52']['class_type'],'H3MainCapacityProbe')
 def test_capacity_verdict_accepts_controlled_scope(self):self.assertTrue(c.successful_capacity(self.report()))
 def test_wrong_native_exact_rejected(self):
  p=self.report();p['native_exact']=False
  with self.assertRaises(ValueError):c.successful_capacity(p)
 def test_missing_full_forward_rejected(self):
  p=self.report();p['model_forward_calls']=1
  with self.assertRaises(ValueError):c.successful_capacity(p)
 def test_false_video_completion_rejected(self):
  p=self.report();p['inference_complete']=True
  with self.assertRaises(ValueError):c.successful_capacity(p)
 def test_invalid_peak_rejected(self):
  p=self.report();p['forwards'][1]['peak_reserved_bytes']=1
  with self.assertRaises(ValueError):c.successful_capacity(p)
 def test_command_uses_reserve8_and_original_math_flags(self):
  cfg={'runtime':{'python':'python','remote_root':'/r54','core':'/comfy','models':'/models'},'port':8527};args=runner.command(Path('/probe'),cfg)
  self.assertEqual(args[args.index('--reserve-vram')+1],'8')
  for flag in ('--disable-dynamic-vram','--disable-cuda-malloc','--use-pytorch-cross-attention','--enable-triton-backend'):self.assertIn(flag,args)
  self.assertNotIn('--lowvram',args);self.assertNotIn('--fp16-unet',args);self.assertIn('/probe/scripts/capacity_entry.py',args)
 def test_node_interface_matches_existing_model_patcher(self):
  node=(HERE/'H3MainCapacityProbe/__init__.py').read_text();self.assertIn('get_all_wrappers(WrappersMP.PREDICT_NOISE)',node);self.assertNotIn('model.get_wrappers(WrappersMP.PREDICT_NOISE)',node)
 def test_single_gpu_env_and_exact_lifetime_guard(self):
  source=(HERE/'run_probe.py').read_text();self.assertIn('CUDA_VISIBLE_DEVICES=gpu',source);self.assertIn('H3_CAPACITY_PARENT=json.dumps(identity(os.getpid()))',source);self.assertIn('entry is not None and identity(proc.pid)==entry',source)
 def test_no_import_time_gpu_calls(self):
  for p in HERE.rglob('*.py'):
   if 'test_tmp' in p.parts:continue
   compile(p.read_text(),str(p),'exec')
  self.assertNotIn('import torch', (HERE/'prepare.py').read_text())
if __name__=='__main__':
 (HERE/'test_tmp').mkdir(exist_ok=True);unittest.main(verbosity=2)
