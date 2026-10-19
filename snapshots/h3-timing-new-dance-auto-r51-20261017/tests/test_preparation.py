import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from preparation import check,graph_preview,selection_from_verdicts


class PreparationTests(unittest.TestCase):
    def test_exact_source_archive_and_unbound_state(self):
        result=check()
        self.assertEqual(result['exact_numerical_files'],17)
        self.assertFalse(result['actual_parent_closed'])
        self.assertFalse(result['resource_admitted'])

    def test_priority_and_pending_do_not_skip_first_candidate(self):
        f=selection_from_verdicts
        self.assertIsNone(f({'10264579':None,'6980766':True})['selected_source_id'])
        self.assertEqual(f({'10264579':True,'6980766':True})['selected_source_id'],'10264579')
        self.assertEqual(f({'10264579':False,'6980766':True})['selected_source_id'],'6980766')
        self.assertIsNone(f({'10264579':False,'6980766':None})['selected_source_id'])
        self.assertEqual(f({'10264579':False,'6980766':False})['status'],'NO_QUALIFYING_CASE_TEMPLATE_ONLY')

    def test_verdict_bool_is_not_integer_or_truthy_string(self):
        for value in (1,0,'true',{},[]):
            with self.assertRaises(ValueError):
                selection_from_verdicts({'10264579':value,'6980766':False})
        with self.assertRaises(ValueError):
            selection_from_verdicts({'6980766':True})

    def test_both_graph_previews_preserve_numerical_inputs(self):
        cases=json.loads((ROOT/'configs/CANDIDATES.json').read_text())['candidates']
        for case in cases:
            parent=json.loads((ROOT/'audit/reference/r47/graphs'/(case['run_id']+'.json')).read_text())
            old=copy.deepcopy(parent);new=graph_preview(parent,case)
            self.assertEqual(parent,old)
            for key in ('1','2','3','4','7','8','9','10','11','12','13','21','22','23','41'):
                self.assertEqual(parent[key],new[key])
            for key in ('prompt','width','height','length','semantic_fps','phase_frames'):
                self.assertEqual(parent['5']['inputs'][key],new['5']['inputs'][key])
            self.assertEqual(new['50']['class_type'],'H3AutomaticWindowRouter')
            self.assertNotIn('start_frame',new['50']['inputs'])
            self.assertNotIn('end_frame',new['50']['inputs'])
            self.assertEqual(new['6']['inputs']['noise_seed'],case['seed'])

    def test_bad_graph_prompt_seed_source_geometry_rejected(self):
        case=json.loads((ROOT/'configs/CANDIDATES.json').read_text())['candidates'][0]
        old=json.loads((ROOT/'audit/reference/r47/graphs'/(case['run_id']+'.json')).read_text())
        for node,key,value in [('5','prompt','wrong'),('6','noise_seed',0),('22','file','wrong.mp4'),('5','length',158)]:
            parent=copy.deepcopy(old);parent[node]['inputs'][key]=value
            with self.assertRaises(ValueError):
                graph_preview(parent,case)


if __name__=='__main__':unittest.main()
