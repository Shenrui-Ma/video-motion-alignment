import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from r123_contract import read,sha
import parent_noise
spec=importlib.util.spec_from_file_location('r123_wrapper',R/'audit/root_run_batch.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class ReadonlyPeerNoise(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.r=Path(self.t.name);(self.r/'configs').mkdir();(self.r/'audit').mkdir()
  self.peer={'pid':77,'identity':{'uid':os.getuid(),'start_ticks':'12','cmdline_sha256':'abc'},'gpu_uuid':'GPU5'};self.put('configs/readonly_peer.json',self.peer)
 def put(self,p,v):(self.r/p).write_text(json.dumps(v))
 def test_exact_peer_allowed_readonly(self):
  with patch.object(w.service,'external_identity',return_value=self.peer['identity']),patch.object(w.service,'compute_processes',return_value=[{'pid':77,'gpu_uuid':'GPU5'}]),patch.object(w.service,'GPU','GPU2'):self.assertEqual(w.readonly_peer_policy(self.r),[{'pid':77,'identity':self.peer['identity']}])
 def test_absent_peer_allowed(self):
  with patch.object(w.service,'external_identity',return_value=None):self.assertEqual(w.readonly_peer_policy(self.r),[])
 def test_reused_pid_refused(self):
  with patch.object(w.service,'external_identity',return_value=dict(self.peer['identity'],start_ticks='13')):
   with self.assertRaisesRegex(ValueError,'identity changed'):w.readonly_peer_policy(self.r)
 def test_changed_gpu_refused(self):
  with patch.object(w.service,'external_identity',return_value=self.peer['identity']),patch.object(w.service,'compute_processes',return_value=[{'pid':77,'gpu_uuid':'GPU3'}]):
   with self.assertRaisesRegex(ValueError,'GPU changed'):w.readonly_peer_policy(self.r)
 def test_parent_noise_copy_and_mutation_guard(self):
  src=self.r/'original.pt';src.write_bytes(b'noise');man=self.r/'manifest.json';meta={'signature':{'seed':1},'actual_noise_streams':[{'sha256':'tensor'}]};man.write_text(json.dumps(meta))
  c=dict(source_file=str(src),source_sha256=sha(src),source_noise_manifest=str(man),source_noise_manifest_sha256=sha(man),destination_filename='reuse.pt',**meta);self.put('configs/parent_noise.json',c)
  self.assertTrue(parent_noise.prepare(self.r)['passed']);self.assertEqual((self.r/'audit/reuse.pt').read_bytes(),src.read_bytes());(self.r/'audit/reuse.pt').write_bytes(b'bad')
  with self.assertRaisesRegex(ValueError,'copied noise differs'):parent_noise.prepare(self.r)
