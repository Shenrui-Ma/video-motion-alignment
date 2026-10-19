import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import execution_gate as gate
from r80_contract import sha
class Host9Recovery(unittest.TestCase):
 def fixture(self,path):
  d=path/'analysis/postrun/short_0230';d.mkdir(parents=True);(path/'configs').mkdir()
  old=d/'NATIVE_RUNTIME_GATE.json';old.write_text(json.dumps({'passed':False}))
  expected=path/'configs/expected_input_pixels_host9_v2.json';expected.write_text('{}')
  corrected=d/'NATIVE_RUNTIME_GATE_HOST9_v2.json'
  value={'schema':'r80-native-host9-decode-runtime-gate-v2','passed':True,'source_id':'short_0230','strict_decode_replay':{'passed':True,'expectation_sha256':sha(expected)},'legacy_gate':{'sha256':sha(old)}}
  corrected.write_text(json.dumps(value));return old,expected,corrected,value
 def test_failed_legacy_preserved_corrected_selected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);old,_,corrected,_=self.fixture(p);self.assertEqual(gate.first_native_gate(p),corrected);self.assertFalse(json.loads(old.read_text())['passed'])
 def test_changed_expectation_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);_,expected,_,_=self.fixture(p);expected.write_text('{"changed":true}')
   with self.assertRaisesRegex(ValueError,'expectation changed'):gate.first_native_gate(p)
 def test_changed_old_receipt_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);old,_,_,_=self.fixture(p);old.write_text('{"passed":false,"modified":true}')
   with self.assertRaisesRegex(ValueError,'historical failed gate changed'):gate.first_native_gate(p)
 def test_unsuccessful_replay_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);_,_,corrected,value=self.fixture(p);value['strict_decode_replay']['passed']=False;corrected.write_text(json.dumps(value))
   with self.assertRaisesRegex(ValueError,'replay source'):gate.first_native_gate(p)
if __name__=='__main__':unittest.main()
