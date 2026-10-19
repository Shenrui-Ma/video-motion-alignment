import ast,copy,json,subprocess,sys,unittest
from pathlib import Path
import contract as c

class AdminMigration(unittest.TestCase):
 def setUp(self):self.p=c.read(c.HERE/'PROTOCOL.json');self.root=c.HERE.parents[1]
 def test_only_protocol_admin_fields_change(self):
  old=c.read(c.HERE/'R44_PROTOCOL.json');new=copy.deepcopy(self.p)
  for key in ('schema','root_local','root_remote','project','producer_manifest_sha256','producer_protocol_sha256','producer_manifest_original','revision'):new[key]=old[key]
  new['cases'][0]['run_id']=old['cases'][0]['run_id'];new['online_priority_roots'][0]=old['online_priority_roots'][0]
  self.assertEqual(new,old)
 def test_numerical_and_lifecycle_files_exact(self):
  old=c.read(c.HERE/'R44_FREEZE.json')
  for name in ('contract.py','remote_consume.py','consume.py','evaluate.py','test_postrun.py','test_phase_dependencies.py','parents/native.pose.json','parents/native_job.json','EVIDENCE_BINDING.json'):
   self.assertEqual(c.sha(c.HERE/name),old['files'][name],name)
 def test_current_producer_and_source_parent_binding(self):
  self.assertEqual(c.sha(self.root/'deploy_manifest.json'),self.p['producer_manifest_sha256'])
  self.assertEqual(c.sha(self.root/'configs/protocol.json'),self.p['producer_protocol_sha256'])
  self.assertEqual(self.p['cases'][0]['run_id'],'r45_source28289_seed2026101701_auto')
  self.assertEqual(self.p['source_pose_sha256'],c.sha(self.root/'configs/source.pose.json'))
  self.assertEqual(self.p['parents'],c.read(c.HERE/'R44_PROTOCOL.json')['parents'])
 def test_unbound_owner_and_no_default_action(self):
  b=c.read(c.HERE/'BINDING.template.json');self.assertIsNone(b['service_record']);self.assertIs(b['approved_for_consumer_start'],False)
  self.assertFalse((c.HERE/'BINDING.json').exists());self.assertEqual(b['protocol_sha256'],c.sha(c.HERE/'PROTOCOL.json'))
  result=subprocess.run([sys.executable,'-B',str(c.HERE/'one_phase.py')],capture_output=True,text=True,timeout=20)
  self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Prepared only',result.stdout)
 def test_verifier_only_contract_module_changes(self):
  # Original function ASTs shared with frozen producer; scoped verifier is read-only.
  def functions(p):return {x.name:ast.dump(x) for x in ast.parse(p.read_text()).body if isinstance(x,ast.FunctionDef)}
  a,b=functions(self.root/'scripts/verify_completed.py'),functions(c.HERE/'verify_single.py')
  for name in ('check_record_semantics','check_submission','check_owner_evidence'):self.assertEqual(a[name],b[name])
  self.assertIn('from r45_contract import validate_job',(c.HERE/'verify_single.py').read_text())
 def test_all_source_python_parses(self):
  for p in c.HERE.glob('*.py'):ast.parse(p.read_text())

if __name__=='__main__':unittest.main()
