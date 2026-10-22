import copy
import json
import unittest
from build import B,prepare_one


class GraphTests(unittest.TestCase):
    def test_two_real_graphs_preserve_science_and_inputs(self):
        jobs=json.loads((B/'field_pilots/jobs.json').read_text())['jobs']
        self.assertEqual(len(jobs),2)
        for source in jobs:
            old=json.loads((B/'field_pilots'/source['graph']).read_text());before=copy.deepcopy(old)
            job,raw,check=prepare_one(source,old);new=json.loads(raw)
            self.assertEqual(old,before)
            self.assertEqual(check['changed_nodes'],['14','50'])
            for key in set(old)-{'14','50'}:self.assertEqual(new[key],old[key])
            self.assertEqual(new['50']['class_type'],'H3TemporalGainFieldRole5')
            self.assertEqual(job['max_attempts'],1)
            self.assertEqual(job['metadata']['baseline_field_job'],source['id'])

    def test_unknown_case_refused(self):
        source=json.loads((B/'field_pilots/jobs.json').read_text())['jobs'][0]
        old=json.loads((B/'field_pilots'/source['graph']).read_text())
        source['metadata']['task_id']='unregistered'
        with self.assertRaisesRegex(ValueError,'unregistered'):prepare_one(source,old)


if __name__=='__main__':unittest.main()
