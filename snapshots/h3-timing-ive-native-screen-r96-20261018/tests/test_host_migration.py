import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r96_contract as c
OLD=ROOT/'source_snapshot/r87_parent'

class ParentInheritance(unittest.TestCase):
 def test_parent_snapshot_bound_by_original_seal(self):
  seal=c.read(OLD/'deploy_manifest.json')
  for p in OLD.rglob('*'):
   if p.is_file() and p.name!='deploy_manifest.json':self.assertEqual(c.sha(p),seal['files'][str(p.relative_to(OLD))]['sha256'])
 def test_numerical_kernel_files_identical_to_parent(self):
  parent=c.read(OLD/'configs/runtime_kernel_hashes.json')
  self.assertEqual({p:r['current_sha256'] for p,r in parent.items()},{p:r['current_sha256'] for p,r in c.read(ROOT/'configs/runtime_kernel_hashes.json').items()})
  for path,row in parent.items():self.assertEqual(c.sha(ROOT/path),row['current_sha256'])
  self.assertEqual(c.sha(ROOT/'configs/parent_graphs/r63_template_native.json'),c.sha(OLD/'configs/parent_graphs/r63_template_native.json'))
 def test_template_delta_only_visual_style(self):
  old=(OLD/'design/P1_TEMPLATE.txt').read_text()
  self.assertEqual((ROOT/'design/P1_TEMPLATE.txt').read_text(),old.replace('photographic appearance','original visual style'))
 def test_paired_graphs_differ_only_route_and_audit_identity(self):
  jobs,order=c.registry(ROOT)
  for a,b in zip(order[::2],order[1::2]):
   native=c.read(ROOT/'configs/graphs'/(a+'.json'));forced=c.read(ROOT/'configs/graphs'/(b+'.json'))
   normalized=json.loads(json.dumps(forced).replace(b,a));normalized['50']['inputs']['mode']='native'
   self.assertEqual(native,normalized)
 def test_host41_device_and_first_pair_gate(self):
  r=c.read(ROOT/'configs/runtime.json');self.assertEqual((r['expected_gpu_index'],r['gpu_uuid'],r['port']),(2,'GPU-REDACTED',8560))
  self.assertEqual(r['uid'],1004);self.assertEqual(r['reserve_vram'],8)
  self.assertFalse(c.read(ROOT/'configs/admission.json')['ready_for_launch']);self.assertFalse((ROOT/'processes/service.json').exists())
 def test_clip_exploration_scope(self):
  s=c.read(ROOT/'configs/scientific_contract.json');self.assertFalse(s['evaluation']['full_benchmark_reproduction']);self.assertEqual(s['evaluation']['fixed_case_denominator'],5)
  self.assertTrue(all(x['evaluation_scope']=='IVEBench素材片段探索' for x in s['cases']))

if __name__=='__main__':unittest.main()
