import copy, json, sys, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import r108_contract as c

class RecoveryContract(unittest.TestCase):
    def test_only_unsubmitted_fireplace_is_registered(self):
        jobs,order=c.registry()
        self.assertEqual(c.SOURCES,('short_0392',))
        self.assertEqual(len(order),2)
        self.assertEqual([jobs[r]['arm'] for r in order],['native','forced'])
        self.assertTrue(all(jobs[r]['case']['valid_frame_count']==57 for r in order))

    def test_parent_graphs_have_identical_science(self):
        parent=ROOT/'source_snapshot/r100_parent'
        before=c.read(parent/'configs/runtime.json')['remote_root']
        after=c.read(ROOT/'configs/runtime.json')['remote_root']
        for arm in c.ARMS:
            old=c.read(parent/'configs/graphs'/f'r100_short_0392_seed2026101701_{arm}.json')
            expected=json.loads(json.dumps(old).replace(before,after).replace('r100_short_0392','r108_short_0392'))
            actual=c.read(ROOT/'configs/graphs'/f'r108_short_0392_seed2026101701_{arm}.json')
            self.assertEqual(actual,expected)
        self.assertEqual(c.sha(ROOT/'configs/prompts/short_0392.txt'),c.sha(parent/'configs/prompts/short_0392.txt'))

    def test_full_padding_guidance_is_rejected(self):
        original=c.read
        def changed(path):
            value=original(path)
            if Path(path).name=='r108_short_0392_seed2026101701_forced.json':
                value=copy.deepcopy(value);value['50']['inputs']['end_frame']=72
            return value
        with patch.object(c,'read',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'graph numerical'):
                c.registry()

    def test_prompt_change_is_rejected(self):
        original=c.read
        def changed(path):
            value=original(path)
            if Path(path).name=='scientific_contract.json':
                value=copy.deepcopy(value);value['cases'][0]['prompt']+=' new gesture'
            return value
        with patch.object(c,'read',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'prompt'):
                c.registry()

if __name__=='__main__':unittest.main()
