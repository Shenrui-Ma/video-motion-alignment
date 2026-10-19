import ast,importlib.util,json,os,shutil,subprocess,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
C=Path(__file__).resolve().parents[1];O=C/'r55/overlay'
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
t=load('r55_transport_v4',O/'extensions/H3AutomaticWindowRouter/transport.py')
def fn(path,name):return ast.dump(next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
class Tests(unittest.TestCase):
 def test_formal_pending_hard(self):
  with self.assertRaisesRegex(ValueError,'measured'):t.decoder_memory_profile()
 def test_bootstrap_full90_16GiB_unmeasured(self):
  p=t.decoder_memory_profile(bootstrap=True);self.assertEqual(p['required_free_bytes'],16*1024**3);self.assertEqual(p['status'],'PENDING');self.assertIsNone(p['peak_reserved_bytes'])
 def test_bootstrap_foreign_many_cards_ok(self):
  gpu={'uuid':t.DECODER_UUID,'memory_free_mib':16384,'memory_used_mib':30000,'utilization_percent':100}
  rows=[{'gpu_uuid':u,'pid':pid} for u,pid in [('GPU-a',1),('GPU-b',2),(t.MAIN_UUID,3),(t.DECODER_UUID,4)]]
  with patch.object(t,'query_resource_state',return_value=(gpu,rows,{})),patch.object(t,'validate_resource_capacity',wraps=lambda uuid,gpu,rows,required:t.validate_resource_capacity_original(uuid,gpu,rows,required,lookup=lambda pid:{'pid':pid,'uid':os.getuid()+1})):
   t.standalone_decoder_admission(t.DECODER_UUID)
 def test_formal_measured_mock_profile(self):
  folder=Path(tempfile.mkdtemp(dir=C/'test_tmp'));(folder/'configs/decoder_memory_evidence').mkdir(parents=True)
  p=json.loads((O/'configs/decoder_memory_profile.json').read_text());p.update(status='MEASURED',peak_reserved_bytes=6*1024**3,required_free_bytes=8*1024**3,evidence_file='configs/decoder_memory_evidence/MOCK_ONLY.json')
  evidence={'passed':True,'NFE':0,'model_forward_calls':0,'decode':{'status':'complete','decoded_shape':[90,736,1312,3],'fps':24,'vae_sha256':p['vae_sha256'],'fallback_guard':{'calls':0},'max_memory_reserved_bytes':6*1024**3,'max_memory_allocated_bytes':5*1024**3}}
  path=folder/p['evidence_file'];path.write_text(json.dumps(evidence));p['evidence_sha256']=t.sha(path);(folder/'configs/decoder_memory_profile.json').write_text(json.dumps(p))
  with patch.object(t,'ROOT',folder):self.assertEqual(t.decoder_memory_profile()['required_free_bytes'],8*1024**3)
 def test_four_runtime_resource_logic_matches_tested_r50(self):
  for rel in ('scripts/run_observer.py','scripts/decode_live_child.py','scripts/gpu_release_gate.py'):self.assertEqual((O/rel).read_bytes(),(C/'r50/overlay'/rel).read_bytes())
  for name in ('run_child','decoder_memory_profile','validate_resource_capacity','query_resource_state','validate_separate_decoder','validate_response','typed_cuda_oom','validate_oom_proof','wait_decoder_admission'):
   self.assertEqual(fn(O/'extensions/H3AutomaticWindowRouter/transport.py',name),fn(C/'r50/overlay/extensions/H3AutomaticWindowRouter/transport.py',name))
 def test_service_runtime_command_and_stop_unchanged(self):
  for name in ('command','stop','assert_owned'):self.assertEqual(fn(O/'scripts/service.py',name),fn(C/'r55/before/scripts/service.py',name))
 def test_gate_full90_checks_unchanged(self):
  def checks(p):
   for node in ast.walk(ast.parse(p.read_text())):
    if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='checks' for x in node.targets):return ast.dump(node,include_attributes=False)
  self.assertEqual(checks(O/'scripts/known_endpoint_90_gate.py'),checks(C/'r55/before/scripts/known_endpoint_90_gate.py'))
 def test_bootstrap_preserves_exact_profile_and_bindings(self):
  source=(O/'scripts/known_endpoint_90_gate.py').read_text();self.assertIn("destination.open('xb')",source);self.assertIn("handle.write(source.read_bytes())",source);self.assertIn("t.sha(bootstrap_bindings)==request['bindings_sha256']",source)
 def test_prelaunch_requires_actual_measured_gate(self):
  s=(O/'scripts/prelaunch_gates.py').read_text();self.assertIn('profile=t.decoder_memory_profile()',s);self.assertIn("profile['evidence_sha256']==sha(dp)",s)
 def test_main_profile_pending(self):self.assertEqual(json.loads((O/'configs/main_memory_profile.json').read_text())['status'],'PENDING')
 def test_compile_and_patch_reconstruct(self):
  folder=Path(tempfile.mkdtemp(dir=C/'test_tmp'))/'copy';shutil.copytree(C/'r55/before',folder)
  subprocess.run(['git','apply',str(C/'r55/candidate.patch')],cwd=folder,capture_output=True,check=True)
  for p in O.rglob('*.py'):
   compile(p.read_text(),str(p),'exec');self.assertEqual(p.read_bytes(),(folder/p.relative_to(O)).read_bytes())
t.validate_resource_capacity_original=t.validate_resource_capacity
if __name__=='__main__':unittest.main(verbosity=2)
