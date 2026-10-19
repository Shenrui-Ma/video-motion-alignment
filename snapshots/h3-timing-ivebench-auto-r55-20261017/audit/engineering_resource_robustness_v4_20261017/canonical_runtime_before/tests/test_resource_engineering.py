"""Production source checks for measured resource admission and final-seal evidence."""
import ast,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import service,build_manifest
from observer_import import t

class EngineeringTests(unittest.TestCase):
 def test_reserve_eight_is_a_single_model_residency_argument(self):
  args=service.command();self.assertEqual(args.count('--reserve-vram'),1);self.assertEqual(args[args.index('--reserve-vram')+1],'8')
 def test_decoder_bootstrap_is_explicit_and_formal_profile_waits(self):
  profile=json.loads((ROOT/'configs/decoder_memory_profile.json').read_text())
  if profile['status']=='PENDING':
   with self.assertRaises(ValueError):t.decoder_memory_profile()
   self.assertEqual(t.decoder_memory_profile(bootstrap=True)['required_free_bytes'],16*1024**3)
  else:self.assertEqual(t.decoder_memory_profile()['status'],'MEASURED')
 def test_main_capacity_waits_for_measured_evidence(self):
  profile=json.loads((ROOT/'configs/main_memory_profile.json').read_text())
  if profile['status']=='PENDING':
   with self.assertRaises(ValueError):service.main_memory_profile()
  else:self.assertGreater(service.main_memory_profile()['required_free_bytes'],0)
 def test_final_seal_collects_both_engineering_generations_and_actual_gates(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   for generation in ('v3','v4'):
    p=root/('audit/engineering_resource_robustness_'+generation+'_20261017');p.mkdir(parents=True);(p/'evidence.log').write_text('captured evidence')
   with self.assertRaisesRegex(ValueError,'actual GPU gate required'):build_manifest.engineering_files(root)
   for rel in ('gpu_dynamic_union_gate.json','known_endpoint_90_gate.json','resource_admission.json'):(root/'audit'/rel).write_text('{}')
   selected={p.relative_to(root).as_posix() for p in build_manifest.engineering_files(root)}
   self.assertEqual(len(selected),5)
 def test_numeric_inheritance_still_exact(self):
  for rel,row in json.loads((ROOT/'configs/NUMERICAL_INHERITANCE.json').read_text()).items():
   self.assertEqual(t.sha(ROOT/rel),row['current_sha256'],rel)
 def test_bootstrap_snapshot_loop_preserves_native_endpoint_source(self):
  tree=ast.parse((ROOT/'scripts/known_endpoint_90_gate.py').read_text())
  main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
  writes=[n for n in ast.walk(main) if isinstance(n,ast.Name) and n.id=='source' and isinstance(n.ctx,ast.Store)]
  self.assertEqual(len(writes),1)
  assignment=next(n for n in main.body if isinstance(n,ast.Assign) and any(isinstance(q,ast.Name) and q.id=='source' for q in n.targets))
  self.assertIn("'audit/x0'",ast.unparse(assignment.value))
  record=next(n.value for n in main.body if isinstance(n,ast.Assign) and any(isinstance(q,ast.Name) and q.id=='record' for q in n.targets))
  archived=record.values[next(i for i,k in enumerate(record.keys) if isinstance(k,ast.Constant) and k.value=='archived_endpoint')]
  self.assertEqual(ast.unparse(archived),"{'file': str(source), 'sha256': t.sha(source)}")
if __name__=='__main__':unittest.main()
