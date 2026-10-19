import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import job
class NativeGeneration(unittest.TestCase):
 def test_forced_requires_same_actual_native_owner(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'logs').mkdir();run='r89_short_0131_seed2026101701_native';owner={'pid':123,'identity':{'uid':1,'start_ticks':'new','cmdline':'x'}}
   (root/'logs'/(run+'_job.json')).write_text(json.dumps({'status':'success','service_pid':123,'service_identity':owner['identity']}));(root/'logs'/(run+'_history.json')).write_text(json.dumps({'status':{'status_str':'success','completed':True}}))
   with patch.object(job,'RUN',root):
    job.require_native_generation({'arm':'forced','source_id':'short_0131'},owner)
    with self.assertRaisesRegex(RuntimeError,'generation differs'):job.require_native_generation({'arm':'forced','source_id':'short_0131'},{'pid':124,'identity':owner['identity']})
 def test_native_does_not_require_prior_output(self):job.require_native_generation({'arm':'native'}, {})
if __name__=='__main__':unittest.main()
