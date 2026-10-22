import copy, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import common as c

class OfficialPrompt(unittest.TestCase):
    def test_both_graphs_use_exact_benchmark_instruction(self):
        p = c.info('short_0114')
        for run in (p['run_id'], p['forced_run_id']):
            c.verify_official_prompt(p, c.read(c.ROOT / 'configs/graphs' / (run + '.json')))

    def test_added_instruction_rejected(self):
        p = copy.deepcopy(c.info('short_0114'))
        p['prompt'] += '. Preserve all motions.'
        with self.assertRaises(ValueError): c.verify_official_prompt(p)

    def test_task_prefix_rejected(self):
        p = c.info('short_0114')
        g = c.read(c.ROOT / 'configs/graphs' / (p['run_id'] + '.json'))
        g['5']['inputs']['prompt'] = 'Edit <Video 1>: ' + p['prompt']
        with self.assertRaises(ValueError): c.verify_official_prompt(p, g)

    def test_reference_target_description_substitution_rejected(self):
        p = copy.deepcopy(c.info('short_0114'))
        p['prompt'] = p['original_task']['target_prompt']
        with self.assertRaises(ValueError): c.verify_official_prompt(p)

if __name__ == '__main__': unittest.main()
