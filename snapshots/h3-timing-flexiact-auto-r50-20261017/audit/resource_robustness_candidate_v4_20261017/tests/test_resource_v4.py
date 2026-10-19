import ast,hashlib,importlib.util,json,os,sys,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
C=Path(__file__).resolve().parents[1];O=C/'r50/overlay'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
t=load('transport_v4',O/'extensions/H3AutomaticWindowRouter/transport.py')
sys.modules['observer_import']=types.SimpleNamespace(t=t,ROOT=O)
g=load('gpu_release_gate',O/'scripts/gpu_release_gate.py');sys.modules['gpu_release_gate']=g
obs=load('run_observer_v4',O/'scripts/run_observer.py')
srv=load('service_v4',O/'scripts/service.py');srv.RUN=O
live=load('decode_live_v4',O/'scripts/decode_live_child.py')
class Clock:
 def __init__(self):self.now=10.
 def __call__(self):return self.now
 def sleep(self,n):self.now+=n
class Tests(unittest.TestCase):
 def setUp(self):
  self.p={'pid':10,'uid':os.getuid(),'start_ticks':1,'cmdline_sha256':'p'}
  self.gpu={'uuid':t.DECODER_UUID,'memory_free_mib':7752,'memory_used_mib':70000,'utilization_percent':99}
  self.rows=[{'gpu_uuid':t.MAIN_UUID,'pid':10},{'gpu_uuid':t.MAIN_UUID,'pid':20},{'gpu_uuid':t.DECODER_UUID,'pid':21}]
  self.lookup=lambda pid:self.p if pid==10 else {'pid':pid,'uid':os.getuid()+1}
 def admit(self,rows=None,lookup=None,gpu=None):return t.validate_separate_decoder(self.p,t.DECODER_UUID,gpu or self.gpu,rows or self.rows,lookup or self.lookup)
 def test_foreign_coexistence_main_and_decoder(self):self.assertEqual(self.admit()['required_free_bytes'],8128561152)
 def test_duplicate_main_row_accepted(self):self.admit(self.rows+self.rows[:1])
 def test_short_by_one_mib_waits(self):
  with self.assertRaises(t.ResourceUnavailable):self.admit(gpu=dict(self.gpu,memory_free_mib=7751))
 def test_unknown_owner_waits(self):
  with self.assertRaises(t.ResourceUnavailable):self.admit(lookup=lambda pid:self.p if pid==10 else None)
 def test_parent_generation_hard_failure(self):
  with self.assertRaises(t.AdmissionIntegrityError):self.admit(lookup=lambda pid:dict(self.p,start_ticks=2) if pid==10 else self.lookup(pid))
 def test_missing_parent_nvml_waits(self):
  with self.assertRaises(t.ResourceUnavailable):self.admit(rows=self.rows[1:])
 def test_third_owned_card_waits(self):
  with self.assertRaises(t.ResourceUnavailable):self.admit(rows=self.rows+[{'gpu_uuid':'GPU-third','pid':30}],lookup=lambda pid:{'pid':pid,'uid':os.getuid()} if pid==30 else self.lookup(pid))
 def test_foreign_occupies_four_cards_while_own_uses_two(self):self.admit(rows=self.rows+[{'gpu_uuid':'GPU-third','pid':30},{'gpu_uuid':'GPU-fourth','pid':31}])
 def test_profile_exact_bound(self):self.assertEqual(t.decoder_memory_profile()['required_free_bytes'],5981077504+2*1024**3)
 def test_profile_tamper_hard(self):
  real=t.read_json
  def read(path):
   p=real(path)
   if Path(path).name=='decoder_memory_profile.json':p['required_free_bytes']-=1
   return p
  with patch.object(t,'read_json',side_effect=read),self.assertRaises(ValueError):t.decoder_memory_profile()
 def test_pending_formal_hard_bootstrap16GiB(self):
  with patch.object(t,'ROOT',C/'r55/overlay'):
   with self.assertRaises(ValueError):t.decoder_memory_profile()
   self.assertEqual(t.decoder_memory_profile(bootstrap=True)['required_free_bytes'],16*1024**3)
 def test_wait_recovery_with_actual_snapshot(self):
  c=Clock();events=[];count=[]
  def check(*args):
   count.append(1)
   if len(count)==1:raise t.ResourceUnavailable('low',{'free':1})
   return {'free':9000}
  with patch.object(t,'record_resource_event',side_effect=lambda p,v:events.append(v)):
   self.assertEqual(t.wait_decoder_admission(self.p,clock=c,sleep=c.sleep,check=check,is_alive=lambda p:True),{'free':9000})
  self.assertEqual(events[0]['snapshot'],{'free':1})
 def test_wait_hard_error_not_retried(self):
  check=lambda *a:(_ for _ in ()).throw(ValueError('data'))
  with self.assertRaisesRegex(ValueError,'data'):t.wait_decoder_admission(self.p,check=check,is_alive=lambda p:True)
 def test_wait_absolute_deadline(self):
  c=Clock();check=lambda *a:(_ for _ in ()).throw(t.ResourceUnavailable('low',{}))
  with self.assertRaises(TimeoutError):t.wait_decoder_admission(self.p,deadline=12,clock=c,sleep=c.sleep,check=check,is_alive=lambda p:True)
  self.assertEqual(c.now,12)
 def test_release_foreign_and_reused_pid(self):
  child={'returncode':0,'process':self.p}
  r=g.wait_own_child_released(t.DECODER_UUID,child,lambda p:dict(self.p,start_ticks=2),compute_pids=lambda:[10,21])
  self.assertTrue(r['pid_reused']);self.assertTrue(r['original_generation_absent'])
 def test_release_same_generation_hard(self):
  with self.assertRaises(RuntimeError):g.wait_own_child_released(t.DECODER_UUID,{'returncode':0,'process':self.p},lambda p:self.p,compute_pids=lambda:[10])
 def test_release_oom_requires_explicit_verified_path(self):
  child={'returncode':86,'process':self.p}
  with self.assertRaises(RuntimeError):g.wait_own_child_released(t.DECODER_UUID,child,lambda p:None,compute_pids=lambda:[])
  g.wait_own_child_released(t.DECODER_UUID,child,lambda p:None,compute_pids=lambda:[21],allow_cuda_oom=True)
 def test_release_own_tail_bounded(self):
  c=Clock()
  with self.assertRaises(TimeoutError):g.wait_own_child_released(t.DECODER_UUID,{'returncode':0,'process':self.p},lambda p:None,compute_pids=lambda:[10,21],timeout=1,clock=c,sleep=c.sleep)
 def test_only_typed_cuda_oom(self):
  class FakeOOM(RuntimeError):pass
  self.assertIsNone(t.typed_cuda_oom(RuntimeError('CUDA out of memory'),FakeOOM))
  self.assertIsNone(t.typed_cuda_oom(FakeOOM('CPU out of memory'),FakeOOM))
  self.assertTrue(t.typed_cuda_oom(FakeOOM('CUDA out of memory'),FakeOOM))
  wrapper=RuntimeError('tiled fallback forbidden');wrapper.__context__=FakeOOM('CUDA out of memory')
  self.assertTrue(t.typed_cuda_oom(wrapper,FakeOOM))
 def test_service_foreign_ok_and_no_resident_memory_gate(self):
  with patch.object(t,'admission_document',return_value={}),patch.object(srv,'proc_uid',return_value=os.getuid()+1):srv.check_admission({'permitted_compute_processes':[]},self.rows,{'queue_running':[],'queue_pending':[]})
 def test_service_unknown_own_identity_hard(self):
  with patch.object(t,'admission_document',return_value={}),patch.object(srv,'proc_uid',return_value=os.getuid()),patch.object(srv,'external_identity',return_value={}):
   with self.assertRaises(RuntimeError):srv.check_admission({'permitted_compute_processes':[]},self.rows[:1],{'queue_running':[],'queue_pending':[]})
 def test_main_memory_evidence_bound(self):self.assertEqual(srv.main_memory_profile()['required_free_bytes'],77968965632)
 def test_scientific_functions_unchanged(self):
  def functions(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
  before=functions(C/'r50/before/scripts/decode_live_child.py');after=functions(O/'scripts/decode_live_child.py')
  for name in ('load_snapshot','install_fallback_guard','write_video'):self.assertEqual(before[name],after[name])
  a=(C/'r50/before/scripts/decode_live_child.py').read_text();b=(O/'scripts/decode_live_child.py').read_text()
  self.assertEqual(a[a.index('    # Reuse the frozen'):a.index('\n\nfrom observer_import')],b[b.index('    # Reuse the frozen'):b.index('\n\nfrom observer_import')])
 def test_request_and_stop_guards_unchanged(self):
  def f(p,name):return ast.dump(next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
  for rel,name in [('extensions/H3AutomaticWindowRouter/transport.py','request'),('scripts/service.py','stop')]:self.assertEqual(f(C/'r50/before'/rel,name),f(O/rel,name))
 def retry_fixture(self,failures,advance=0,mutate=False,exit_code=86):
  folder=Path(tempfile.mkdtemp(dir=C/'test_tmp'));(folder/'request.json').write_text('{}')
  request={'parent':self.p,'endpoint_file':'/fixed/endpoint','endpoint_file_sha256':'ep','geometry':{'frames':158},'seed':123}
  record={'request_sha256':'request'};calls=[];releases=[];c=Clock()
  def runner(args,env,d,label,timeout,parent,**kw):
   calls.append((args,env,timeout,kw));attempt=Path(env['H3_DECODER_ATTEMPT_DIRECTORY']);c.now+=advance
   child={'returncode':exit_code if len(calls)<=failures else 0,'process':dict(self.p,pid=100+len(calls))}
   if child['returncode']:
    t.write_new(attempt/'decoder_oom.json',{'schema':'h3-typed-cuda-oom-v4','typed_cuda_oom':True,'identity':child['process'],'request_sha256':'request','exception_chain':[{'type':'FakeOOM','message':'CUDA out of memory'}],**{k:request[k] for k in ('endpoint_file_sha256','seed','geometry')}})
    raise t.ChildExitError('oom',child)
   (attempt/'native.mp4').write_bytes(b'video')
   t.write_new(attempt/'native.json',{'status':'complete','request_sha256':'request','snapshot_sha256':'ep','gpu_admission':{'owned_GPU_cards':[t.MAIN_UUID]}})
   return child
  admission=lambda *a,**kw: {'owned_GPU_cards':[t.MAIN_UUID]} if c.now<kw['deadline'] else (_ for _ in ()).throw(TimeoutError('absolute resource deadline'))
  patches=[patch.object(t,'sha',return_value='request'),patch.object(t,'request',side_effect=lambda p:dict(request,seed=999) if mutate else request),patch.object(t,'admission_document',return_value={}),patch.object(t,'wait_decoder_admission',side_effect=admission),patch.object(t,'run_child',side_effect=runner),patch.object(t,'record_resource_event'),patch.object(g,'wait_own_child_released',side_effect=lambda *a,**kw:releases.append((a,kw)) or {'released':True})]
  for p in patches:p.start()
  try:obs.decode_with_retries(request,str(folder/'request.json'),folder,{'comfy':'c','runtime_deps':'r','vae':'v','vae_sha256':'s'},self.p,record,clock=c)
  finally:
   for p in reversed(patches):p.stop()
  return calls,releases,record,folder
 def test_oom_retry_same_inputs_fresh_paths_and_release(self):
  calls,releases,record,folder=self.retry_fixture(1)
  self.assertEqual(len(calls),2);self.assertEqual(len(releases),2)
  self.assertEqual(calls[0][0][2],calls[1][0][2]);self.assertEqual(calls[0][1]['H3_DECODER_RESOURCE_DEADLINE'],calls[1][1]['H3_DECODER_RESOURCE_DEADLINE'])
  self.assertNotEqual(calls[0][1]['H3_DECODER_ATTEMPT_DIRECTORY'],calls[1][1]['H3_DECODER_ATTEMPT_DIRECTORY'])
  self.assertTrue((folder/'native.mp4').exists());self.assertTrue(releases[0][1]['allow_cuda_oom'])
  json.dumps(record,allow_nan=False)
 def test_oom_max_three_attempts(self):
  with self.assertRaisesRegex(RuntimeError,'after3'):self.retry_fixture(3)
 def test_mutated_input_hard_before_child(self):
  with self.assertRaisesRegex(ValueError,'immutable'):self.retry_fixture(0,mutate=True)
 def test_180_second_parent_race_removed(self):
  calls,*_=self.retry_fixture(0)
  self.assertEqual(calls[0][2],780);self.assertEqual(calls[0][3]['execution_timeout'],780)
 def test_retry_does_not_reset600deadline(self):
  with self.assertRaisesRegex(TimeoutError,'absolute'):self.retry_fixture(2,advance=350)
 def test_non_oom_exit_is_not_retried(self):
  with self.assertRaises(t.ChildExitError) as e:self.retry_fixture(1,exit_code=1)
  self.assertEqual(e.exception.result['process']['pid'],101)
 def test_oom_proof_wrong_seed_hard(self):
  folder=Path(tempfile.mkdtemp(dir=C/'test_tmp'));path=folder/'oom.json'
  proof={'schema':'h3-typed-cuda-oom-v4','identity':self.p,'request_sha256':'r','seed':999,'geometry':{},'endpoint_file_sha256':'e','typed_cuda_oom':True,'exception_chain':[{'type':'OOM'}]}
  t.write_new(path,proof)
  with self.assertRaisesRegex(ValueError,'seed'):t.validate_oom_proof(path,{'process':self.p,'returncode':86},{'seed':1,'geometry':{},'endpoint_file_sha256':'e'},'r')
 def test_response_contract_serializes_and_checks_measured_headroom(self):
  child={'process':self.p,'returncode':0}
  release=g.wait_own_child_released(t.DECODER_UUID,child,lambda p:None,compute_pids=lambda:[21])
  r={'parent':self.p,'request_id':'x'}
  response={'status':'complete','request_id':'x','request_sha256':'r','decoder_released_before_pose':True,'decoder_admission':self.admit(),'after_decoder_release':release,'decoder':child,'pose_process':{'returncode':0},'decoder_attempts':[{'status':'complete'}]}
  t.validate_response(json.loads(json.dumps(response)),r,'r')
  response['decoder_admission']['memory_free_mib']=7751
  with self.assertRaises(ValueError):t.validate_response(response,r,'r')
 def test_patches_reconstruct_exact_source(self):
  import shutil,subprocess
  folder=Path(tempfile.mkdtemp(dir=C/'test_tmp'))/'copy';shutil.copytree(C/'r50/before',folder)
  subprocess.run(['git','apply',str(C/'r50/candidate.patch')],cwd=folder,capture_output=True,check=True)
  for p in (C/'r50/before').rglob('*.py'):self.assertEqual((folder/p.relative_to(C/'r50/before')).read_bytes(),(O/p.relative_to(C/'r50/before')).read_bytes())
 def supervised_stage(self,finish):
  c=Clock();folder=Path(tempfile.mkdtemp(dir=C/'test_tmp'));marker=folder/'started.json';entry=dict(self.p,pid=200);state={'killed':False}
  class FakeProcess:
   pid=200;returncode=None
   def poll(inner):
    if inner.returncode is not None:return inner.returncode
    if c.now>=30 and not marker.exists():marker.write_text(json.dumps({'schema':'h3-child-execution-start-v1','identity':entry,'started_monotonic':c.now}))
    if c.now>=finish:inner.returncode=0
    return inner.returncode
  proc=FakeProcess()
  def terminate(process,identity):
   if process.poll() is None:state['killed']=True;process.returncode=-15
  with patch.object(t,'ROOT',folder.parent),patch.object(t,'inside',side_effect=lambda p,r:Path(p)),patch.object(t,'time',types.SimpleNamespace(monotonic=c,sleep=c.sleep)),patch.object(t,'identity',return_value=entry),patch.object(t,'alive',side_effect=lambda e:e==self.p or proc.returncode is None),patch.object(t,'terminate_owned',side_effect=terminate),patch.object(t.subprocess,'Popen',return_value=proc):
   try:result=t.run_child(['fake'],{},folder,'decoder',780,self.p,execution_started_path=marker,execution_timeout=780)
   except Exception as error:result=error
  return result,c.now,state
 def test_shared_compute_decode_over180_under780_succeeds(self):
  result,now,state=self.supervised_stage(400)
  self.assertEqual(result['returncode'],0);self.assertFalse(state['killed']);self.assertGreater(now-30,180)
 def test_shared_stage_over780_stops_and_reaps(self):
  result,now,state=self.supervised_stage(900)
  self.assertIsInstance(result,TimeoutError);self.assertTrue(state['killed']);self.assertLess(now,791)
 def test_all_candidate_python_compiles(self):
  for p in O.rglob('*.py'):compile(p.read_text(),str(p),'exec')
if __name__=='__main__':unittest.main(verbosity=2)
