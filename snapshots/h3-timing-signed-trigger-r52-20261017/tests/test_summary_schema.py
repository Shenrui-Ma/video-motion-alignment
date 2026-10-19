import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from replay import check_summary

class SummarySchemaTests(unittest.TestCase):
    def test_four_actual_schemas_use_bound_run_seed_pose(self):
        for case in json.loads((ROOT/'design/PROTOCOL.json').read_text())['cases']:
            summary=json.loads(Path(case['summary']['path']).read_text())
            check_summary(summary,case)
            bad=dict(summary,source_pose_sha256='0'*64)
            with self.assertRaises(ValueError):check_summary(bad,case)
            bad=dict(summary,source_id='wrong-source')
            with self.assertRaises(ValueError):check_summary(bad,case)

if __name__=='__main__':unittest.main()
