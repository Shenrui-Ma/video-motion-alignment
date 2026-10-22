from pathlib import Path
import copy
import json
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'extensions'))
import r112_contract as contract
from H3TemporalRouter import correspondence, NODE_CLASS_MAPPINGS


class ContractTests(unittest.TestCase):
    def test_both_graphs_and_unchanged_source_inputs(self):
        jobs,order=contract.registry()
        self.assertEqual(len(jobs),2)
        for run in order:contract.validate_job(run)

    def test_two_graphs_differ_only_arm_ids_paths_and_spatial_rule(self):
        cases=contract.read(ROOT/'design/CASE_DEFINITIONS.json')
        graphs=[contract.expected_graph(ROOT,c) for c in cases]
        def normalized(value):
            if isinstance(value,dict):return {k:normalized(v) for k,v in value.items()}
            if isinstance(value,list):return [normalized(v) for v in value]
            if isinstance(value,str):
                for arm in contract.ARMS:value=value.replace(arm,'ARM')
            return value
        self.assertEqual(normalized(graphs[0]),normalized(graphs[1]))

    def test_policy_binds_shared_bank_and_unchanged_schedule(self):
        scientific=contract.read(ROOT/'configs/scientific_contract.json')
        self.assertEqual(scientific['correspondence']['matching_policy'],correspondence.POLICY)
        self.assertEqual(scientific['correspondence']['active_steps_half_open'],[6,15])
        first=contract.correspondence_configuration(contract.run_id('fixed_one_bin'))
        second=contract.correspondence_configuration(contract.run_id('matched_one_bin'))
        self.assertNotIn('paired_root',first)
        self.assertEqual(second['paired_root'],first['root'])
        self.assertEqual(second['paired_prefix_manifest'],first['prefix_manifest'])
        self.assertIn('r96_long_0174',first['paired_prefix_manifest'])

    def test_reference_events_are_inherited_unchanged(self):
        self.assertEqual(contract.sha(ROOT/'design/PREREGISTERED_EVENTS.json'),'10e4673a3586fb46875f808af059aa2be63b0a046ebd11986d4c49a7ee109f70')

    def test_runtime_refuses_before_separate_gpu_review(self):
        root=Path(contract.read(ROOT/'configs/runtime.json')['remote_root'])
        with self.assertRaisesRegex(ValueError,'deployment review'):
            contract.validate_router('fixed_one_bin',1.,0,0,0,144,0,50,6,15,contract.run_id('fixed_one_bin'),str(root/'audit/router'))

    def test_modes_registered_without_importing_comfy(self):
        modes=NODE_CLASS_MAPPINGS['H3TemporalRouter'].INPUT_TYPES()['required']['mode'][0]
        for mode in contract.ARMS:self.assertIn(mode,modes)


if __name__=='__main__':unittest.main()
