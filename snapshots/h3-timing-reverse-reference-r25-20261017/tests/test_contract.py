import importlib.util,json,sys,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r25_contract as c,prepare_lanes as b,preflight

def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class ContractTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name)
  for folder in ('scripts','configs','parent_evidence','extensions','inputs'):
   shutil.copytree(ROOT/folder,self.root/folder,ignore=shutil.ignore_patterns('__pycache__','graphs','runtime.json','queue.json','job_registry.json','admission.json'))
  self.run=b.configure(self.root,'reverse_block')
 def tearDown(self):self.t.cleanup()
 def write(self,rel,v):b.write(self.root/rel,v)
 def test_both_graphs_only_declared_changes(self):
  for arm in c.ARMS:
   run=b.configure(self.root,arm);g=c.read(self.root/'configs/graphs'/f'{run}.json');row=c.validate_job(run,self.root)
   self.assertEqual(g['6']['inputs']['noise_seed'],c.SEED);self.assertEqual(g['50']['inputs']['mode'],arm)
   self.assertEqual(preflight.check(self.root)['planned_NFE'],20)
   parent=c.read(self.root/'configs/parent_graph.json');self.assertEqual(set(k for k in g if g[k]!=parent[k]),{'5','6','14','50','51','52'})
 def test_graph_mutation_rejected_even_if_rehashed(self):
  p=self.root/'configs/graphs'/f'{self.run}.json';g=c.read(p);g['6']['inputs']['noise_seed']+=1;self.write(str(p.relative_to(self.root)),g)
  jobs=c.read(self.root/'configs/job_registry.json');jobs['jobs'][self.run]['graph_sha256']=c.sha(p);self.write('configs/job_registry.json',jobs)
  with self.assertRaises(ValueError):c.validate_job(self.run,self.root)
 def test_asset_mutation(self):
  name=next(iter(c.read(self.root/'configs/input_hashes.json')));(self.root/'inputs'/name).write_bytes(b'bad')
  with self.assertRaises(ValueError):c.validate_job(self.run,self.root)
 def test_unregistered_or_unsafe(self):
  for name in ('r3_s05_full_6to14','../evil'):
   with self.assertRaises(ValueError):c.validate_job(name,self.root)
 def test_queue_only_finalize(self):
  self.write('configs/queue.json',{'jobs':[self.run],'finalize':True});c.registry(self.root)
  self.write('configs/queue.json',{'jobs':[self.run,'extra'],'finalize':True})
  with self.assertRaises(ValueError):c.registry(self.root)
 def test_default_admission_closed(self):
  with self.assertRaises(ValueError):preflight.check(self.root,live=True)
 def test_actual_input_copy_and_corruption(self):
  c.prepare_loader_inputs(self.run,self.root);g=c.expected_graph(self.root,'reverse_block');p=self.root/'input'/g['22']['inputs']['file'];self.assertEqual(c.sha(p),c.read(self.root/'configs/input_hashes.json')[p.name]);p.write_bytes(b'bad')
  with self.assertRaises(ValueError):c.prepare_loader_inputs(self.run,self.root)
 def test_cleanup_identity_and_generation(self):
  svc=module('r25_svc',self.root/'scripts/service.py');(self.root/'processes').mkdir()
  ident={'uid':svc.os.getuid(),'start_ticks':'12','cmdline':f'{svc.CORE}/main.py {svc.RUN}'};rec={'pid':111,'identity':ident,'gpu_uuid':svc.GPU,'port':svc.PORT};self.write('processes/service.json',rec)
  with patch.object(svc,'current_identity',return_value=dict(ident,start_ticks='13')),patch.object(svc.os,'kill') as kill:
   with self.assertRaises(RuntimeError):svc.stop(expected_record=rec)
   kill.assert_not_called()
  self.write('processes/service.json',dict(rec,pid=222))
  with patch.object(svc.os,'kill') as kill:
   with self.assertRaises(RuntimeError):svc.stop(expected_record=rec)
   kill.assert_not_called()
 def test_idle_and_exact_two_gpu(self):
  svc=module('r25_svc2',self.root/'scripts/service.py')
  with patch.dict(sys.modules,{'service':svc}):
   job=module('r25_job',self.root/'scripts/job.py')
   with patch.dict(sys.modules,{'job':job}):q=module('r25_queue',self.root/'scripts/run_queue.py')
  self.assertEqual(q.idle_action({'finalize':False},1799,1800),'resident_hold');self.assertEqual(q.idle_action({'finalize':False},1800,1800),'bounded_idle_expired');self.assertEqual(q.idle_action({'finalize':True},0,1800),'final_close')
  self.assertEqual(q.remaining([self.run],[self.run]),[])
  self.assertNotIn('--cache-none',svc.command())
  uid=svc.os.getuid();identity={'uid':uid,'start_ticks':'20','cmdline_sha256':'a'*64};a={'scope':'own_user_video_jobs','permitted_compute_processes':[{'pid':222,'identity':identity}]};empty={'queue_running':[],'queue_pending':[]}
  with patch.object(svc,'proc_uid',return_value=uid),patch.object(svc,'external_identity',return_value=identity):
   svc.check_admission(a,[{'pid':222,'gpu_uuid':'other'}],empty)
   for rows in ([{'pid':222,'gpu_uuid':svc.GPU}],[{'pid':223,'gpu_uuid':'other'}],[{'pid':222,'gpu_uuid':'other'},{'pid':223,'gpu_uuid':'third'}]):
    with self.assertRaises(RuntimeError):svc.check_admission(a,rows,empty)
if __name__=='__main__':unittest.main()
