import copy,json,sys,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
import torch
R=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(R/'scripts'),str(R/'analysis/postrun')]
import r106_contract as contract
import capture_checks,verify_pair
from test_sampler_capture import run

def write(p,v):p.write_text(json.dumps(v))

class ContractTests(unittest.TestCase):
 def test_graphs_only_solver_and_output_identity_change(self):
  jobs,order=contract.registry();a,b=[contract.read(R/'configs/graphs'/(r+'.json')) for r in order]
  changed=[]
  for node in a:
   for key,value in a[node]['inputs'].items():
    if value!=b[node]['inputs'][key]:changed.append((node,key))
  self.assertEqual(sorted(changed),sorted([('8','sampler_name'),('6','run_id'),('14','filename_prefix'),('50','run_id'),('51','run_id'),('52','run_id')]))
  self.assertEqual(a['6']['inputs']['pair_id'],b['6']['inputs']['pair_id'])
 def test_non_solver_changes_are_rejected(self):
  for node,key,value in [('9','sigmas','1,0'),('6','noise_seed',123),('5','prompt','changed'),('50','mode','fixed'),('50','alpha',3.)]:
   with self.subTest(node=node,key=key),tempfile.TemporaryDirectory() as d:
    root=Path(d);shutil.copytree(R/'configs',root/'configs');shutil.copytree(R/'design',root/'design')
    p=root/'configs/graphs'/(contract.RUNS[1]+'.json');g=contract.read(p);g[node]['inputs'][key]=value;write(p,g)
    with self.assertRaises(ValueError):contract.registry(root)
 def test_order_cannot_swap(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);shutil.copytree(R/'configs',root/'configs');shutil.copytree(R/'design',root/'design')
   p=root/'configs/queue.json';write(p,{'jobs':list(reversed(contract.RUNS)),'finalize':True})
   with self.assertRaises(ValueError):contract.registry(root)

class CaptureVerificationTests(unittest.TestCase):
 def inspect(self,d,solver):
  config,*_=run(solver,True,Path(d));folder=Path(d)/config.run_id
  m=contract.read(folder/'manifest.json');shapes=dict(zip(('video','audio'),config.shapes))
  with patch.object(capture_checks,'SHAPES',shapes),patch.object(capture_checks,'GEOMETRY',m['geometry']):
   return folder,capture_checks.inspect_capture(folder,config.run_id,m['sigmas_video'],2026101701,solver)
 def test_actual_captures_gate_and_raw_prefix(self):
  with tempfile.TemporaryDirectory() as d:
   _,a=self.inspect(d,'sample_euler');_,b=self.inspect(d,'sample_res_multistep')
   self.assertEqual(len(a[1]),23);self.assertTrue(all(verify_pair.compare_prefix(a[2],b[2]).values()))
   b[2][1]['raw']['state_video'][0,0,0,0,0]+=1
   self.assertFalse(all(verify_pair.compare_prefix(a[2],b[2]).values()))
 def test_raw_payload_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   folder,(_,_,_)=self.inspect(d,'sample_euler');p=folder/'raw_prefix_step000.pt'
   data=torch.load(p,weights_only=True);data['state_video'][0,0,0,0,0]+=1;torch.save(data,p)
   m=contract.read(folder/'manifest.json');shapes={'video':(1,24,2,2,2),'audio':(1,32,2,8)}
   with patch.object(capture_checks,'SHAPES',shapes),patch.object(capture_checks,'GEOMETRY',m['geometry']),self.assertRaises(ValueError):
    capture_checks.inspect_capture(folder,m['run_id'],m['sigmas_video'],2026101701,'sample_euler')
 def test_wrong_solver_manifest_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   folder,_=self.inspect(d,'sample_euler');m=contract.read(folder/'manifest.json')
   with self.assertRaises(ValueError):capture_checks.inspect_capture(folder,m['run_id'],m['sigmas_video'],2026101701,'sample_res_multistep')

if __name__=='__main__':unittest.main()
