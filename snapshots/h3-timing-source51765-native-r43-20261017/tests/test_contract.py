import copy,json,os,sys,tempfile,threading,time,unittest,runpy,subprocess,hashlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r43_contract as c,preflight,service,job,start_controller,service_entry,launch_remote
class ContractTests(unittest.TestCase):
 def test_single_exact_parent_derived_graph(self):
  jobs,order=c.registry(ROOT);self.assertEqual(len(order),1);self.assertTrue(preflight.check(ROOT)['passed'])
  for run in order:
   row=c.validate_job(run,ROOT);g=c.read(ROOT/'configs/graphs'/f'{run}.json');self.assertEqual(g,c.expected_graph(ROOT,row['case']));self.assertEqual(g['50']['inputs']['step_start'],0);self.assertEqual(g['50']['inputs']['step_end'],20);self.assertEqual([g['50']['inputs'][x] for x in ('start_frame','end_frame')],[0,140]);self.assertEqual(g['6']['inputs']['noise_seed'],row['seed'])
 def test_old_parent_science_preserved(self):
  for run,row in c.registry(ROOT)[0].items():
   old=c.read(ROOT/row['case']['parent_graph']);g=c.read(ROOT/'configs/graphs'/f'{run}.json')
   for n in ('1','9','41'):
    if n in old:self.assertEqual(g[n],old[n])
   self.assertEqual(g['5']['inputs']['prompt'],c.PROMPT);self.assertNotEqual(g['5']['inputs']['prompt'],old['5']['inputs']['prompt']);self.assertEqual(g['6']['inputs']['noise_seed'],row['seed'])
 def test_scientific_mutations_rejected(self):
  jobs,order=c.registry(ROOT);run=order[0]
  for field,value in [('step_start',5),('end_frame',65),('alpha',.5),('mode','mass_preserve')]:
   original=c.read
   def altered(p):
    x=original(p)
    if Path(p).name==run+'.json':x['50']['inputs'][field]=value
    return x
   with patch.object(c,'read',side_effect=altered),self.assertRaises(ValueError):c.validate_job(run,ROOT)
 def test_integer_finalize_rejected(self):
  original=c.read
  def altered(p):
   x=original(p)
   if Path(p).name=='queue.json':x['finalize']=1
   return x
  with patch.object(c,'read',side_effect=altered),self.assertRaises(ValueError):c.registry(ROOT)
 def test_generation_submit_rejected(self):
  a={'pid':1,'identity':{'start_ticks':'1'}};b={'pid':2,'identity':{'start_ticks':'2'}}
  with self.assertRaises(RuntimeError):job.require_generation(a,b)
 def test_entry_is_same_process_no_subprocess(self):
  text=(ROOT/'scripts/service_entry.py').read_text();self.assertNotIn('subprocess',text);self.assertIn('runpy.run_path',text)
  cmd=service.command();self.assertEqual(Path(cmd[2]).name,'service_entry.py');self.assertEqual(Path(cmd[3]).name,'compatibility_bootstrap.py')
 def test_no_decoder_or_observer_nodes(self):
  self.assertEqual(sorted(p.name for p in (ROOT/'extensions').iterdir() if p.is_dir() and p.name!='__pycache__'),['H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout'])
class SingleSourceTests(unittest.TestCase):
 def test_actual_new_source_identity_and_noise_seed(self):
  jobs,order=c.registry(ROOT);self.assertEqual(len(order),1);run=order[0];row=jobs[run];g=c.read(ROOT/'configs/graphs'/f'{run}.json')
  self.assertEqual(row['source_id'],'51765');self.assertEqual(row['case']['identity'],'Sam Altman');self.assertEqual(g['6']['inputs']['noise_seed'],2026101701)
  self.assertIn('Sam Altman',g['5']['inputs']['prompt']);self.assertIn('headphones',g['5']['inputs']['prompt']);self.assertIn('exact timing',g['5']['inputs']['prompt']);self.assertNotIn('Elon Musk',g['5']['inputs']['prompt'])
 def test_wrong_source_seed_prompt_or_extra_case_rejected(self):
  original=c.read
  for mode in ('source','seed','prompt','extra'):
   def altered(p):
    x=original(p)
    if Path(p).name=='scientific_contract.json':
     if mode=='source':x['cases'][0]['source_id']='51310'
     if mode=='seed':x['cases'][0]['seed']=2026101702
     if mode=='prompt':x['cases'][0]['prompt']='different'
     if mode=='extra':x['cases'].append(copy.deepcopy(x['cases'][0]))
    return x
   with patch.object(c,'read',side_effect=altered),self.assertRaises(ValueError):c.registry(ROOT)
 def test_new_root_guard(self):
  self.assertEqual(c.audit_dir(str(c.REMOTE/'audit')),c.REMOTE/'audit')
  with self.assertRaises(ValueError):c.audit_dir('/data5/researcher/h3_runs/timing_new_actions_native_r38_20261017/audit')
 def test_frozen_design_inputs_and_numerical_bytes(self):
  for rel,h in c.read(ROOT/'configs/source_freeze.json').items():self.assertEqual(c.sha(ROOT/rel),h)
  for rel,row in c.read(ROOT/'configs/runtime_kernel_hashes.json').items():self.assertEqual(c.sha(ROOT/rel),row['current_sha256']);self.assertEqual(row['current_sha256'],row['parent_sha256'])
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
class NewSourceEvidenceTests(unittest.TestCase):
 def test_source_origin_and_integer_pts(self):
  selected=c.read(ROOT/'design/SOURCE_ONLY_SELECTION.json');self.assertEqual(selected['prepared_video_range_24fps'],[192,332]);self.assertEqual(selected['source_original_fps'],'24000/1001');self.assertIs(selected['inference_observed'],False)
  probe=c.read(ROOT/'design/INPUT_PROBE.json');frames=probe['frames'];self.assertEqual(len(frames),141);self.assertEqual([int(f['best_effort_timestamp']) for f in frames],[512*i for i in range(141)])
  self.assertTrue(all((f['width'],f['height'])==(1312,736) for f in frames));self.assertEqual(probe['streams'][0]['avg_frame_rate'],'24/1')
 def test_original_evidence_and_exact_sam_portrait(self):
  for row in c.read(ROOT/'configs/RAW_EVIDENCE_COPIES.json')['files']:self.assertEqual(c.sha(ROOT/row['target']),row['sha256'])
  row=c.registry(ROOT)[0][c.registry(ROOT)[1][0]];self.assertEqual(row['case']['portrait_sha256'],'4231440d7d8c8305b5f1bdd497ad699fee30e07443ba8ee681cedd19c1a7da42')
  review=c.read(ROOT/'design/SOURCE_POSE_REVIEW.json');self.assertEqual(review['prepared_video_sha256'],row['case']['video_sha256']);self.assertIs(review['source_only'],True)
 def test_gpu3_runtime_and_no_source_pose_policy(self):
  runtime=c.read(ROOT/'configs/runtime.json');self.assertEqual(runtime['gpu_uuid'],'GPU-REDACTED');self.assertEqual(runtime['port'],8505)
  run=c.registry(ROOT)[1][0];graph=c.read(ROOT/'configs/graphs'/f'{run}.json');self.assertTrue(all('pose' not in n['class_type'].lower() for n in graph.values()));self.assertNotIn('SOURCE_ONLY_SELECTION',json.dumps(graph))
if __name__=='__main__':unittest.main()
