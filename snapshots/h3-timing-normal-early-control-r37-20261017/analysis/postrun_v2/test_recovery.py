import ast,copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import recovery as r

class RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.e=r.read(HERE/'RECOVERY_EVIDENCE.json');self.b=r.read(HERE/'SOURCE_POSE_PROVENANCE_EXCEPTION.json')
 def test_exact_registered_provenance(self):
  self.assertTrue(r.check_pose_provenance(self.e['source_provenance'],self.e['generated_provenance'],self.b['source_sha256'])['other19_fields_exact'])
 def test_wrong_source_rejected(self):
  with self.assertRaises(ValueError):r.check_pose_provenance(self.e['source_provenance'],self.e['generated_provenance'],'0'*64)
 def test_wrong_script_and_every_other_field_rejected(self):
  for side in ('source_provenance','generated_provenance'):
   for key in self.e[side]:
    e=copy.deepcopy(self.e);e[side][key]='corrupt'
    with self.subTest(side=side,key=key),self.assertRaises(ValueError):r.check_pose_provenance(e['source_provenance'],e['generated_provenance'],self.b['source_sha256'])
 def test_extra_field_rejected(self):
  s=dict(self.e['source_provenance'],extra=True);g=dict(self.e['generated_provenance'],extra=True)
  with self.assertRaises(ValueError):r.check_pose_provenance(s,g,self.b['source_sha256'])
 def fixture(self,folder):
  folder.mkdir();video=folder.parent/'video';video.write_bytes(b'video');source=folder.parent/'source';source.write_bytes(b'source');p=folder/'pose.json'
  raw={'video':{'sha256':r.sha(video),'width':1312,'height':736,'container_frame_count':141,'fps':24},'extraction':{'start':0,'end':None,'stride':1},'statistics':{'processed_frames':141},'frames':[{'frame':i,'time_s':i/24} for i in range(141)]};r.save(p,raw)
  e={'files':{'pose.json':{'sha256':r.sha(p),'bytes':p.stat().st_size}},'pose_relative':'pose.json','pose_sha256':r.sha(p),'video_sha256':r.sha(video),'source_pose_sha256':r.sha(source),'statistics':raw['statistics']};return video,source,p,e
 def test_exact_cached_inventory(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'pose';v,s,p,e=self.fixture(f);self.assertEqual(r.check_cached(f,v,s,e)[0],p)
 def test_cached_corruption_and_extra_missing(self):
  for how in ('extra','missing','pose','video','source'):
   with self.subTest(how=how),tempfile.TemporaryDirectory() as d:
    f=Path(d)/'pose';v,s,p,e=self.fixture(f)
    if how=='extra':(f/'unexpected').write_text('bad')
    elif how=='missing':p.unlink()
    else:{'pose':p,'video':v,'source':s}[how].write_text('changed')
    with self.assertRaises(ValueError):r.check_cached(f,v,s,e)
 def test_cached_bad_timebase_even_if_rehashed(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'pose';v,s,p,e=self.fixture(f);a=r.read(p);a['frames'][4]['time_s']=0;r.save(p,a);e['pose_sha256']=e['files']['pose.json']['sha256']=r.sha(p);e['files']['pose.json']['bytes']=p.stat().st_size
   with self.assertRaises(ValueError):r.check_cached(f,v,s,e)
 def test_no_pose_subprocess_in_recovery(self):
  node=next(n for n in ast.parse((HERE/'recovery.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='recover_pose')
  self.assertNotIn('subprocess',ast.dump(node));self.assertNotIn('execute',ast.dump(node))
 def test_shared_archive_and_lock_bound(self):
  p=r.read(HERE/'PROTOCOL.json');self.assertEqual(p['recovery']['archive_root'],self.e['archive_root']);self.assertIn("legacy_local",(HERE/'one_phase.py').read_text());self.assertIn("P['recovery']['archive_root']",(HERE/'consume.py').read_text())

if __name__=='__main__':unittest.main()
