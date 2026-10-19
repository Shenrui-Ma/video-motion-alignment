import os,unittest
from test_pose_transport import t
class AdmissionTest(unittest.TestCase):
 def setUp(self):
  self.parent={'pid':123,'uid':os.getuid(),'start_ticks':12,'cmdline_sha256':'x'}
  self.gpu={'uuid':t.MAIN_UUID,'memory_free_mib':12288}
  self.processes=[{'pid':123,'gpu_uuid':t.MAIN_UUID}]
 def call(self,parent=None,gpu=None,processes=None,lookup=None,uuid=None):
  return t.validate_co_resident(parent or self.parent,uuid or t.MAIN_UUID,gpu or self.gpu,self.processes if processes is None else processes,lookup or (lambda pid:self.parent))
 def test_exact_parent_pass(self):self.assertEqual(self.call()['only_compute_parent'],self.parent)
 def test_foreign_duplicate_missing(self):
  for rows in ([],[{'pid':124,'gpu_uuid':t.MAIN_UUID}],self.processes*2,self.processes+[{'pid':124,'gpu_uuid':t.MAIN_UUID}]):
   with self.assertRaises(ValueError):self.call(processes=rows)
 def test_pid_reuse_or_missing(self):
  for found in (None,dict(self.parent,start_ticks=13)):
   with self.assertRaises(ValueError):self.call(lookup=lambda pid:found)
 def test_wrong_gpu(self):
  with self.assertRaises(ValueError):self.call(uuid='GPU-other')
 def test_headroom(self):
  with self.assertRaises(ValueError):self.call(gpu=dict(self.gpu,memory_free_mib=12287))
if __name__=='__main__':unittest.main()

class GlobalCardTest(unittest.TestCase):
 def setUp(self):
  self.entries={1:{'pid':1,'uid':os.getuid(),'start_ticks':11,'cmdline_sha256':'a'},2:{'pid':2,'uid':os.getuid(),'start_ticks':22,'cmdline_sha256':'b'},3:{'pid':3,'uid':os.getuid(),'start_ticks':33,'cmdline_sha256':'c'}}
  self.rows=[{'pid':1,'gpu_uuid':t.MAIN_UUID},{'pid':2,'gpu_uuid':t.SECOND_TASK_UUID}]
  self.allowed=[{'pid':2,'identity':dict(self.entries[2],start_ticks='22')}]
 def test_admitted_second_card(self):self.assertEqual(len(t.validate_owned_gpu_limit(self.rows,self.allowed,self.entries.get)),2)
 def test_third_card_reject(self):
  with self.assertRaises(ValueError):t.validate_owned_gpu_limit(self.rows+[{'pid':3,'gpu_uuid':'third'}],self.allowed,self.entries.get)
 def test_second_card_reused_or_unregistered(self):
  for permitted in ([],[{'pid':2,'identity':dict(self.entries[2],start_ticks='wrong')}]):
   with self.assertRaises(ValueError):t.validate_owned_gpu_limit(self.rows,permitted,self.entries.get)

 def test_wrong_second_GPU(self):
  rows=[self.rows[0],dict(self.rows[1],gpu_uuid='unexpected')]
  with self.assertRaises(ValueError):t.validate_owned_gpu_limit(rows,self.allowed,self.entries.get)

class AdmissionDocumentTest(unittest.TestCase):
 def test_only_explicit_admin_fields_mutable(self):
  import tempfile,json,pathlib
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'configs').mkdir()
   template={'fixed_fields':{'scope':'own_user_video_jobs','existing_comfy_port':None}}
   (r/'configs/admission_template.json').write_text(json.dumps(template))
   p=r/'configs/admission.json';good=dict(template['fixed_fields'],root_live_review_required=False,permitted_compute_processes=[])
   with patch.object(t,'ROOT',r):
    p.write_text(json.dumps(good));self.assertEqual(t.admission_document(approved=True),good)
    for bad in (dict(good,scope='all'),dict(good,existing_comfy_port=123),dict(good,extra=True),dict(good,root_live_review_required=True)):
     p.write_text(json.dumps(bad))
     with self.assertRaises(ValueError):t.admission_document(approved=True)
