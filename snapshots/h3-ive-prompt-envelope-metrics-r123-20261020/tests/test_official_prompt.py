import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
class OfficialPromptTests(unittest.TestCase):
 def test_prompt_envelope_and_final_verbatim_sentence(self):
  p=c.info('short_0358')
  self.assertEqual(p['prompt'],c.TASK_ENVELOPE+p['original_task']['edit_prompt'])
  self.assertEqual(p['prompt'].splitlines()[-1],'Add a pair of glasses to the man.')
 def test_unwrapped_prompt_rejected(self):
  p=copy.deepcopy(c.info('short_0358'));p['prompt']=p['original_task']['edit_prompt']
  with self.assertRaises(ValueError):c.verify_official_prompt(p)
 def test_exact_all_four_graphs(self):
  for source in c.SOURCES:
   p=c.info(source)
   for key in ('run_id','forced_run_id'):c.verify_official_prompt(p,c.read(c.ROOT/'configs/graphs'/f"{p[key]}.json"))
 def test_added_instruction_rejected(self):
  for source in c.SOURCES:
   p=copy.deepcopy(c.info(source));p['prompt']+=' Preserve the action.'
   with self.assertRaises(ValueError):c.verify_official_prompt(p)
 def test_prefix_rejected(self):
  for source in c.SOURCES:
   p=c.info(source);g=c.read(c.ROOT/'configs/graphs'/f"{p['run_id']}.json");g['5']['inputs']['prompt']='[video editing] '+p['prompt']
   with self.assertRaises(ValueError):c.verify_official_prompt(p,g)
 def test_target_description_rejected(self):
  for source in c.SOURCES:
   p=copy.deepcopy(c.info(source));p['prompt']=p['original_task']['target_prompt']
   with self.assertRaises(ValueError):c.verify_official_prompt(p)
