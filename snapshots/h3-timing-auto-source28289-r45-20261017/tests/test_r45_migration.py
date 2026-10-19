"""Administrative relocation checks only; no tensor/model imports."""
import ast,copy,hashlib,json,subprocess,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
OLD=R/'audit/preparation/original_evidence/r44'
sys.path.insert(0,str(R/'scripts'))
from observer_import import t
import service
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class MigrationTests(unittest.TestCase):
 def test_protocol_only_four_administrative_changes(self):
  a=read(OLD/'configs/protocol.json');b=read(R/'configs/protocol.json')
  b['schema']=a['schema'];b['cases'][0]['run_id']=a['cases'][0]['run_id']
  for k in ('main_uuid','decoder_uuid'):b['resources'][k]=a['resources'][k]
  self.assertEqual(a,b)
 def test_graph_only_paths_and_run_ids(self):
  a=read(OLD/'configs/r44_source28289_seed2026101701_auto.json');b=read(R/'configs/r45_source28289_seed2026101701_auto.json')
  for n in b.values():
   for k,v in n['inputs'].items():
    if isinstance(v,str):n['inputs'][k]=v.replace('timing_auto_source28289_r45_20261017','timing_auto_source28289_r44_20261017').replace('r45_source28289_','r44_source28289_')
  self.assertEqual(a,b)
 def test_all_historical_parent_and_source_evidence_raw(self):
  names=[p.name for p in (OLD/'configs').glob('parent*')]
  names += ['source.pose.json','source_pose_files.json','source_input_probe.json','source_selection.json','source_provenance.json','input_hashes.json','CASE_ROLE_ADDENDUM.json','kernel_inheritance.json','r27_inheritance.json','r27_parent_manifest.json','r28_parent_manifest.json']
  for n in names:self.assertEqual(sha(OLD/'configs'/n),sha(R/'configs'/n),n)
 def test_failure_is_not_success_and_no_actual_gate_forged(self):
  self.assertFalse((R/'audit/gpu_dynamic_union_gate.json').exists())
  self.assertFalse((R/'audit/resource_admission.json').exists())
  self.assertFalse((R/'analysis/postrun/BINDING.json').exists())
  self.assertIs(read(R/'configs/RESOURCE_ADMISSION_TEMPLATE.json')['root_approved'],False)
  failure=R/'audit/preparation/original_evidence/r44/audit/root_actual_admission/FIRST_FAILURE_DIAGNOSIS.json'
  self.assertEqual(sha(failure),sha(OLD/'audit/root_actual_admission/FIRST_FAILURE_DIAGNOSIS.json'))
 def test_exact_current_gpu_and_new_gate_required(self):
  self.assertEqual(service.GPU,t.MAIN_UUID);self.assertEqual(service.PORT,8507)
  self.assertEqual(t.MAIN_UUID,'GPU-REDACTED')
  self.assertEqual(t.SECOND_TASK_UUID,'GPU-REDACTED')
  self.assertEqual(t.DECODER_UUID,t.MAIN_UUID)
 def test_cpu_evidence_is_historical_not_new_actual_run(self):
  v=read(R/'configs/CPU_EVIDENCE.json');self.assertIs(v['new_actual_Comfy_run'],False)
  old=v['inherited_actual_Comfy_cpu'];self.assertEqual(sha(R/old['source']),old['sha256']);self.assertEqual(sha(R/old['log']),old['log_sha256'])
 def test_fresh_admin_imports_do_not_import_torch(self):
  code="import sys;sys.path.insert(0,sys.argv[1]);import service,job,launch_remote,run_queue,start_controller,preflight,prelaunch_gates,parent_binding,verify_completed,r45_contract;assert 'torch' not in sys.modules;assert service.PORT==8507"
  subprocess.run([sys.executable,'-B','-c',code,str(R/'scripts')],check=True,capture_output=True,timeout=20)
 def test_runtime_AST_only_approved_constants_or_module_name(self):
  oldhash=sha(OLD/'configs/protocol.json');newhash=sha(R/'configs/protocol.json')
  class Normalize(ast.NodeTransformer):
   def visit_Constant(self,node):
    if isinstance(node.value,str):
     value=node.value
     for a,b in [('timing_auto_source28289_r45_20261017','timing_auto_source28289_r44_20261017'),('r45_source28289_','r44_source28289_'),('h3-timing-auto-source28289-r45-20261017','h3-timing-auto-source28289-r44-20261017'),('r45-root-resource-admission-v1','r44-root-resource-admission-v1'),('r45-immutable-deploy-v1','r44-immutable-deploy-v1'),('R45 actual kernel','R44 actual kernel'),('R45 WAITING','R44 WAITING'),('frozen R45 root','frozen R44 root'),(newhash,oldhash)]:value=value.replace(a,b)
     if node.value=='GPU-REDACTED':value='GPU-REDACTED'
     elif node.value=='GPU-REDACTED':value='GPU-REDACTED'
     node.value=value
    elif type(node.value) is int and node.value==8507:node.value=8506
    return node
   def visit_ImportFrom(self,node):
    if node.module=='r45_contract':node.module='r44_contract'
    return node
  for sub in ('scripts','extensions'):
   for p in (OLD/sub).rglob('*.py'):
    rel=p.relative_to(OLD);q=R/rel
    if p.name=='r44_contract.py':q=R/'scripts/r45_contract.py'
    # Exact files require no device normalization; changed ones are constrained.
    if p.read_bytes()==q.read_bytes():continue
    self.assertEqual(ast.dump(ast.parse(p.read_text())),ast.dump(Normalize().visit(ast.parse(q.read_text()))),str(rel))

if __name__=='__main__':unittest.main()
