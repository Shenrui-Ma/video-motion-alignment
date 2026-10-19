"""Exercise the auxiliary graph nodes' output path guard before GPU launch."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "r13_audit_root_test", ROOT / "extensions/H3EventAudit/__init__.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class GraphAuditRootTest(unittest.TestCase):
    def test_formal_graph_noise_node_and_reference_root(self):
        graph = json.loads((ROOT / "configs/r13_s05_one_step_fork.json").read_text())
        with patch.object(Path, "mkdir"):
            for node in ("5", "6"):
                value = graph[node]["inputs"]["audit_dir"]
                self.assertEqual(audit.audit_root(value), Path(value).resolve())
            node = audit.NODE_CLASS_MAPPINGS[graph["6"]["class_type"]]()
            self.assertEqual(len(node.get_noise(**graph["6"]["inputs"])), 1)

    def test_parent_or_relative_output_is_rejected(self):
        with patch.object(Path, "mkdir") as mkdir:
            for value in ("audit", "/data5/researcher/h3_runs/timing_counterfactual_r10_20261016/audit"):
                with self.assertRaises(ValueError):
                    audit.audit_root(value)
            mkdir.assert_not_called()


if __name__ == "__main__":
    unittest.main()
