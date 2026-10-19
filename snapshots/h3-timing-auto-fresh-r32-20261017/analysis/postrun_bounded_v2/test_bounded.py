import ast,copy,json,tempfile,unittest,subprocess,sys
from pathlib import Path
from unittest.mock import patch
import indexed_contract as c
import remote_consume as remote
import one_phase
class BoundedTests(unittest.TestCase):

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

 def test_no_eager_heavy_import(self):
   import sys
   self.assertNotIn('torch',sys.modules);self.assertNotIn('cv2',sys.modules)

 def test_original_evaluator_and_condition_logic_exact(self):
  old=Path(remote.P['bounded_v2']['local_original_postrun'])
  self.assertEqual((old/'evaluate.py').read_bytes(),(c.HERE/'evaluate.py').read_bytes())
  self.assertEqual((old/'verify_single.py').read_bytes(),(c.HERE/'verify_single.py').read_bytes())
  def code(path,name):
   src=path.read_text();n=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name==name);return ast.dump(n,include_attributes=False)
  for name in ['inventory','condition_checks','runtime_imports']:
   self.assertEqual(code(old/'remote_consume.py',name),code(c.HERE/'remote_consume.py',name))
  for name in ['numeric_observer','observer_summary','validate_replay','verify_source_archive','check_playback_probe','validate_complete_inventory','validate_local_inventory']:
   self.assertEqual(code(old/'contract.py',name),code(c.HERE/'contract.py',name))
 def test_snapshot_never_loads_counterfactual_or_calls_inventory(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);run='test'
   rels=[f'logs/{run}_history.json',f'logs/{run}_job.json',f'configs/{run}.json',f'audit/counterfactual/{run}.json',f'audit/{run}_conditioning.json',f'audit/{run}_noise.json','deploy_manifest.json','configs/source.pose.json']
   for n in rels:c.save(r/n,{'irrelevant':'data'})
   for n in [f'audit/x0/{run}',f'audit/counterfactual/{run}_snapshots','audit/observations']:(r/n).mkdir(parents=True,exist_ok=True)
   c.save(r/f'audit/x0/{run}/manifest.json',{'status':'complete','captures':[{}]*20})
   real_read=remote.read;real_sha=remote.sha
   def read(p):
    self.assertNotIn('/counterfactual/',str(p));return real_read(p)
   def sha(p):
    self.assertNotIn('/counterfactual/',str(p));return real_sha(p)
   with patch.object(remote,'ROOT',r),patch.object(remote,'read',side_effect=read),patch.object(remote,'sha',side_effect=sha),patch.object(remote,'inventory',side_effect=AssertionError('eager large audit')):
    a=remote.metadata_token(run);(r/f'audit/counterfactual/{run}.json').write_text('changed');b=remote.metadata_token(run)
   self.assertNotEqual(a,b)
 def test_one_phase_stability_and_no_implicit_execution(self):
  self.assertEqual(one_phase.readiness({'status':'pending'},None,0,60)[0],'pending')
  x={'status':'success_files_present','token':'a'};mode,state=one_phase.readiness(x,None,0,60);self.assertEqual(mode,'stabilizing')
  self.assertEqual(one_phase.readiness(x,state,59,60)[0],'stabilizing');self.assertEqual(one_phase.readiness(x,state,60,60)[0],'ready')
  text=(c.HERE/'one_phase.py').read_text();self.assertIn("local_original_postrun",text);self.assertIn("str(HERE/'history')",text)
  result=subprocess.run([sys.executable,str(c.HERE/'one_phase.py')],capture_output=True,text=True,timeout=10);self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Prepared only',result.stdout)
 def test_bounded_remote_timeout(self):
  import consume
  with patch.object(consume.subprocess,'run') as run:
   consume.remote(['observation','--run','x','--index','0']);args=run.call_args;self.assertIn('/usr/bin/timeout',args.args[0][-1]);self.assertIn('--kill-after=15s',args.args[0][-1]);self.assertEqual(args.kwargs['timeout'],960)
 def test_source_dependency_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'scripts').mkdir();(r/'scripts/example.py').write_text('a');c.save(r/'deploy_manifest.json',{'files':{'scripts/example.py':{'bytes':1,'sha256':c.sha(r/'scripts/example.py')}}});digest=c.sha(r/'deploy_manifest.json');c.verify_producer_sources(r,digest);(r/'scripts/example.py').write_text('b')
   with self.assertRaises(ValueError):c.verify_producer_sources(r,digest)
 def test_fresh_process_all_imports(self):
  result=subprocess.run([sys.executable,'-c','import contract,indexed_contract,remote_consume,consume,one_phase,evaluate'],cwd=c.HERE,capture_output=True,text=True,timeout=20);self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
