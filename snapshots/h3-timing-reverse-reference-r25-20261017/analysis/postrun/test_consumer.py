import importlib.util,json,tempfile,unittest
from pathlib import Path
P=Path(__file__).with_name('remote_consume.py');s=importlib.util.spec_from_file_location('remote',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
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
if __name__=='__main__':unittest.main()
