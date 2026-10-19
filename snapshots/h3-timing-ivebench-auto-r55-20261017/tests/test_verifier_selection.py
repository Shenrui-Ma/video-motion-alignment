"""Single-case validation keeps global evidence and cannot publish a full batch gate."""
import contextlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
import verify_completed as v
contract=importlib.import_module('r50_contract' if 'r50-' in ROOT.name else 'r55_contract')
CASES=json.loads((ROOT/'configs/protocol.json').read_text())['cases']


class VerifierSelection(unittest.TestCase):
    def test_default_covers_all_five_and_single_selector_is_explicit(self):
        self.assertEqual(v.select_cases(CASES),CASES)
        results=[{'run':case['run_id']} for case in CASES]
        self.assertEqual(v.result_scope(CASES,results,None),{
            'partial_batch':False,'planned_denominator':5,'verified_runs':[c['run_id'] for c in CASES]})
        chosen=CASES[2]['run_id']
        self.assertEqual(v.select_cases(CASES,chosen),[CASES[2]])
        self.assertEqual(v.result_scope(CASES,[{'run':chosen}],chosen),{
            'partial_batch':True,'planned_denominator':5,'verified_runs':[chosen]})
        with self.assertRaisesRegex(ValueError,'unknown selected run'):
            v.select_cases(CASES,'outside-fixed-five')
        with self.assertRaisesRegex(ValueError,'fixed five-case'):
            v.select_cases(CASES[:1],chosen)

    def setup_root(self,folder):
        root=Path(folder)
        for name in ('configs','processes','logs','audit/counterfactual'):(root/name).mkdir(parents=True)
        (root/'configs/protocol.json').write_text(json.dumps({'cases':CASES}))
        (root/'deploy_manifest.json').write_text(json.dumps({'files':{}}))
        (root/'processes/service.json').write_text('{}')
        return root

    def global_stubs(self):
        stack=contextlib.ExitStack()
        stack.enter_context(patch.object(v.t,'bindings',return_value={}))
        stack.enter_context(patch.object(v.t,'admission_document',return_value={}))
        stack.enter_context(patch.object(contract,'validate_job',return_value={}))
        return stack

    def test_missing_selected_job_stays_incomplete_and_does_not_read_other_jobs(self):
        chosen=CASES[2]['run_id']
        with tempfile.TemporaryDirectory() as folder,self.global_stubs():
            root=self.setup_root(folder)
            with self.assertRaises(FileNotFoundError) as failure:
                v.check(root,allow_resident=True,run=chosen)
            self.assertIn(chosen+'_job.json',str(failure.exception))
            (root/'logs'/f'{chosen}_job.json').write_text('{}')
            (root/'audit/counterfactual'/f'{chosen}.json').write_text(json.dumps({
                'status':'running','counterfactual':{'full_physical_indices':[]}}))
            with self.assertRaisesRegex(ValueError,'invalid complete mask'):
                v.check(root,allow_resident=True,run=chosen)

    def test_unknown_selector_checks_global_bindings_and_rejects_before_jobs(self):
        with tempfile.TemporaryDirectory() as folder,self.global_stubs():
            root=self.setup_root(folder)
            with patch.object(v.t,'bindings',side_effect=ValueError('global parent changed')):
                with self.assertRaisesRegex(ValueError,'global parent changed'):
                    v.check(root,allow_resident=True,run='outside-fixed-five')
            with self.assertRaisesRegex(ValueError,'unknown selected run'):
                v.check(root,allow_resident=True,run='outside-fixed-five')
            (root/'sealed.txt').write_text('changed')
            (root/'deploy_manifest.json').write_text(json.dumps({'files':{'sealed.txt':{'sha256':'0'*64}}}))
            with self.assertRaisesRegex(ValueError,'immutable file changed'):
                v.check(root,allow_resident=True,run=CASES[0]['run_id'])

    def test_partial_output_cannot_publish_or_overwrite_batch_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);batch=root/'RUNTIME_GATE.json'
            partial={'status':'pass','partial_batch':True,'planned_denominator':5,'verified_runs':[CASES[0]['run_id']]}
            with self.assertRaisesRegex(ValueError,'separate case gate'):
                v.write_result(batch,partial)
            self.assertFalse(batch.exists())
            path=root/'CASE_RUNTIME_GATE.json';v.write_result(path,partial)
            self.assertEqual(json.loads(path.read_text()),partial)
            with self.assertRaises(FileExistsError):v.write_result(path,partial)
            full=dict(partial,partial_batch=False,verified_runs=[c['run_id'] for c in CASES])
            v.write_result(batch,full)
            with self.assertRaisesRegex(ValueError,'separate case gate'):v.write_result(batch,partial)
            self.assertEqual(json.loads(batch.read_text()),full)


if __name__=='__main__':unittest.main()
