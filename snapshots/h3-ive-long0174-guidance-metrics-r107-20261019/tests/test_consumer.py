"""Synthetic gate fixtures only; no generated experiment result is fabricated."""
import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('r107_consumer',ROOT/'scripts/consume.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


class ConsumerEvidence(unittest.TestCase):
    def gate(self):
        p=c.CONFIG['cases']['long_0174']
        return {'schema':'r107-historical-native-paired-runtime-gate-v1','passed':True,
                'source_id':'long_0174','checks':dict.fromkeys(c.REQUIRED_CHECKS,True),
                'runtime_profile_sha256':c.CONFIG['producer_runtime_sha256'],
                'runs':{'native':{'run_id':p['run_id'],'video':{'sha256':p['native_video']['sha256']},
                                  'NFE':20,'routed_blocks':0,'valid_frames':145},
                        'forced':{'run_id':'r107_long_0174_seed2026101701_forced',
                                  'video':{'file':str(c.REMOTE/'output/SYNTHETIC_TEST_ONLY.mp4')},
                                  'NFE':20,'routed_blocks':450,'valid_frames':145}},
                'prefix_tensor_comparison':[{'step_zero_based':i,'video':True,'audio':True,
                    'parent_file_sha256':row['sha256']} for i,row in enumerate(p['first_six_predictions'])]}

    def test_valid_synthetic_gate(self):
        self.assertIsNotNone(c.verify_gate('long_0174',self.gate()))

    def reject(self,mutate):
        g=self.gate();mutate(g)
        with self.assertRaises((ValueError,KeyError)):c.verify_gate('long_0174',g)

    def test_all_checks_required(self):
        for key in c.REQUIRED_CHECKS:self.reject(lambda g:g['checks'].pop(key))

    def test_failed_check_rejected(self):self.reject(lambda g:g['checks'].update(extra=False))
    def test_other_run_gate_rejected(self):self.reject(lambda g:g.update(schema='r101-historical-native-paired-runtime-gate-v1'))
    def test_failed_gate_rejected(self):self.reject(lambda g:g.update(passed=False))
    def test_other_source_rejected(self):self.reject(lambda g:g.update(source_id='long_0173'))
    def test_wrong_native_rejected(self):self.reject(lambda g:g['runs']['native']['video'].update(sha256='0'*64))
    def test_other_runtime_rejected(self):self.reject(lambda g:g.update(runtime_profile_sha256='0'*64))
    def test_route_count_rejected(self):self.reject(lambda g:g['runs']['forced'].update(routed_blocks=449))
    def test_nfe_rejected(self):self.reject(lambda g:g['runs']['forced'].update(NFE=8))
    def test_flex_support_rejected(self):self.reject(lambda g:g['runs']['forced'].update(valid_frames=147))
    def test_missing_prefix_rejected(self):self.reject(lambda g:g['prefix_tensor_comparison'].pop())
    def test_false_audio_prefix_rejected(self):self.reject(lambda g:g['prefix_tensor_comparison'][2].update(audio=False))
    def test_wrong_parent_snapshot_rejected(self):self.reject(lambda g:g['prefix_tensor_comparison'][2].update(parent_file_sha256='0'*64))
    def test_output_traversal_rejected(self):self.reject(lambda g:g['runs']['forced']['video'].update(file=str(c.REMOTE/'output/../outside.mp4')))
    def test_static_source_and_native_bytes(self):
        for name in ('reference_video','native_video'):
            p=c.CONFIG['cases']['long_0174'][name];self.assertEqual(c.sha(p['file']),p['sha256'])
    def test_producer_seal_binding(self):
        p=Path(c.CONFIG['producer_local'])/'deploy_manifest.json'
        self.assertEqual(c.sha(p),c.CONFIG['producer_seal_sha256'])
        self.assertEqual(c.read(p),c.read(ROOT/'configs/producer_deploy_manifest.json'))


if __name__=='__main__':unittest.main()
