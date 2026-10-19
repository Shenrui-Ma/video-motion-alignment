import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import evaluate

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

class IntakeTest(unittest.TestCase):
    def test_original_clip_semantics_on_actual_raw_range(self):
        # Values from metadata-only RAW_SCORE_RANGE_DIAGNOSTIC, not lag output.
        self.assertEqual(evaluate.metric_weight([1.2188950777053833,1.2453231811523438,1.20608651638031]),1.)
        self.assertEqual(evaluate.metric_weight([.9,1.2453231811523438,.7]),.7)
        self.assertEqual(evaluate.metric_weight([-.1,.9,.8]),0.)

    def test_legal_unit_interval_weights_unchanged(self):
        import itertools
        for values in itertools.product((0.,.3,.5,.8,1.),repeat=3):
            self.assertEqual(evaluate.metric_weight(values),min(values))
        for value in (float('nan'),float('inf'),-float('inf')):
            with self.assertRaises(ValueError):evaluate.metric_weight([.9,value,.9])

    def fixture(self,root):
        (root/'PROTOCOL.json').write_text('{}')
        (root/'FREEZE.json').write_text('{"files":{}}')
        (root/'pose.json').write_text('{"deliberately_not_parsed":true}')
        (root/'RUN_GATE.json').write_text('{"passed":true,"run_id":"run"}')
        (root/'ARCHIVE.json').write_text(json.dumps({'complete':True,'source_sha':digest(root/'pose.json'),'target_sha':digest(root/'pose.json')}))
        def item(name):return {'path':str(root/name),'sha256':digest(root/name)}
        case={'case_id':'test','run_id':'run','family':'R26','endpoint':'final',
              'source_pose':item('pose.json'),'target_pose':item('pose.json'),
              'gates':[item('RUN_GATE.json')|{'kind':'RUN_GATE'}],
              'archive_evidence':[item('ARCHIVE.json')|{'predicates':[{'pointer':['complete'],'equals':True}]}],
              'pose_evidence':{k:{'path':str(root/'ARCHIVE.json'),'pointer':[field]} for k,field in [('source_pose','source_sha'),('target_pose','target_sha')]}}
        return {'authorized_for_actual_evaluation':True,'protocol_sha256':digest(root/'PROTOCOL.json'),
                'freeze_sha256':digest(root/'FREEZE.json'),'cases':[case],'expected_runs':{'run':['final']}}

    def test_bound_final_intake_reads_no_pose_content(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);b=self.fixture(root)
            with patch.object(evaluate,'HERE',root):self.assertTrue(evaluate.validate_binding(b))

    def test_refuses_unapproved(self):
        with self.assertRaises(ValueError):evaluate.validate_binding({'authorized_for_actual_evaluation':False})

    def test_rejects_missing_terminal_archive_or_changed_input(self):
        for mutation in ('gate','archive','changed','run'):
            with tempfile.TemporaryDirectory() as td:
                root=Path(td);b=self.fixture(root)
                if mutation=='gate':b['cases'][0]['gates']=[]
                if mutation=='archive':b['cases'][0]['archive_evidence']=[]
                if mutation=='changed':(root/'pose.json').write_text('changed')
                if mutation=='run':b['cases'][0]['run_id']='wrong'
                with patch.object(evaluate,'HERE',root),self.assertRaises(ValueError):evaluate.validate_binding(b)

    def test_r27_requires_all20_before_read(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);b=self.fixture(root);c=b['cases'][0]
            b['cases']=[dict(c,case_id=f'index{i}',family='R27',endpoint=i) for i in range(20)]
            b['expected_runs']={'run':list(range(20))}
            with patch.object(evaluate,'HERE',root):self.assertTrue(evaluate.validate_binding(b))
            b['cases'].pop();b['expected_runs']={'run':list(range(19))}
            with patch.object(evaluate,'HERE',root),self.assertRaises(ValueError):evaluate.validate_binding(b)

    def test_domain_edge_is_not_missing_pose(self):
        self.assertIsNone(evaluate.rows_for_null({}, {},[0,15],4,-2,'arm_direction',None))
        self.assertIsNone(evaluate.rows_for_null({}, {},[125,140],4,0,'arm_direction',None))

    def test_all186_part_windows(self):
        ws=list(evaluate.windows());self.assertEqual(len(ws)*3,186)
        self.assertIn([125,140],ws);self.assertIn([109,140],ws)

    def test_pose_evidence_cannot_be_replaced_by_unlinked_file(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);b=self.fixture(root)
            (root/'other.json').write_text('{}')
            b['cases'][0]['target_pose']={'path':str(root/'other.json'),'sha256':digest(root/'other.json')}
            with patch.object(evaluate,'HERE',root),self.assertRaises(ValueError):evaluate.validate_binding(b)

if __name__=='__main__':unittest.main()
