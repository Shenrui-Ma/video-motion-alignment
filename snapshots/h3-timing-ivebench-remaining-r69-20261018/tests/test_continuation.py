"""Prove four preselected tasks keep R63 numerical graphs and final denominator."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from r69_contract import registry,read,sha
import execution_gate


def normalized(graph):
    g=copy.deepcopy(graph)
    for node,key in [('5','audit_dir'),('6','audit_dir'),('50','audit_dir'),('51','source_audit_dir'),('52','output_dir')]:
        g[node]['inputs'][key]='AUDIT_ROOT'
    for node in ('5','6','50','51','52'):
        g[node]['inputs']['run_id']=g[node]['inputs']['run_id'].replace('r63_','RUN_').replace('r69_','RUN_')
    for node,key in [('51','source_run_id'),('6','pair_id'),('14','filename_prefix')]:
        g[node]['inputs'][key]=g[node]['inputs'][key].replace('r63_','RUN_').replace('r69_','RUN_')
    return g


class ContinuationTests(unittest.TestCase):
    def test_numerical_graphs_identical_to_all_eight_r63_graphs(self):
        _,order=registry(ROOT)
        for run in order:
            before=read(ROOT/'configs/R63_reference_graphs'/(run.replace('r69_','r63_')+'.json'))
            after=read(ROOT/'configs/graphs'/(run+'.json'))
            self.assertEqual(normalized(before),normalized(after),run)

    def test_original_five_denominator_and_prior_0210_preserved(self):
        scope=read(ROOT/'configs/fixed_five_scope.json')
        _,order=registry(ROOT)
        self.assertEqual(scope['original_selected_source_count'],5)
        self.assertEqual(scope['original_source_ids'],['short_0210','short_0230','short_0263','short_0352','short_0370'])
        self.assertTrue(scope['retained_prior_source']['include_in_final_five_source_outcomes'])
        self.assertEqual(len(order),8)
        self.assertFalse(any('short_0210' in name for name in order))

    def test_runtime_and_bounded_hold(self):
        r=read(ROOT/'configs/runtime.json');s=read(ROOT/'configs/scientific_contract.json')
        self.assertEqual((r['expected_gpu_index'],r['port']),(7,8538))
        self.assertEqual(r['gpu_uuid'],'GPU-REDACTED')
        self.assertEqual(s['continuous']['idle_hold_seconds'],1800)
        self.assertFalse(s['online_observer'])
        self.assertTrue(s['continuous']['failure_releases_exact_owned'])

    def test_frozen_kernels_equal_parent(self):
        for name,row in read(ROOT/'configs/runtime_kernel_hashes.json').items():
            self.assertTrue(row['byte_equal'])
            self.assertEqual(sha(ROOT/name),row['parent_sha256'])

    def test_registry_rejects_shifted_window_or_source_substitution(self):
        with tempfile.TemporaryDirectory() as d:
            # Use a lightweight complete config tree; inputs are not read by registry.
            import shutil
            root=Path(d);shutil.copytree(ROOT/'configs',root/'configs')
            first=read(root/'configs/queue.json')['jobs'][0]
            graph=root/'configs/graphs'/(first+'.json')
            value=read(graph);value['50']['inputs']['time_offset']=1
            graph.write_text(json.dumps(value))
            with self.assertRaises(ValueError):registry(root)
            shutil.copy2(ROOT/'configs/graphs'/(first+'.json'),graph)
            s=read(root/'configs/scientific_contract.json');s['cases'][0]['source_id']='short_0210'
            (root/'configs/scientific_contract.json').write_text(json.dumps(s))
            with self.assertRaises(ValueError):registry(root)


if __name__=='__main__':unittest.main(verbosity=2)
