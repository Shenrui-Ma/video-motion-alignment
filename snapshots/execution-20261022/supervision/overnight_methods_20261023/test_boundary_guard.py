import unittest,copy,tempfile
from pathlib import Path
import boundary_guard as b
class T(unittest.TestCase):
 def setUp(self):
  self.base={'jobs':[{'id':'old'}]};self.req={'status':'ready','cpu_tests':{'passed':True},'base':self.base,'pilots':{'jobs':[{'id':'new','graph':'g','metadata':{'method':'x'}}]},'assets':[{'path':'a'}],'service_change':{'x':1}}
 def test_merge(self):self.assertEqual(len(b.validate_request(self.req,self.base)['jobs']),2)
 def test_duplicate(self):
  self.req['pilots']['jobs'][0]['id']='old'
  with self.assertRaises(AssertionError):b.validate_request(self.req,self.base)
 def test_unvalidated(self):
  self.req['cpu_tests']['passed']=False
  with self.assertRaises(AssertionError):b.validate_request(self.req,self.base)
 def test_external_change(self):
  with self.assertRaises(AssertionError):b.validate_request(self.req,{'jobs':[]})
 def fixture(self,root,name):
  p=root/name;s=root/(name+'.staged');p.write_text('value = 1\n');s.write_text('value = 2\n')
  return {'path':str(p),'staged_path':str(s),'before_sha256':b.sha(p),'after_sha256':b.sha(s)}
 def test_optional_empty_changes_and_idempotent_after(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=self.fixture(Path(tmp),'service.py');req={'service_change':c}
   b.apply_file_changes(b.prepare_file_changes(req));self.assertEqual(b.sha(c['path']),c['after_sha256'])
   req['additional_file_changes']=[];self.assertFalse(b.prepare_file_changes(req)[0][2])
 def test_multiple_files_and_partial_resume(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.fixture(Path(tmp),'service.py');c=self.fixture(Path(tmp),'durable.py');req={'service_change':a,'additional_file_changes':[c]}
   b.apply_file_changes(b.prepare_file_changes(req)[:1])
   prepared=b.prepare_file_changes(req);self.assertFalse(prepared[0][2]);self.assertTrue(prepared[1][2])
   b.apply_file_changes(prepared);self.assertEqual(b.sha(c['path']),c['after_sha256'])
 def test_bad_second_hash_leaves_first_unchanged(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.fixture(Path(tmp),'service.py');c=self.fixture(Path(tmp),'durable.py');Path(c['staged_path']).write_text('value = 3\n')
   with self.assertRaises(AssertionError):b.prepare_file_changes({'service_change':a,'additional_file_changes':[c]})
   self.assertEqual(b.sha(a['path']),a['before_sha256'])
 def test_bad_live_hash_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.fixture(Path(tmp),'service.py');Path(a['path']).write_text('value = 9\n')
   with self.assertRaises(AssertionError):b.prepare_file_changes({'service_change':a})
 def test_duplicate_file_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.fixture(Path(tmp),'service.py')
   with self.assertRaises(AssertionError):b.prepare_file_changes({'service_change':a,'additional_file_changes':[a]})
if __name__=='__main__':unittest.main()
