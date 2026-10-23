import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cache_loader',ROOT/'custom_nodes/H3TrustedConditionCache/__init__.py');cache=importlib.util.module_from_spec(spec);spec.loader.exec_module(cache)
class PackageTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name);self.t=torch.arange(12,dtype=torch.float32).reshape(1,3,4);self.f=self.p/'tensor.pt';torch.save(self.t,self.f);self.rec=dict(file=str(self.f),sha256=cache.sha(self.f),tensor_signature=cache.signature(self.t))
 def tearDown(self):self.temp.cleanup()
 def test_tensor_round_trip(self):self.assertTrue(torch.equal(cache.checked_tensor(self.rec),self.t))
 def test_changed_file_rejected(self):
  torch.save(self.t+1,self.f)
  with self.assertRaises(ValueError):cache.checked_tensor(self.rec)
 def test_changed_shape_rejected(self):
  self.rec['tensor_signature']['shape']=[12]
  with self.assertRaises(ValueError):cache.checked_tensor(self.rec)
 def test_symlink_rejected(self):
  link=self.p/'alias.pt';link.symlink_to(self.f);self.rec['file']=str(link)
  with self.assertRaises(ValueError):cache.checked_tensor(self.rec)
 def test_manifest_identity_rejected(self):
  f=self.p/'manifest.json';f.write_text('{}')
  with self.assertRaises(ValueError):cache.H3TrustedConditionCache().load(str(f),'0'*64)
 def test_reference_binding_rejected(self):
  f=self.p/'manifest.json';f.write_text(json.dumps(dict(schema='r146-original-clean-condition-cache-v1',source_video=str(self.f),source_video_sha256='0'*64)))
  with self.assertRaises(ValueError):cache.H3TrustedConditionCache().load(str(f),cache.sha(f))
 def test_all_graphs_connected(self):
  for job in json.loads((ROOT/'jobs.json').read_text())['jobs']:
   graph=json.loads((ROOT/job['graph']).read_text())
   for node in graph.values():
    for val in node['inputs'].values():
     if isinstance(val,list) and len(val)==2 and isinstance(val[0],str):self.assertIn(val[0],graph)
   self.assertEqual(graph['50']['class_type'],'H3DirectionGatedSchedule');self.assertEqual(graph['50']['inputs']['alpha'],.25)
   self.assertFalse(any('X0' in n['class_type'] or 'Pose' in n['class_type'] or 'Audit' in n['class_type'] for n in graph.values()))
 def test_ten_exact_pairings(self):
  cases=json.loads((ROOT.parent/'manifest_preparation/catalog.json').read_text())['cases'];jobs=json.loads((ROOT/'jobs.json').read_text())['jobs']
  self.assertEqual(len(jobs),10)
  for c,j in zip(cases,jobs):
   g=json.loads((ROOT/j['graph']).read_text());self.assertEqual(j['metadata']['prompt'],c['prompt']);self.assertEqual(g['6']['inputs']['noise_seed'],c['seed']);self.assertEqual(g['9']['inputs']['sigmas'],c['sampling']['sigmas']);self.assertEqual(g['50']['inputs']['end_frame'],c['geometry']['valid_frames']-1)
   if 'condition_cache_manifest' in c:
    cm=ROOT/'cache_manifests'/f"{c['task_id']}.json";self.assertEqual(cache.sha(cm),g['5']['inputs']['manifest_sha256']);m=json.loads(cm.read_text());orig=c['condition_cache_manifest']['contents'];self.assertEqual([r['sha256'] for r in m['tensors']],[r['sha256'] for r in orig['tensors']]);self.assertEqual(m['geometry'],orig['geometry'])
   else:self.assertEqual(g['5']['inputs']['prompt'],c['prompt'])
 def test_pilot_order(self):
  j=json.loads((ROOT/'pilot_jobs.json').read_text())['jobs'];self.assertEqual([x['metadata']['task_id'] for x in j],['short_0252','short_0358'])
if __name__=='__main__':unittest.main()
