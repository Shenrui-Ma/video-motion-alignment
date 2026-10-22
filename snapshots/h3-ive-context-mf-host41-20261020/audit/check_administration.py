from pathlib import Path
import sys,tempfile,types,json,unittest,ast,difflib,hashlib
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import gpu_coexistence as g,peer_support as p
from common import read,save

def row(pid,gpu,start='1'):return {'pid':pid,'uid':1004,'start_ticks':start,'cmdline_sha256':'a'*64,'gpu_uuid':gpu}
class Policy(unittest.TestCase):
 def test_known_user_excluded_but_preserved_in_observation(self):
  old=row(1,'user');h3=row(2,'h3');v=g.assess([old,h3],'tracker',[old],reserved_gpus=['h3']);self.assertTrue(v['passed']);self.assertEqual(v['owned_gpu_uuids_including_selected'],['h3','tracker']);self.assertEqual(len(v['observed_owned_cuda']),2)
 def test_reused_pid_not_exempt(self):
  v=g.assess([row(1,'user','2'),row(2,'h3')],'tracker',[row(1,'user')],reserved_gpus=['h3']);self.assertFalse(v['passed'])
 def test_reserved_peer_counts_before_cuda(self):self.assertFalse(g.assess([row(3,'other')],'tracker',[],reserved_gpus=['h3'])['passed'])
 def test_other_user_capacity_record_does_not_count(self):
  r=row(4,'external');r['uid']=1008;self.assertTrue(g.assess([r],'tracker',[],reserved_gpus=['h3'])['passed'])
 def test_registration_preserves_existing_entry(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);owner={'pid':5,'identity':{'uid':1004,'start_ticks':'12','cmdline':['service']}};peer={'root':str(root),'owner':owner};identity=types.SimpleNamespace(snapshot=lambda _:dict(actual=True),service_record=lambda _:owner['identity']);old={'pid':1,'identity':{'start_ticks':'1'}};entry={'pid':8,'identity':{'start_ticks':'2'}};path=root/'configs/admission.json';save(path,{'scope':'own_user_video_jobs','permitted_compute_processes':[old]});p.update_peer(peer,entry,identity);self.assertEqual(read(path)['permitted_compute_processes'],[old,entry]);p.update_peer(peer,entry,identity,remove=True);self.assertEqual(read(path)['permitted_compute_processes'],[old])
 def test_changed_owner_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);owner={'pid':5,'identity':{'uid':1004,'start_ticks':'12'}};peer={'root':str(root),'owner':owner};identity=types.SimpleNamespace(snapshot=lambda _:dict(actual=True),service_record=lambda _:dict(uid=1004,start_ticks='13'));path=root/'configs/admission.json';save(path,{'scope':'own_user_video_jobs','permitted_compute_processes':[]})
   with self.assertRaises(AssertionError):p.update_peer(peer,{'pid':8,'identity':{}},identity)
   self.assertEqual(read(path)['permitted_compute_processes'],[])
for q in (R/'scripts').glob('*.py'):ast.parse(q.read_text(),str(q))
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Policy));assert result.wasSuccessful()
old=R.parent/'h3-ive-r121-mf-host41-20261020';diffs=[]
for name in ['common.py','gpu_coexistence.py','run_batch.py']:diffs.extend(difflib.unified_diff((old/'scripts'/name).read_text().splitlines(True),(R/'scripts'/name).read_text().splitlines(True),fromfile='R121/'+name,tofile='context/'+name))
(R/'audit/ADMIN_DIFF.txt').write_text(''.join(diffs));save(R/'audit/ADMIN_CHECKS.json',{'passed':True,'tests':result.testsRun,'all_scripts_AST_passed':True,'track_byte_identical':(R/'scripts/track.py').read_bytes()==(old/'scripts/track.py').read_bytes(),'score_byte_identical':(R/'scripts/score.py').read_bytes()==(old/'scripts/score.py').read_bytes(),'capacity_byte_identical':(R/'scripts/capacity.py').read_bytes()==(old/'scripts/capacity.py').read_bytes(),'GPU_started':False})
