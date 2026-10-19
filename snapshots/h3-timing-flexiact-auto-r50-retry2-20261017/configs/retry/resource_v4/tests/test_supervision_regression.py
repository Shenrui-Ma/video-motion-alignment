"""Reuse existing v3 supervision/release regressions against v4 R50 code."""
import importlib.util,unittest
from pathlib import Path
C=Path(__file__).resolve().parents[1]
old=C.parent/'resource_robustness_candidate_20261017/tests/test_candidate.py'
s=importlib.util.spec_from_file_location('v3tests',old);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m.TMP=C/'test_tmp'
def modules(self):
 t=m.load('r50_transport',C/'r50/overlay/extensions/H3AutomaticWindowRouter/transport.py');t.ROOT=self.root
 release=m.load('r50_release',C/'r50/overlay/scripts/gpu_release_gate.py')
 yield 'r50',t,release
m.CandidateTests.modules=modules
names=['test_resource_wait_over_180s_then_decode_is_allowed','test_execution_has_independent_180s_limit','test_execution_marker_wrong_generation_is_hard_failure','test_execution_marker_stale_time_is_hard_failure','test_own_nvml_tail_waits_while_other_users_continue','test_own_nvml_tail_timeout_preserves_snapshot','test_timeout_is_bounded','test_data_binding_error_is_hard_failure']
suite=unittest.TestSuite(m.CandidateTests(n) for n in names)
if __name__=='__main__':raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
