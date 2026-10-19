"""Lightweight template binding checks; no actual parent execution is claimed."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_graphs import derive, diff


class PreparedGraphs(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((ROOT/'configs/protocol.json').read_text())['cases']

    def parent(self, case):
        return json.loads((ROOT/'configs/parent_graphs'/(case['parent_run']+'.json')).read_text())

    def test_all_five_graphs_preserve_numerical_inputs(self):
        record = json.loads((ROOT/'audit/GRAPH_PREPARATION.json').read_text())
        self.assertIs(record['deployable'], False)
        self.assertIs(record['actual_parent_history_verified'], False)
        self.assertEqual(len(record['cases']), 5)
        for case, receipt in zip(self.cases, record['cases']):
            with self.subTest(source=case['source_id']):
                old = self.parent(case)
                path = ROOT/receipt['graph']
                new = json.loads(path.read_text())
                self.assertEqual(new, derive(old, case))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),receipt['graph_sha256'])
                self.assertEqual(diff(old, new), receipt['diff'])
                for key in ('1','2','3','4','7','8','9','10','11','12','13','21','22','23','41'):
                    self.assertEqual(old[key], new[key])
                for field in ('prompt','width','height','length','semantic_fps','phase_frames','ref_image','ref_video'):
                    self.assertEqual(old['5']['inputs'][field],new['5']['inputs'][field])
                self.assertEqual(old['6']['inputs']['noise_seed'],new['6']['inputs']['noise_seed'])
                self.assertEqual(new['50']['class_type'],'H3AutomaticWindowRouter')
                self.assertEqual(set(new['50']['inputs']),{'model','positive','run_id','audit_dir'})

    def test_changed_source_prompt_seed_geometry_rejected(self):
        case = self.cases[0]
        for node, key, replacement in (('5','prompt','changed'),('6','noise_seed',0),
                                       ('5','length',141),('21','image','wrong.jpg'),('22','file','wrong.mp4')):
            parent = self.parent(case)
            parent[node]['inputs'][key] = replacement
            with self.subTest(field=key), self.assertRaises(ValueError):
                derive(parent,case)

    def test_controlled_parent_not_accepted_as_native_template(self):
        case=self.cases[0];parent=self.parent(case)
        parent['50']['inputs']['mode']='mass_preserve'
        with self.assertRaisesRegex(ValueError,'Native parent'):
            derive(parent,case)

    def test_derivation_does_not_mutate_parent_evidence(self):
        for case in self.cases:
            old=self.parent(case);saved=copy.deepcopy(old)
            derive(old,case)
            self.assertEqual(old,saved)


if __name__=='__main__':
    unittest.main()
