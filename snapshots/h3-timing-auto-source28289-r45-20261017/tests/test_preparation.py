"""Small stdlib-only draft checks; no parent results, torch, or GPU required."""
import ast,copy,hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'scripts'))
from r45_contract import expected_graph,validate_job
from observer_import import t

def read(rel):return json.loads((R/rel).read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def constants(rel):
 result={}
 for n in ast.parse((R/rel).read_text()).body:
  if isinstance(n,ast.Assign):
   try:value=ast.literal_eval(n.value)
   except (ValueError,TypeError):continue
   for name in n.targets:
    if isinstance(name,ast.Name):result[name.id]=value
 return result

class DraftTests(unittest.TestCase):
 def test_exact_17_numerical_files(self):
  spec=read('audit/preparation/NUMERICAL_INHERITANCE.json');self.assertEqual(len(spec['exact_numerical_files']),17)
  for name,sha in spec['exact_numerical_files'].items():self.assertEqual(digest(R/name),sha,name)
 def test_rule_exact_except_pending_source_hash(self):
  original=read('configs/inherited_policy.json');p=read('configs/protocol.json')
  observer=copy.deepcopy(p['observer']);observer['source_pose_sha256']=original['observer']['source_pose_sha256']
  self.assertEqual(observer,original['observer']);self.assertEqual(p['actuator'],original['actuator'])
 def test_parent_graph_and_prompt_exact(self):
  p=read('configs/parent_graph.json');case=read('configs/protocol.json')['cases'][0];g=read('configs/'+case['run_id']+'.json')
  self.assertEqual(g,expected_graph(p,case));self.assertEqual(g['5']['inputs']['prompt'].encode(),p['5']['inputs']['prompt'].encode())
  for n in ('1','2','3','4','7','8','9','10','11','12','13','21','22','23','41'):self.assertEqual(p[n],g[n],n)
  for key in ('width','height','length','semantic_fps','phase_frames','clip','vae','ref_image','ref_video'):self.assertEqual(p['5']['inputs'][key],g['5']['inputs'][key])
  for k in ('seed','steps','scheduler','sampler_name'):
   for n in p:
    if n!='50' and k in p[n]['inputs']:self.assertEqual(p[n]['inputs'][k],g[n]['inputs'][k])
  self.assertEqual(g['6']['inputs']['noise_seed'],2026101701)
 def test_no_oracle_window_in_auto_node(self):
  case=read('configs/protocol.json')['cases'][0];g=read('configs/'+case['run_id']+'.json')
  self.assertEqual(set(g['50']['inputs']),{'model','positive','run_id','audit_dir'})
  self.assertEqual(read('configs/protocol.json')['observer']['indices'],list(range(20)))
 def test_source_bytes(self):
  for name,sha in read('configs/input_hashes.json').items():self.assertEqual(digest(R/'inputs'/name),sha)
  self.assertEqual(digest(R/'configs/parent_graph.json'),'4cd4dcc7c72d5345827d6f2b435e915f63b5026f86bcd09dcfe2913028758fdc')
 def test_original_evidence_copies_exact(self):
  for item in read('audit/preparation/COPY_INVENTORY.json'):
   name=item['destination']
   if name.startswith(('audit/preparation/original_evidence/','inputs/')) or name in ('configs/parent_graph.json','configs/source_provenance.json','configs/source_input_probe.json','configs/source_selection.json'):
    self.assertEqual(digest(R/name),item['sha256'],name)
 def test_24fps_prepared_mapping(self):
  rows=read('configs/source_input_probe.json')['frames'];self.assertEqual(len(rows),141)
  self.assertTrue(all(abs(float(row['best_effort_timestamp_time'])-i/24)<1e-6 for i,row in enumerate(rows)))
 def test_new_resources(self):
  service=constants('scripts/service.py');self.assertEqual(service['PORT'],8507)
  self.assertEqual(service['GPU'],t.MAIN_UUID);self.assertEqual(t.MAIN_UUID,t.DECODER_UUID)
  self.assertEqual(t.MAIN_UUID,'GPU-REDACTED');self.assertEqual(t.SECOND_TASK_UUID,'GPU-REDACTED')
 def test_actual_source_pose_and_parent_closure(self):
  closure=read('configs/PARENT_CLOSURE.json');self.assertIs(closure['ready'],True)
  self.assertEqual(closure['remaining_required_files'],[])
  self.assertEqual(read('configs/protocol.json')['observer']['source_pose_sha256'],'20d6079ec8eb3e9824f599a23447bc122c49d796289f4408345eda4e3645946c')
  self.assertEqual(read('configs/protocol.json')['prefix']['old_indices'],list(range(20)))
 def test_actual_parent_metadata_copied_without_rewriting(self):
  evidence=read('configs/parent_evidence_bindings.json')
  for name,row in evidence.items():self.assertEqual(digest(R/'configs'/name),row['sha256'],name)
  gate=read('configs/parent_run_gate.json');self.assertIs(gate['passed'],True)
  self.assertEqual(gate['file_inventory_sha256'],digest(R/'configs/parent_file_inventory.json'))
  self.assertEqual(gate['runtime_gate_sha256'],digest(R/'configs/parent_runtime_gate.json'))
 def test_actual_parent_21_and_new_layout(self):
  c=read('configs/parent_captures.json');self.assertEqual([row['step_zero_based'] for row in c['captures']],list(range(20)))
  self.assertEqual(c['seed'],2026101701)
  b=read('configs/parent_layout.json');self.assertEqual(b['conditioning_sha256'],digest(R/'configs/parent_conditioning.json'))
  self.assertEqual(b['packed_layout']['seq_len'],87366)
  self.assertEqual(b['packed_layout']['segments'],[[0,6734,'text'],[6734,7684,'ref_img'],[7684,47290,'ref_img'],[47290,47760,'audio'],[47760,87366,'video']])
 def test_runtime_bindings_match_actual_parent(self):
  self.assertIn('configs/source.pose.json',t.bindings()['local_files'])
 def test_preflight_metadata_actual_parent(self):
  import preflight
  self.assertTrue(preflight.check(R,metadata_only=True)['pass'])
 def test_boolean_and_false_inventory_cannot_admit(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'configs').mkdir();c=read('configs/PARENT_CLOSURE.json')
   for ready in (False,1):
    c['ready']=ready;c['status']='READY';(root/'configs/PARENT_CLOSURE.json').write_text(json.dumps(c))
    with self.assertRaisesRegex(ValueError,'WAITING_R42_PARENT_CLOSURE'):t.require_parent_closure(root)
   c['ready']=True;c['actual_file_sha256']={};(root/'configs/PARENT_CLOSURE.json').write_text(json.dumps(c))
   with self.assertRaisesRegex(ValueError,'inventory incomplete'):t.require_parent_closure(root)
 def test_default_admission_false(self):
  self.assertIs(t.admission_document()['root_live_review_required'],True)
  with self.assertRaises(ValueError):t.admission_document(approved=True)
 def test_manifest_cannot_be_written_without_final_parent_archive(self):
  with tempfile.TemporaryDirectory() as temp:
   # Check the independent final-seal requirement without mutating active configs.
   tree=ast.parse((R/'scripts/build_manifest.py').read_text());checks=[n for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='require']
   self.assertEqual(len(checks),1)
   code=compile(ast.Module(body=checks,type_ignores=[]),'manifest_final_guard','exec')
   for value in (False,1,None):
    with self.assertRaisesRegex(ValueError,'WAITING_R42_FINAL_ARCHIVE'):exec(code,{'t':t,'closure':{'final_archive_ready':value}})
   exec(code,{'t':t,'closure':{'final_archive_ready':True}})
 def test_all_current_python_parses(self):
  for sub in ('extensions','scripts','tests'):
   for p in (R/sub).rglob('*.py'):ast.parse(p.read_text(),filename=str(p))

if __name__=='__main__':unittest.main()
