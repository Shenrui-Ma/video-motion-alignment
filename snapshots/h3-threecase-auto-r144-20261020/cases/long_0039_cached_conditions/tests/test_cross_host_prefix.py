from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extensions"))
from H3AutomaticWindowRouter.pair_gate import HistoricalPairGate


class CrossHostPrefix(unittest.TestCase):
    def check_branch(self, actual, *, mode="cross_host_signature_audit"):
        gate = HistoricalPairGate()
        gate.case = {"historical_prefix_comparison": mode}
        gate.records = {0: {"sigma_video": 1.0, "sigma_next_video": .99,
                            "video": {"sha256": "original-video"}, "audio": {"sha256": "original-audio"}}}
        state = SimpleNamespace(audit={"counterfactual": {"pair_gates": []}})
        row = {"physical_index": 0, "branch": "native", "sigma": 1.0, "sigma_next": .99,
               "normalized_stream_signatures": actual}
        gate.branch(state, None, None, row)
        return gate, state.audit["counterfactual"]["pair_gates"][0]

    def test_actual_difference_is_reported_without_changing_decision(self):
        gate, row = self.check_branch([{"sha256": "different"}, {"sha256": "original-audio"}])
        self.assertEqual(row["status"], "cross_host_signature_comparison")
        self.assertFalse(row["normalized_signature_equal"])
        self.assertIsNone(gate.first_on)
        self.assertEqual(gate.done, {0})

    def test_exact_signature_match_is_retained(self):
        _, row = self.check_branch([{"sha256": "original-video"}, {"sha256": "original-audio"}])
        self.assertTrue(row["normalized_signature_equal"])

    def test_audit_mode_requires_explicit_case_binding(self):
        with self.assertRaises(ValueError):
            self.check_branch([], mode="undeclared")


if __name__ == "__main__":
    unittest.main()
