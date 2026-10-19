import copy,json,tempfile,time,unittest
from pathlib import Path
import remote_consume as m
class Finalize(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.root=self.base/'producer';self.arc=self.base/'archive';self.root.mkdir();self.arc.mkdir();self.run='run';self.owner={'pid':17,'identity':{'uid':1016,'start_ticks':'123','cmdline':'fixed'}}
  self.old={'jobs':['run'],'approved_continuations':[],'finalize':False}
  for root in [self.arc,self.root]:
   m.save(root/'configs/queue.json',self.old);(root/'blob.pt').write_bytes(b'unchanged')
  m.save(self.arc/'FILE_INVENTORY.json',{k:{'sha256':m.sha(self.arc/k)} for k in ['configs/queue.json','blob.pt']})
  m.save(self.arc/'RUN_GATE.json',{'passed':True,'owner':self.owner,'run_id':self.run})
  m.save(self.root/'configs/queue.json',dict(self.old,finalize=True))
  self.record={'unix':time.time()+1,'pid':17,'owner':self.owner['identity'],'gate_file':str(self.arc/'RUN_GATE.json'),'gate_sha256':m.sha(self.arc/'RUN_GATE.json')};self.putrecord()
 def putrecord(self):m.save(self.root/'audit/root_release_request.json',self.record)
 def verify(self):return m.verify_source_archive(self.root,self.arc,self.owner,self.run)
 def test_exact_transition_idempotent(self):self.assertEqual(self.verify(),self.verify())
 def test_no_change_accepted_without_record(self):m.save(self.root/'configs/queue.json',self.old);(self.root/'audit/root_release_request.json').unlink();self.assertIsNone(self.verify())
 def test_queue_rejects_other_fields(self):
  for extra in [{'jobs':['other']},{'approved_continuations':[{}]},{'extra':1},{'finalize':1}]:
   with self.subTest(extra=extra):
    m.save(self.root/'configs/queue.json',dict(self.old,finalize=True)|extra)
    with self.assertRaises(ValueError):self.verify()
 def test_wrong_owner_gate_or_time(self):
  original=copy.deepcopy(self.record)
  for field,value in [('pid',18),('owner',{'uid':1016}),('gate_file','wrong'),('gate_sha256','bad'),('unix',0)]:
   with self.subTest(field=field):
    self.record=copy.deepcopy(original);self.record[field]=value;self.putrecord()
    with self.assertRaises(ValueError):self.verify()
 def test_missing_record(self):
  (self.root/'audit/root_release_request.json').unlink()
  with self.assertRaises(FileNotFoundError):self.verify()
 def test_archive_changed(self):
  (self.arc/'blob.pt').write_bytes(b'changed')
  with self.assertRaises(ValueError):self.verify()
 def test_other_source_changed(self):
  (self.root/'blob.pt').write_bytes(b'changed')
  with self.assertRaises(ValueError):self.verify()
 def test_failed_gate(self):
  d=m.read(self.arc/'RUN_GATE.json');d['passed']=False;m.save(self.arc/'RUN_GATE.json',d)
  with self.assertRaises(ValueError):self.verify()
 def test_gate_other_owner(self):
  d=m.read(self.arc/'RUN_GATE.json');d['owner']={'pid':18};m.save(self.arc/'RUN_GATE.json',d)
  with self.assertRaises(ValueError):self.verify()
 def test_derived_hash_tamper_rejected_before_read(self):
  (self.arc/'derived.json').write_text('tampered')
  with self.assertRaisesRegex(ValueError,'recovery analysis binding'):m.validate_existing_analysis(self.arc,self.run,{},self.base/'source',{'derived.json':'bad'})
 def test_recovery_has_no_subprocess_sampling_or_pose(self):
  s=(Path(__file__).parent/'recover_existing.py').read_text()
  for forbidden in ['subprocess.run','load_runtime(','pose_probe.py','torch.load']:
   self.assertNotIn(forbidden,s)
if __name__=='__main__':unittest.main()
