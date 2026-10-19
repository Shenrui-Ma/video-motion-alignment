import importlib.util,json,pathlib,tempfile,unittest
R=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('r19_transport',R/'extensions/H3PoseObserverRouter/transport.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
class TransportTest(unittest.TestCase):
 def test_immutable(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'response.json';t.write_new(p,{'status':'complete'})
   with self.assertRaises(FileExistsError):t.write_new(p,{'status':'different'})
 def test_nonfinite_reject(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'bad.json';p.write_text('{"lag":NaN}')
   with self.assertRaises(ValueError):t.read_json(p)
 def test_path_escape(self):
  with tempfile.TemporaryDirectory() as d:
   for p in ('relative',str(pathlib.Path(d).parent/'elsewhere')):
    with self.assertRaises(ValueError):t.inside(p,d)
 def test_symlink_reject(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'x').touch();(p/'y').symlink_to(p/'x')
   with self.assertRaises(ValueError):t.inside(p/'y',d)
 def test_frozen_bindings(self):self.assertTrue(t.bindings()['external_files'])
if __name__=='__main__':unittest.main()

class ResponseTest(unittest.TestCase):
 def setUp(self):
  self.r={'request_id':'a','physical_index':10,'nfe_index':14,'endpoint_file_sha256':'b','condition_sha256':'c','reference_sha256':'d','seed':2026101311,'sigma':.9}
  self.response=dict(self.r,status='complete',request_sha256='e',decoder_released_before_pose=True,decoder={'returncode':0},pose_process={'returncode':0})
 def test_good(self):self.assertIs(t.validate_response(self.response,self.r,'e'),self.response)
 def test_stale_or_wrong_identity(self):
  for key in ('request_id','physical_index','nfe_index','endpoint_file_sha256','condition_sha256','reference_sha256','seed','sigma'):
   bad=dict(self.response);bad[key]='wrong'
   with self.assertRaises(ValueError):t.validate_response(bad,self.r,'e')
 def test_failure_not_unknown(self):
  for key,value in [('status','failed'),('decoder_released_before_pose',False),('request_sha256','stale')]:
   with self.assertRaises(ValueError):t.validate_response(dict(self.response,**{key:value}),self.r,'e')
