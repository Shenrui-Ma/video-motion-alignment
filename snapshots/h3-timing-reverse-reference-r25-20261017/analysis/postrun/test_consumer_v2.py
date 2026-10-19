import importlib.util,json,tempfile,unittest
from pathlib import Path
P=Path(__file__).with_name('remote_consume_v2.py');s=importlib.util.spec_from_file_location('remote',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Contract(unittest.TestCase):
 def test_exact_output(self):
  h={'outputs':{'14':{'images':[{'filename':'r25_s05_reverse_same_6to14_00001_.mp4','type':'output','subfolder':''}]}}}
  self.assertEqual(m.output_file(Path('/tmp'),h,'r25_s05_reverse_same_6to14').name,'r25_s05_reverse_same_6to14_00001_.mp4')
 def test_wrong_run(self):
  h={'outputs':{'14':{'images':[{'filename':'bench_00001_.mp4','type':'output','subfolder':''}]}}}
  with self.assertRaises(ValueError):m.output_file(Path('/tmp'),h,'r25_s05_reverse_same_6to14')
 def test_ambiguous_output(self):
  with self.assertRaises(ValueError):m.output_file(Path('/tmp'),{'outputs':{'14':{'images':[]}}},'r25')
 def test_traversal(self):
  with self.assertRaises(ValueError):m.safe(Path('/tmp'),'../x')
 def test_absolute(self):
  with self.assertRaises(ValueError):m.safe(Path('/tmp'),'/x')
 def test_symlink(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'link').symlink_to('/tmp')
   with self.assertRaises(ValueError):m.safe(p,'link')
 def test_unknown_kept(self):
  with tempfile.TemporaryDirectory() as d:
   r=m.compact(Path(d));self.assertEqual(r,{'0.3':{'status':'UNKNOWN'},'0.5':{'status':'UNKNOWN'}})


class Recovery(unittest.TestCase):
 def setUp(self):
  self.generated={'script_sha256':m.HASHES['scripts/pose_probe.py'],'detector_sha256':'fixed-detector','pose_sha256':'fixed-pose','person_selection':'fixed-largest-then-iou','threads':4}
  self.source=dict(self.generated,script_sha256='b0eb01e8a0d24049cff8880dc3f356a177ada760cc919a31cfbd11ee7f82fa89')
 def test_explicit_legacy_source_allowed(self):
  m.check_pose_provenance(self.source,self.generated,[self.generated.copy(),self.generated.copy()])
 def test_wrong_legacy_script_rejected(self):
  with self.assertRaises(ValueError):m.check_pose_provenance(dict(self.source,script_sha256='other'),self.generated,[self.generated])
 def test_wrong_generated_script_rejected(self):
  with self.assertRaises(ValueError):m.check_pose_provenance(self.source,dict(self.generated,script_sha256='other'),[self.generated])
 def test_weights_mismatch_rejected(self):
  with self.assertRaises(ValueError):m.check_pose_provenance(dict(self.source,pose_sha256='changed'),self.generated,[self.generated])
 def test_selection_mismatch_rejected(self):
  with self.assertRaises(ValueError):m.check_pose_provenance(dict(self.source,person_selection='changed'),self.generated,[self.generated])
 def test_parent_mismatch_rejected(self):
  with self.assertRaises(ValueError):m.check_pose_provenance(self.source,self.generated,[dict(self.generated,threads=8)])
 def test_missing_provenance_field_rejected(self):
  s=self.source.copy();del s['detector_sha256']
  with self.assertRaises(ValueError):m.check_pose_provenance(s,self.generated,[self.generated])
 def test_cache_registered_exact_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);a=p/'pose';b=p/'video';a.write_bytes(b'pose');b.write_bytes(b'video');r={'reused_pose':{'r':{'pose_sha256':m.sha(a),'video_sha256':m.sha(b)}}}
   m.check_cached_pose('r',a,b,r)
   with self.assertRaises(ValueError):m.check_cached_pose('wrong_run',a,b,r)
   b.write_bytes(b'wrong source')
   with self.assertRaises(ValueError):m.check_cached_pose('r',a,b,r)
 def test_partial_archive_mutation_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'raw').write_bytes(b'original');inv={'raw':{'sha256':m.sha(p/'raw'),'bytes':8}}
   m.save(p/'FILE_INVENTORY.json',inv);m.save(p/'RUN_GATE.json',{'passed':True});m.check_partial_archive(p,inv)
   (p/'raw').write_bytes(b'mutated')
   with self.assertRaises(ValueError):m.check_partial_archive(p,inv)
 def test_partial_archive_unverified_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):m.check_partial_archive(Path(d),{})
if __name__=='__main__':unittest.main()
