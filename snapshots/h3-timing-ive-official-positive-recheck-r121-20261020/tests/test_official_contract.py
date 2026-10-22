import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r121_contract as c

class OfficialProtocol(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Path(self.tmp.name)
  for folder in ('configs','design'):shutil.copytree(ROOT/folder,self.r/folder)
 def test_both_sources_exact_original_prompt(self):
  jobs,order=c.registry(self.r);self.assertEqual(len(order),4)
  for row in jobs.values():self.assertEqual(row['case']['prompt'],row['case']['original_task']['edit_prompt'])
 def test_prompt_expansion_rejected(self):
  p=self.r/'configs/scientific_contract.json';v=c.read(p);v['cases'][0]['prompt']+=' Keep the same camera.';p.write_text(json.dumps(v))
  with self.assertRaisesRegex(ValueError,'official edit_prompt'):c.registry(self.r)
 def test_added_video1_not_silently_allowed(self):
  p=self.r/'configs/graphs/r121_short_0252_seed2026101701_native.json';v=c.read(p);v['5']['inputs']['prompt']='In Video1, '+v['5']['inputs']['prompt'];p.write_text(json.dumps(v))
  with self.assertRaisesRegex(ValueError,'graph differs'):c.registry(self.r)
 def test_pairs_differ_only_run_binding_and_route_mode(self):
  jobs,order=c.registry(self.r)
  for a,b in zip(order[::2],order[1::2]):
   x=c.read(self.r/'configs/graphs'/(a+'.json'));y=c.read(self.r/'configs/graphs'/(b+'.json'))
   for node in ('6','50','51','52'):y[node]['inputs']['run_id']=a
   y['14']['inputs']['filename_prefix']=a;y['50']['inputs']['mode']='native'
   self.assertEqual(x,y)
 def test_physical_padding_excluded(self):
  jobs,order=c.registry(self.r)
  oxygen=c.routing_layout(jobs[order[0]]['case']);drink=c.routing_layout(jobs[order[2]]['case'])
  self.assertEqual(oxygen['latent_interval_half_open'],[0,29]);self.assertEqual(oxygen['pure_pad_bins'],[29,30,31])
  self.assertEqual(drink['latent_interval_half_open'],[0,32]);self.assertEqual(drink['pure_pad_bins'],[])
  self.assertEqual(drink['pixel_interval_inclusive'],[0,104])
 def test_sampler_noise_and_kernel_inputs_preserved(self):
  jobs,order=c.registry(self.r)
  for run in order:
   case=jobs[run]['case'];parent=c.read(self.r/case['parent_graph']);new=c.read(self.r/'configs/graphs'/(run+'.json'))
   for node in parent:
    if node not in ('5','6','14','50','51','52'):self.assertEqual(parent[node],new[node],node)
   self.assertEqual(new['6']['inputs']['noise_seed'],2026101701)
   self.assertEqual(parent['6']['inputs']['noise_seed'],new['6']['inputs']['noise_seed'])
 def test_source_order_and_scope_locked(self):
  p=self.r/'configs/scientific_contract.json';v=c.read(p);v['cases'][0]['valid_frame_count']=107;p.write_text(json.dumps(v))
  with self.assertRaisesRegex(ValueError,'geometry'):c.registry(self.r)

if __name__=='__main__':unittest.main()
