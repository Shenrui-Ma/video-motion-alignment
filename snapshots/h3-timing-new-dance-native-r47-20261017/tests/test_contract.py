import copy,json,os,sys,tempfile,threading,time,unittest,runpy,subprocess,hashlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r47_contract as c,preflight,service,job,start_controller,service_entry,launch_remote
class AdmissionTests(unittest.TestCase):
 def test_transient_peer_child_wait_then_one_submission(self):
  owner={'pid':1,'identity':{'start_ticks':'1'}}
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'logs').mkdir()
   with patch.object(job,'RUN',p),patch.object(job,'active_service',return_value=owner),patch.object(job,'check_host_admission',side_effect=[RuntimeError('Unexpected host compute PID 2; refusing to start'),123.]),patch.object(job.time,'sleep') as sleep:
    self.assertEqual(job.wait_host_admission(owner),123.);sleep.assert_called_once()
 def test_peer_wait_actual_submit_once(self):
  owner={'pid':1,'identity':{'start_ticks':'1'}}
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for d in ('logs','processes','configs/graphs'):(root/d).mkdir(parents=True)
   graph=root/'configs/graphs/toy.json';graph.write_text('{"node":{}}');(root/'configs/queue.json').write_text('{}')
   answers={'/queue':{'queue_running':[],'queue_pending':[]},'/prompt':{'prompt_id':'one'}}
   with patch.object(job,'RUN',root),patch.object(c,'validate_job',return_value={'graph_sha256':hashlib.sha256(graph.read_bytes()).hexdigest()}),patch.object(c,'prepare_loader_inputs'),patch.object(job,'active_service',return_value=owner),patch.object(job,'check_host_admission',side_effect=[RuntimeError('Unexpected host compute PID 2; refusing to start'),123.]),patch.object(job.time,'sleep'),patch.object(job,'request',side_effect=lambda route,body=None:answers[route]) as req:
    result=job.submit('toy',expected_owner=owner)
   self.assertEqual(result['prompt_id'],'one');self.assertEqual([a.args[0] for a in req.call_args_list].count('/prompt'),1)
 def test_foreign_target_times_out_no_prompt(self):
  owner={'pid':1,'identity':{'start_ticks':'1'}}
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'logs').mkdir()
   with patch.object(job,'RUN',p),patch.object(job,'active_service',return_value=owner),patch.object(job,'check_host_admission',side_effect=RuntimeError('Selected GPU has active compute; refusing to start')),patch.object(job,'request') as request,self.assertRaises(TimeoutError):job.wait_host_admission(owner,timeout=0)
   request.assert_not_called()
 def test_owner_change_during_wait_rejected(self):
  with patch.object(job,'active_service',return_value={'pid':2,'identity':{}}),patch.object(job,'check_host_admission') as gate,self.assertRaises(RuntimeError):job.wait_host_admission({'pid':1,'identity':{}})
  gate.assert_not_called()
 def test_controller_exclusive_lock(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'processes').mkdir()
   with start_controller.controller_start_lock(p):
    with self.assertRaises(BlockingIOError):
     with start_controller.controller_start_lock(p):pass
 def test_stale_controller_admission(self):
  with self.assertRaises(ValueError):start_controller.admit(1,'1',{'pid':2,'identity':{'start_ticks':'2'}})
