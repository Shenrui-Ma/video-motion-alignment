import copy,json,tempfile,unittest
from pathlib import Path
from merge_mf_manifests import merge
from ive_mf_adapter import SELECTION_SHA,sha,read_json

SELECTION=Path(__file__).resolve().parents[2]/'inputs_selection/PILOT_5_MANIFEST.json'
if not SELECTION.is_file():SELECTION=Path(__file__).resolve().parents[1]/'PILOT_5_MANIFEST.json'

class MergeIdentityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  media=self.root/'bound.dat';media.write_bytes(b'identity fixture, no generated video')
  binding={'file':str(media),'sha256':sha(media)}
  self.native={'schema':'h3-ivebench-official-mf-inputs-v1','selection_sha256':SELECTION_SHA,'methods':['native'],'pairs':[]}
  for e in read_json(SELECTION)['pairs']:
   self.native['pairs'].append({'pair_id':e['pair_id'],'source_original':copy.deepcopy(binding),'source_prepared_video':copy.deepcopy(binding),'source_score_video':copy.deepcopy(binding),'source_preparation_record':copy.deepcopy(binding),'score_frame_indices':list(range(e['input_protocol']['effective_frame_count'])),'input_to_original_frame':e['input_protocol']['input_to_original_frame'],'edited':{'native':{'fixture':True}}})
  self.auto=copy.deepcopy(self.native);self.auto['methods']=['auto']
  for row in self.auto['pairs']:row['edited']={'auto':{'fixture':True}}
 def tearDown(self):self.temp.cleanup()
 def attempt(self):
  paths=[]
  for name,data in [('native',self.native),('auto',self.auto)]:
   p=self.root/(name+'.json');p.write_text(json.dumps(data));paths.append(p)
  return merge(paths,SELECTION)
 def test_same_inputs_combine_two_methods_and_five_pairs(self):
  out=self.attempt();self.assertEqual(out['methods'],['native','auto']);self.assertEqual(len(out['pairs']),5)
  self.assertTrue(all(set(p['edited'])=={'native','auto'} for p in out['pairs']))
 def test_changed_prepared_input_rejected(self):
  p=self.root/'other.dat';p.write_bytes(b'other model input')
  self.auto['pairs'][0]['source_prepared_video']={'file':str(p),'sha256':sha(p)}
  with self.assertRaisesRegex(ValueError,'different source binding'):self.attempt()
 def test_changed_time_map_rejected(self):
  self.auto['pairs'][0]['input_to_original_frame'][0]=999
  with self.assertRaisesRegex(ValueError,'different time samples'):self.attempt()
 def test_incomplete_five_or_duplicate_method_rejected(self):
  self.auto['pairs'].pop()
  with self.assertRaisesRegex(ValueError,'all five'):self.attempt()
  self.auto=copy.deepcopy(self.native)
  with self.assertRaisesRegex(ValueError,'duplicate method'):self.attempt()

if __name__=='__main__':unittest.main()
