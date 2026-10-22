import errno,hashlib,importlib.util,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parents[1]/'extensions/H3CachedCondition/__init__.py'
spec=importlib.util.spec_from_file_location('cached_for_copy_test',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CopyTests(unittest.TestCase):
 def test_exdev_exact_bytes_and_idempotence(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);a=p/'source';b=p/'target';a.write_bytes(b'fixed scientific bytes');h=m.sha(a)
   with patch.object(m.os,'link',side_effect=OSError(errno.EXDEV,'cross device')):m.publish_blob(a,b,h)
   self.assertEqual(a.read_bytes(),b.read_bytes());self.assertFalse(os.path.samefile(a,b));m.publish_blob(a,b,h)
 def test_hash_mismatch_does_not_publish(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);a=p/'source';b=p/'target';a.write_bytes(b'original')
   with patch.object(m.os,'link',side_effect=OSError(errno.EXDEV,'cross device')):
    with self.assertRaisesRegex(ValueError,'copy differs'):m.publish_blob(a,b,'0'*64)
   self.assertFalse(b.exists());self.assertEqual(list(p.glob('*.copy.*')),[])
 def test_other_errors_are_not_swallowed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);a=p/'source';a.write_bytes(b'x')
   with patch.object(m.os,'link',side_effect=PermissionError(errno.EACCES,'denied')):
    with self.assertRaises(PermissionError):m.publish_blob(a,p/'target',m.sha(a))
if __name__=='__main__':unittest.main()
