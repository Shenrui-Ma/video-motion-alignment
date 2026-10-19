import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r87_contract as c
OLD=ROOT/'source_snapshot/r83_migration'

class HostMigration(unittest.TestCase):
 def test_old_snapshot_bound_by_original_seal(self):
  seal=c.read(OLD/'deploy_manifest.json')
  for p in (OLD/'configs').rglob('*'):
   if p.is_file():self.assertEqual(c.sha(p),seal['files'][str(p.relative_to(OLD))]['sha256'])
 def test_fourteen_graphs_only_paths_and_run_names_changed(self):
  a=c.read(OLD/'configs/scientific_contract.json');b=c.read(ROOT/'configs/scientific_contract.json');oldroot=c.read(OLD/'configs/runtime.json')['remote_root'];newroot=c.read(ROOT/'configs/runtime.json')['remote_root']
  self.assertEqual(len(a['cases']),14);self.assertEqual(len(b['cases']),14)
  for before,after in zip(a['cases'],b['cases']):
   with self.subTest(run=after['run_id']):
    expected=copy.deepcopy(before);expected['run_id']=expected['run_id'].replace('r83_','r87_',1);self.assertEqual(expected,after)
    old=c.read(OLD/'configs/graphs'/(before['run_id']+'.json'));new=c.read(ROOT/'configs/graphs'/(after['run_id']+'.json'))
    normalized=json.loads(json.dumps(new).replace(newroot,oldroot).replace('r87_','r83_'));self.assertEqual(normalized,old)
 def test_input_bytes_and_numeric_kernels_preserved(self):
  self.assertEqual(c.read(OLD/'configs/input_hashes.json'),c.read(ROOT/'configs/input_hashes.json'))
  for path,row in c.read(OLD/'configs/runtime_kernel_hashes.json').items():self.assertEqual(c.sha(ROOT/path),row['current_sha256'])
 def test_host9_device_and_first_pair_gate(self):
  r=c.read(ROOT/'configs/runtime.json');self.assertEqual((r['expected_gpu_index'],r['gpu_uuid'],r['port']),(0,'GPU-REDACTED',8552))
  self.assertEqual(r['uid'],1016);self.assertEqual(r['reserve_vram'],8)
  self.assertFalse(c.read(ROOT/'configs/admission.json')['ready_for_launch']);self.assertFalse((ROOT/'processes/service.json').exists())
  self.assertNotIn('verify_predecessor',(ROOT/'audit/root_run_batch.py').read_text())

if __name__=='__main__':unittest.main()
