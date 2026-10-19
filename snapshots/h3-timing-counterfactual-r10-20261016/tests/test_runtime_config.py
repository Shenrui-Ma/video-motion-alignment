import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'extensions'))
import preflight
import service
from H3EventAudit import audit_root

class RuntimeTests(unittest.TestCase):
    def test_frozen_graph_warmup_and_resources(self):
        report=preflight.check(ROOT)
        self.assertTrue(report['validated'])
        self.assertEqual(report['timings'],[86.53,80.25,81.19])
        self.assertEqual(service.PORT,8471)
        self.assertEqual(service.GPU,'GPU-REDACTED')
        self.assertEqual(str(service.RUN),'/data5/researcher/h3_runs/timing_counterfactual_r10_20261016')
        self.assertIn('H3CounterfactualRouter',service.command())
        self.assertIn('finally:service.stop()', (ROOT/'scripts/run_queue.py').read_text())

    def test_path_guard_admission(self):
        remote=str(service.RUN)
        with patch.object(Path,'mkdir'):
            self.assertEqual(str(audit_root(remote+'/audit')),remote+'/audit')
        for value in (remote+'/../wrong',remote+'_other/audit','/tmp/audit'):
            with patch.object(Path,'mkdir'),self.assertRaises(ValueError):audit_root(value)
        admission=json.loads((ROOT/'configs/admission.json').read_text())
        queue={'queue_running':[],'queue_pending':[]}
        with patch.object(service,'proc_uid',return_value=service.os.getuid()+1):
            service.check_admission(admission,[{'gpu_uuid':'other','pid':123}],queue)
        with self.assertRaisesRegex(RuntimeError,'Selected GPU'):
            service.check_admission(admission,[{'gpu_uuid':service.GPU,'pid':123}],queue)

    def test_old_capture_scope_is_explicit(self):
        parent=json.loads((ROOT/'audit/parent_x0_manifest.json').read_text())
        self.assertEqual(parent['capture_steps_zero_based'],[5,6,7,8,9,10,15,19])
        self.assertEqual(parent['status'],'complete')
        self.assertEqual(parent['callback_count'],20)
        hashes=json.loads((ROOT/'configs/parent_core_hashes.json').read_text())
        for name in ('comfy/k_diffusion/sampling.py','comfy/patcher_extension.py','comfy_extras/nodes_custom_sampler.py','comfy/conds.py'):
            self.assertIn(name,hashes)

if __name__=='__main__':unittest.main()
