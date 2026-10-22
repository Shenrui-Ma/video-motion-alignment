import copy
import json
import unittest
from build import B,prepare_one


class GraphTests(unittest.TestCase):
    def test_all_four_frozen_graphs_change_only_output_and_method_node(self):
        seen=[]
        for directory in ('field_pilots','field_extension_two'):
            jobs=json.loads((B/directory/'jobs.json').read_text())['jobs']
            for source in jobs:
                old=json.loads((B/directory/source['graph']).read_text());before=copy.deepcopy(old)
                job,raw,check=prepare_one(source,old);new=json.loads(raw)
                seen.append(source['metadata']['task_id'])
                self.assertEqual(old,before);self.assertEqual(check['changed_nodes'],['14','50'])
                for key in set(old)-{'14','50'}:self.assertEqual(new[key],old[key])
                self.assertEqual(new['50']['class_type'],'H3TemporalGainFieldFixedBudget')
                self.assertEqual(job['max_attempts'],1)
                self.assertEqual(job['metadata']['innovation_status'],'review_only_not_deployed')
                self.assertEqual(new['50']['inputs']['smoothness'],.625)
        self.assertEqual(set(seen),{'short_0252','short_0358','long_0039','long_0059'})

    def test_unknown_case_rejected(self):
        source=json.loads((B/'field_pilots/jobs.json').read_text())['jobs'][0]
        old=json.loads((B/'field_pilots'/source['graph']).read_text());source['metadata']['task_id']='unknown'
        with self.assertRaisesRegex(ValueError,'unregistered'):prepare_one(source,old)


if __name__=='__main__':unittest.main()