class PreCudaGateTests(unittest.TestCase):
 def gate(self,mode):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);target=d/'toy.py';target.write_text('value=42');ident=lambda:{'uid':1,'start_ticks':'9','cmdline_sha256':'a'*64};errors=[]
   def release():
    p=d/'cuda_gate_ready.json'
    for _ in range(1000):
     if p.exists():
      try:rec=json.loads(p.read_text());break
      except json.JSONDecodeError:pass
     time.sleep(.001)
    else:errors.append('no ready');return
    if mode=='bad':rec['pid']+=1
    (d/'cuda_gate_go.json').write_text(json.dumps(rec))
   if mode!='timeout':th=threading.Thread(target=release);th.start()
   try:result=service_entry.wait_gate(d,target,identity_fn=ident,timeout=.05 if mode=='timeout' else 2)
   finally:
    if mode!='timeout':th.join()
   self.assertFalse(errors);self.assertEqual(result['pid'],os.getpid());self.assertEqual(runpy.run_path(str(target))['value'],42)
 def test_exact_go_allows_same_pid(self):self.gate('good')
 def test_wrong_go_rejected(self):
  with self.assertRaises(ValueError):self.gate('bad')
 @unittest.skipUnless(Path('/proc/self/cmdline').exists(),'Linux /proc identity evidence')
 def test_real_child_pid_and_command_stay_identical(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);target=d/'target.py';target.write_text("import os,json\nfrom service_entry import identity\nfrom pathlib import Path\nPath("+repr(str(d/'done.json'))+").write_text(json.dumps({'pid':os.getpid(),'identity':identity()}))")
   code="import sys,runpy;sys.path.insert(0,"+repr(str(ROOT/'scripts'))+");from service_entry import wait_gate;wait_gate("+repr(str(d))+","+repr(str(target))+");runpy.run_path("+repr(str(target))+",run_name='__main__')"
   child=subprocess.Popen([sys.executable,'-c',code],env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
   try:
    for _ in range(1000):
     if (d/'cuda_gate_ready.json').exists():
      try:ready=json.loads((d/'cuda_gate_ready.json').read_text());break
      except json.JSONDecodeError:pass
     time.sleep(.002)
    else:self.fail('no ready')
    self.assertFalse((d/'done.json').exists());(d/'cuda_gate_go.json').write_text(json.dumps(ready));self.assertEqual(child.wait(timeout=5),0);done=json.loads((d/'done.json').read_text());self.assertEqual(done['pid'],child.pid);self.assertEqual(done['identity'],ready['identity'])
   finally:
    if child.poll() is None:child.terminate();child.wait(timeout=5)
 def test_timeout(self):
  with self.assertRaises(TimeoutError):self.gate('timeout')
class LaunchGenerationTests(unittest.TestCase):
 def test_repeated_launch_with_no_created_child_cannot_stop_old(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'processes').mkdir();(root/'processes/service.json').write_text(json.dumps({'pid':10,'identity':{'start_ticks':'old'}}));(root/'processes/supervisor_20.json').write_text(json.dumps({'pid':20,'identity':{'start_ticks':'new'}}))
   with patch.object(service,'stop') as stop:answer=launch_remote.cleanup_created_owner(root,20,{'start_ticks':'new'})
   stop.assert_not_called();self.assertFalse(answer['stopped'])
 def test_replacement_registry_not_stopped_by_old_launch(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'processes').mkdir();old={'pid':10,'identity':{'start_ticks':'old'}};new={'pid':11,'identity':{'start_ticks':'new'}};sup={'pid':20,'identity':{'start_ticks':'sup'},'service_pid':10,'service_identity':old['identity'],'service_record':old};(root/'processes/supervisor_20.json').write_text(json.dumps(sup));(root/'processes/service.json').write_text(json.dumps(new))
   with patch.object(service,'stop') as stop:answer=launch_remote.cleanup_created_owner(root,20,sup['identity'])
   stop.assert_not_called();self.assertFalse(answer['stopped'])
 def test_only_created_current_generation_can_stop(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'processes').mkdir();owner={'pid':10,'identity':{'start_ticks':'own'}};sup={'pid':20,'identity':{'start_ticks':'sup'},'service_pid':10,'service_identity':owner['identity'],'service_record':owner};(root/'processes/supervisor_20.json').write_text(json.dumps(sup));(root/'processes/service.json').write_text(json.dumps(owner))
   with patch.object(service,'stop',return_value={'stopped':True}) as stop:answer=launch_remote.cleanup_created_owner(root,20,sup['identity'])
   stop.assert_called_once_with(expected_record=owner);self.assertTrue(answer['stopped'])
   with patch.object(service,'stop') as stop:launch_remote.cleanup_created_owner(root,20,{'start_ticks':'other'})
   stop.assert_not_called()

class TwoSourceContractTests(unittest.TestCase):
 def test_declared_order_and_parent_numerics(self):
  jobs,order=c.registry(ROOT)
  self.assertEqual([jobs[r]['source_id'] for r in order],['10264579','6980766'])
  self.assertEqual([jobs[r]['case']['identity'] for r in order],['Sam Altman','Elon Musk'])
  self.assertTrue(preflight.check(ROOT)['passed'])
  self.assertEqual(preflight.check(ROOT)['planned_NFE'],40)
  for run,row in jobs.items():
   c.validate_job(run,ROOT)
   graph=c.read(ROOT/'configs/graphs'/f'{run}.json')
   parent=c.read(ROOT/row['case']['parent_graph'])
   self.assertEqual(graph,c.expected_graph(ROOT,row['case']))
   for n in ('1','2','3','4','8','9','10','11','12','13','41'):
    self.assertEqual(graph[n],parent[n])
   self.assertEqual(graph['5']['inputs']['prompt'],c.PROMPTS[row['source_id']])
   self.assertEqual(graph['6']['inputs']['noise_seed'],2026101701)
 def test_wrong_identity_seed_source_prompt_extra_rejected(self):
  original=c.read
  for mode in ('identity','seed','source','prompt','extra','portrait','reverse'):
   def altered(p):
    x=original(p)
    if Path(p).name=='scientific_contract.json':
     if mode=='identity':x['cases'][1]['identity']='Sam Altman'
     if mode=='seed':x['cases'][1]['seed']=2026101702
     if mode=='source':x['cases'][1]['source_id']='51765'
     if mode=='prompt':x['cases'][1]['prompt']='different'
     if mode=='portrait':x['cases'][1]['portrait_sha256']=x['cases'][0]['portrait_sha256']
     if mode=='extra':x['cases'].append(copy.deepcopy(x['cases'][0]))
     if mode=='reverse':x['cases'].reverse()
    return x
   with self.subTest(mode=mode),patch.object(c,'read',side_effect=altered),self.assertRaises(ValueError):c.registry(ROOT)
 def test_queue_reverse_duplicate_or_integer_finalize_rejected(self):
  original=c.read
  for mode in ('reverse','duplicate','integer'):
   def altered(p):
    x=original(p)
    if Path(p).name=='queue.json':
     if mode=='reverse':x['jobs'].reverse()
     if mode=='duplicate':x['jobs'][1]=x['jobs'][0]
     if mode=='integer':x['finalize']=1
    return x
   with self.subTest(mode=mode),patch.object(c,'read',side_effect=altered),self.assertRaises(ValueError):c.registry(ROOT)
 def test_scientific_graph_mutation_rejected(self):
  original=c.read;run=c.registry(ROOT)[1][1]
  for field,value in [('step_start',5),('end_frame',65),('alpha',.5),('mode','mass_preserve')]:
   def altered(p):
    x=original(p)
    if Path(p).name==run+'.json':x['50']['inputs'][field]=value
    return x
   with patch.object(c,'read',side_effect=altered),self.assertRaises(ValueError):c.validate_job(run,ROOT)
 def test_exact_native_router_guard(self):
  run=c.registry(ROOT)[1][0]
  args=('native',1.,0,0,0,140,0,50,0,20,run,str(c.REMOTE/'audit/router'))
  c.validate_router(*args)
  with self.assertRaises(ValueError):c.validate_router(*(('mass_preserve',)+args[1:]))
 def test_inputs_geometry_and_portraits(self):
  for source,start in [('10264579',366),('6980766',192)]:
   p=c.read(ROOT/'design'/f'INPUT_PROBE_{source}.json')
   self.assertEqual(len(p['frames']),141)
   self.assertEqual([int(f['best_effort_timestamp']) for f in p['frames']],[512*i for i in range(141)])
   self.assertTrue(all((f['width'],f['height'])==(1312,736) for f in p['frames']))
   provenance=c.read(ROOT/'inputs'/f'source_{source}_provenance.json')
   self.assertEqual(provenance['normalized_24fps_source_indices_inclusive'],[start,start+140])
   self.assertEqual(provenance['geometry']['scaled'],[1396,736])
   self.assertEqual(provenance['geometry']['crop'],[42,0,1312,736])
   self.assertEqual(provenance['portrait_sha256'],c.PORTRAITS[source])
   self.assertFalse(provenance['inference_observed'])
 def test_runtime_and_numeric_hashes(self):
  r=c.read(ROOT/'configs/runtime.json')
  self.assertEqual(r['gpu_uuid'],'GPU-REDACTED');self.assertEqual(r['port'],8509)
  self.assertFalse(c.read(ROOT/'configs/admission.json')['ready_for_launch'])
  for rel,row in c.read(ROOT/'configs/runtime_kernel_hashes.json').items():
   self.assertEqual(c.sha(ROOT/rel),row['current_sha256']);self.assertEqual(row['parent_sha256'],row['current_sha256'])
 def test_no_observer_node_and_same_pid_gate(self):
  self.assertEqual(sorted(p.name for p in (ROOT/'extensions').iterdir() if p.is_dir() and p.name!='__pycache__'),['H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout'])
  text=(ROOT/'scripts/service_entry.py').read_text();self.assertNotIn('subprocess',text);self.assertIn('runpy.run_path',text)
  cmd=service.command();self.assertEqual(Path(cmd[2]).name,'service_entry.py')
  for run in c.registry(ROOT)[1]:
   graph=c.read(ROOT/'configs/graphs'/f'{run}.json')
   self.assertFalse(any('observer' in n['class_type'].lower() or 'pose' in n['class_type'].lower() for n in graph.values()))
class SerialQueueTests(unittest.TestCase):
 def test_two_jobs_one_owner_in_order_once(self):
  import run_queue
  jobs,order=c.registry(ROOT);owner={'pid':123,'identity':{'start_ticks':'9'}}
  policy={'max_service_seconds':30,'job_timeout_seconds':10,'idle_hold_seconds':1}
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'logs').mkdir()
   def rd(p):
    name=Path(p).name
    if name=='service.json':return owner
    if name=='scientific_contract.json':return {'continuous':policy}
    if name=='queue.json':return {'jobs':order,'finalize':True}
    if name.endswith('_history.json'):return {'status':{'completed':True}}
    raise AssertionError(name)
   with patch.object(service,'RUN',root),patch.object(preflight,'check'),patch.object(service,'assert_owned'),patch.object(service,'residency_snapshot',return_value={'service':owner}),patch.object(service,'stop') as stop,patch.object(run_queue,'read',side_effect=rd),patch.object(run_queue,'registry',return_value=(jobs,order)),patch.object(job,'submit') as submit,patch.object(job,'status',return_value={'status':'success'}),patch.object(run_queue.subprocess,'run',return_value=type('Result',(),{'stdout':'GPU,1,0,30'})()):
    run_queue.run(expected_pid=123,expected_start_ticks='9')
   self.assertEqual([x.args[0] for x in submit.call_args_list],order)
   self.assertTrue(all(x.kwargs['expected_owner']==owner for x in submit.call_args_list))
   stop.assert_called_once_with(expected_record=owner)
 def test_completed_prefix_reorder_rejected(self):
  import run_queue
  with self.assertRaises(ValueError):run_queue.remaining(['a','b'],['b'])

if __name__=='__main__':unittest.main()
