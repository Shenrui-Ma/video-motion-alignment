import json,tempfile,unittest
from pathlib import Path
from contract import save,sha,verify_phase_dependencies,verify_archive_anchor

class PhaseDependencyTests(unittest.TestCase):
 def fixture(self,base):
  root=base/'producer';arc=base/'postrun/captured/run';root.mkdir();arc.mkdir(parents=True)
  inv={}
  for name,value in [('current.pt',b'current'),('unrelated.pt',b'not a phase dependency'),('source.pose.json',b'{}')]:
   for folder in (root,arc):(folder/name).write_bytes(value)
   inv[name]={'bytes':len(value),'sha256':sha(arc/name)}
  save(arc/'FILE_INVENTORY.json',inv)
  return root,arc
 def test_only_selected_dependencies_read(self):
  with tempfile.TemporaryDirectory() as d:
   root,arc=self.fixture(Path(d));(root/'unrelated.pt').unlink();(arc/'unrelated.pt').unlink()
   self.assertEqual(set(verify_phase_dependencies(root,arc,['current.pt','source.pose.json'])),{'current.pt','source.pose.json'})
 def test_current_source_or_copy_tampering_rejected(self):
  for which in ('producer','copy'):
   with tempfile.TemporaryDirectory() as d:
    root,arc=self.fixture(Path(d));((root if which=='producer' else arc)/'current.pt').write_bytes(b'changed')
    with self.assertRaises(ValueError):verify_phase_dependencies(root,arc,['current.pt'])
 def test_unregistered_and_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root,arc=self.fixture(Path(d))
   for value in ('../current.pt','missing.pt'):
    with self.assertRaises(ValueError):verify_phase_dependencies(root,arc,[value])
 def test_inventory_and_gate_pins_reject_tampering(self):
  with tempfile.TemporaryDirectory() as d:
   root,arc=self.fixture(Path(d));owner={'pid':1,'identity':{'start':'fixed'}}
   save(arc/'RUN_GATE.json',{'passed':True,'run_id':'run','owner':owner,'file_inventory_sha256':sha(arc/'FILE_INVENTORY.json')})
   save(arc.parent.parent/'archive_receipts/run.json',{'run_id':'run','owner':owner,'run_gate_sha256':sha(arc/'RUN_GATE.json'),'inventory_sha256':sha(arc/'FILE_INVENTORY.json')})
   verify_archive_anchor(arc,'run',owner)
   (arc/'FILE_INVENTORY.json').write_text('{}')
   with self.assertRaises(ValueError):verify_archive_anchor(arc,'run',owner)

if __name__=='__main__':unittest.main()
