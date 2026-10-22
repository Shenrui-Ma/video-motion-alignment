"""CPU fake HTTP checks of the production combined startup and one-job queue."""
import contextlib,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import start_controller as start, r132_contract as contract, service, job, run_queue, execution_gate
class Startup(unittest.TestCase):
 def test_combined_http_accepts_registered_types(self):
  info={n['class_type']:{} for n in contract.expected_graph().values()}
  self.assertNotIn('H3ReferenceOrigin',info)
  with patch.object(start.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(info).encode())) as http:
   self.assertTrue(start.check_http_schema(ROOT,8628)['passed'])
   self.assertTrue(http.call_args.args[0].endswith('/object_info'))
 def test_combined_http_missing_node_rejects(self):
  info={n['class_type']:{} for n in contract.expected_graph().values()};del info['H3FixedPhaseCombined']
  with patch.object(start.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(info).encode())):
   with self.assertRaisesRegex(ValueError,'H3FixedPhaseCombined'):start.check_http_schema(ROOT,8628)
 def test_actual_queue_submits_combined_graph_once(self):
  run=contract.RUN_ID;binding=contract.registry()[0][run];owner={'pid':123,'identity':{'uid':1004,'start_ticks':'456','cmdline':'owned'}}
  posts=[]
  def http(req,timeout=30):
   route=req.full_url.rsplit('/',1)[-1]
   if route=='queue':value={'queue_running':[],'queue_pending':[]}
   elif route=='prompt':posts.append(json.loads(req.data));value={'prompt_id':'test-combined'}
   elif route=='test-combined':value={'test-combined':{'status':{'status_str':'success','completed':True},'outputs':{}}}
   else:raise AssertionError(req.full_url)
   return io.BytesIO(json.dumps(value).encode())
  with tempfile.TemporaryDirectory() as tmp,contextlib.ExitStack() as stack:
   root=Path(tmp)
   for d in ('configs/graphs','processes','logs'): (root/d).mkdir(parents=True)
   def write(rel,v):(root/rel).write_text(json.dumps(v))
   write('configs/graphs/'+run+'.json',contract.expected_graph());write('configs/queue.json',{'jobs':[run],'finalize':True});write('configs/scientific_contract.json',contract.science());write('processes/service.json',owner)
   binding=dict(binding,graph_sha256=contract.sha(root/'configs/graphs'/(run+'.json')))
   for target,name,value in ((service,'RUN',root),(job,'RUN',root)) :stack.enter_context(patch.object(target,name,value))
   for target,name,kwargs in ((run_queue,'wait_controller_registration',{'return_value':{}}),(run_queue.preflight,'check',{'return_value':{}}),(service,'assert_owned',{}),(service,'residency_snapshot',{}),(run_queue,'record_resources',{}),(service,'stop',{}),(execution_gate,'admitted_job',{'return_value':True}),(contract,'validate_job',{'return_value':binding}),(contract,'prepare_loader_inputs',{'return_value':binding}),(job,'wait_host_admission',{'return_value':0}),(job.urllib.request,'urlopen',{'side_effect':http}),(run_queue.subprocess,'run',{'return_value':Mock(returncode=0)})):
    stack.enter_context(patch.object(target,name,**kwargs))
   with contextlib.redirect_stdout(io.StringIO()):run_queue.run(123,'456')
   self.assertEqual(len(posts),1);self.assertEqual(posts[0]['prompt']['50']['class_type'],'H3FixedPhaseCombined')
   self.assertEqual(json.loads((root/'logs/controller_state.json').read_text())['status'],'all_sources_finished')
   service.stop.assert_called_once_with(expected_record=owner)
 def test_runtime_gpu_labels_match(self):
  runtime=contract.read(ROOT/'configs/runtime.json');self.assertEqual(runtime['expected_gpu_index'],runtime['gpu_index'])
if __name__=='__main__':unittest.main()
