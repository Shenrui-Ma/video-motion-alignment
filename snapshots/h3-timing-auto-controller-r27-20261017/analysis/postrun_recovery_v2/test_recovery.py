import ast,copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import recovery_contract as c
import remote_consume as remote
import one_phase

class RecoveryTests(unittest.TestCase):
 def fixture(self,d):
  root=Path(d)/'root';arc=Path(d)/'archive';root.mkdir();arc.mkdir();run='test'
  req=root/'obs/request.json';res=root/'obs/response.json';pose=root/'obs/pose.json';obs=root/'obs/observer.json';dec=root/'obs/decode.json';endpoint=root/'endpoint.pt';source=root/'configs/source.pose.json'
  for p in (pose,dec,endpoint,source):p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
  observer={'status':'unknown_visibility','physical_index':0,'source_pose_sha256':c.sha(source),'edited_pose_sha256':c.sha(pose),'windows':[],'reasons':['unreliable torso'],'scan_seconds':1}
  c.save(obs,observer);c.save(req,{'run_id':run,'physical_index':0,'endpoint_file':str(endpoint),'endpoint_file_sha256':c.sha(endpoint)})
  c.save(res,{'physical_index':0,'request_sha256':c.sha(req),'endpoint_file_sha256':c.sha(endpoint),'decode':{'file':str(dec),'sha256':c.sha(dec)},'pose':{'file':str(pose),'sha256':c.sha(pose)},'observer':{'file':str(obs),'sha256':c.sha(obs)}})
  inventory={}
  for p in root.rglob('*'):
   if p.is_file():
    rel=str(p.relative_to(root));a=arc/rel;a.parent.mkdir(parents=True,exist_ok=True);a.write_bytes(p.read_bytes());inventory[rel]={'bytes':p.stat().st_size,'sha256':c.sha(p)}
  m={'physical_index':0,'status':'complete','request_file':str(req),'response_file':str(res),'request_sha256':c.sha(req),'response_sha256':c.sha(res),'observer':observer}
  return root,arc,inventory,m
 def test_actual_measurement_index_and_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   r,a,inv,m=self.fixture(d);v=c.index_measurement(r,a,'test',0,m,inv);self.assertEqual(len(v['dependencies']),7);self.assertEqual(v['expected_replay']['summary']['scientific_status'],'unknown_visibility');self.assertEqual(v['expected_replay']['summary']['rows'],0)
 def test_original_observer_value_change_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,a,inv,m=self.fixture(d);m['observer']['reasons']=['changed']
   with self.assertRaises(ValueError):c.index_measurement(r,a,'test',0,m,inv)
 def test_wrong_source_binding_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,a,inv,m=self.fixture(d);(a/'configs/source.pose.json').write_text('{"wrong":true}')
   with self.assertRaises(ValueError):c.index_measurement(r,a,'test',0,m,inv)
 def test_phase_missing_or_same_size_changed_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,a,inv,m=self.fixture(d);v=c.index_measurement(r,a,'test',0,m,inv);(r/'endpoint.pt').write_text('[]')
   with self.assertRaises(ValueError):c.verify_data_dependencies(r,a,v['dependencies'])
   (r/'endpoint.pt').unlink()
   with self.assertRaises(FileNotFoundError):c.verify_data_dependencies(r,a,v['dependencies'])
 def test_existing_replay_not_recomputed_or_modified(self):
  with tempfile.TemporaryDirectory() as d:
   r,a,inv,m=self.fixture(d);v=c.index_measurement(r,a,'test',0,m,inv);p=a/'old.json';c.save(p,dict(passed=True,all_numeric_values_equal=True,**v['expected_replay']));before=p.read_bytes();self.assertEqual(c.preserve_or_validate(p,v['expected_replay']),c.sha(p));self.assertEqual(p.read_bytes(),before)
   x=c.read(p);x['summary']['rows']=1;c.save(p,x)
   with self.assertRaises(ValueError):c.preserve_or_validate(p,v['expected_replay'])
 def test_index_changed_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,a,inv,m=self.fixture(d);v=c.index_measurement(r,a,'test',0,m,inv);p=a/'index.json';c.save(p,v);digest=c.sha(p);c.check_index(p,digest,'test',0,inv);v['index']=1;c.save(p,v)
   with self.assertRaises(ValueError):c.check_index(p,digest,'test',0,inv)
 def test_stat_is_not_content_hash_claim(self):
  with tempfile.TemporaryDirectory() as d:
   r,a,inv,m=self.fixture(d)
   with patch.object(c,'sha',side_effect=AssertionError('snapshot must not hash large data')):s=c.stat_inventory(r,a,inv)
   self.assertEqual(len(s),64);(r/'endpoint.pt').unlink()
   with self.assertRaises(FileNotFoundError):c.stat_inventory(r,a,inv)
 def test_partial_inventory_extra_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,a,inv,m=self.fixture(d)
   for name in ('FILE_INVENTORY.json','RUN_GATE.json','RUNTIME_GATE.json','DECISION_LEDGER.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json'):(a/name).write_text('{}')
   self.assertEqual(c.validate_partial_inventory(a,inv),set());(a/'extra').write_text('bad')
   with self.assertRaises(ValueError):c.validate_partial_inventory(a,inv)
 def test_technical_error_is_not_unknown(self):
  with self.assertRaises(ValueError):c.observer_summary({'status':'technical_error','windows':[]})
 def test_run_phase_selection(self):
  cases=one_phase.base.P['cases'];runs=[x['run_id'] for x in cases];s={'runs':{r:{'run':r,'phase':'complete'} for r in runs}};s['runs'][runs[1]]['phase']='adopt';self.assertEqual(one_phase.choose_phase(s)[0],runs[1]);self.assertEqual(one_phase.choose_phase(s,runs[0])[0],None)
  with self.assertRaises(ValueError):one_phase.choose_phase(s,'foreign')
 def test_no_eager_heavy_import(self):
  import sys
  self.assertNotIn('torch',sys.modules);self.assertNotIn('cv2',sys.modules)
 def test_deployment_includes_all_frozen_subtrees(self):
  text=(c.HERE/'one_phase.py').read_text();self.assertIn("str(HERE/'parents')",text);self.assertIn("str(HERE/'history')",text)
 def test_frozen_evaluator_exact(self):
  old=Path(c.read(c.HERE/'PROTOCOL.json')['recovery']['local_original_postrun']);self.assertEqual((old/'evaluate.py').read_bytes(),(c.HERE/'evaluate.py').read_bytes())
  def code(path,name):
   src=path.read_text();node=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name==name);return ast.dump(node,include_attributes=False)
  for name in ('numeric_observer','observer_summary','validate_replay','check_playback_probe','validate_complete_inventory','validate_local_inventory'):
   self.assertEqual(code(old/'contract.py',name),code(c.HERE/'contract.py',name),name)

if __name__=='__main__':unittest.main()
