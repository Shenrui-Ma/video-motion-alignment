import unittest
import incremental_case as inc
import remote_consume as remote
class RemainingCases(unittest.TestCase):
 def test_four_legal_remaining_cases(self):
  for c in inc.P['cases'][1:]:self.assertEqual(inc.case_for(c['run_id']),c)
 def test_external_chest_cannot_be_generated_or_consumed_here(self):
  with self.assertRaisesRegex(ValueError,'external'):inc.case_for(inc.P['cases'][0]['run_id'])
 def test_batch_entry_requires_separate_aggregate(self):
  with self.assertRaisesRegex(ValueError,'batch snapshot disabled'):remote.snapshot()
if __name__=='__main__':unittest.main()
