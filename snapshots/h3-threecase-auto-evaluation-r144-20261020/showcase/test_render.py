"""CPU-only checks; synthetic fixtures remain in temporary directories here."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import render


class ShowcaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=render.ROOT, prefix=".test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = render.draft_manifest(render.PLAN)

    def write(self, name, content):
        path = self.root / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(json.dumps(content))
        return render.bound(path)

    def ledger(self):
        case = self.manifest["cases"][0]
        sid = case["source_id"]
        automatic = self.write("automatic.mp4", b"test fixture only")
        video = {**self.write("comparison.mp4", b"test fixture only"), "role": "automatic"}
        page = {**self.write("page.jpg", b"test fixture only"), "physical_frames": [14, 15]}
        record = self.write("FRAME_LEDGER.json", {
            "source_id": sid, "evaluation_plan": self.manifest["plan"],
            "automatic_binding": {"automatic": automatic, "verified_before_render": True},
            "inputs": [case["inputs"][r] for r in ("source", "native", "fixed")] + [automatic],
            "videos": [video], "pages": [page], "valid_frames": 105,
            "fps": 24, "frames_prepared": True,
        })
        render.bind_review(self.manifest, sid, record["file"])
        return case, page

    def test_missing_results_are_pending_and_draft_is_not_mutated(self):
        original = copy.deepcopy(self.manifest)
        page, result = render.render(self.manifest, embed=False)
        self.assertEqual(original, self.manifest)
        self.assertEqual(result["embedded_assets"], 0)
        self.assertIn("成片待评估", page)
        self.assertEqual(page.count("实际开关记录待评估"), 3)
        self.assertNotIn("20 个步骤均为 OFF", page)
        self.assertNotIn('src="http', page)

    def test_changed_sha_is_rejected(self):
        self.manifest["plan"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            render.prepare(self.manifest)

    def test_unverified_auto_result_is_rejected(self):
        self.manifest["cases"][0]["mf"]["values"]["automatic"] = 0.8
        with self.assertRaisesRegex(ValueError, "verified finished video"):
            render.prepare(self.manifest)

    def test_review_binding_and_changed_columns(self):
        case, _ = self.ledger()
        render.prepare(self.manifest)
        case["media"]["automatic"]["columns"] = ["source", "fixed", "automatic"]
        with self.assertRaisesRegex(ValueError, "comparison columns"):
            render.prepare(self.manifest)

    def test_video_not_in_ledger_is_rejected(self):
        case, _ = self.ledger()
        case["media"]["automatic"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "missing from review ledger"):
            render.prepare(self.manifest)

    def test_screenshot_frames_must_match_ledger(self):
        case, page = self.ledger()
        case["screenshots"] = [{**page, "columns": ["source", "native", "fixed", "automatic"]}]
        render.prepare(self.manifest)
        case["screenshots"][0]["physical_frames"] = [50, 72]
        with self.assertRaisesRegex(ValueError, "Screenshot/frame indices"):
            render.prepare(self.manifest)

    def test_steps_are_exact_booleans_and_unique(self):
        case, _ = self.ledger()
        case["control"] = {"evidence": [self.manifest["plan"]],
                           "decisions": [{"step_0based": 4, "on": False, "windows": []}]}
        render.prepare(self.manifest)
        case["control"]["decisions"][0]["on"] = "false"
        with self.assertRaisesRegex(ValueError, "JSON boolean"):
            render.prepare(self.manifest)
        case["control"]["decisions"][0]["on"] = False
        case["control"]["decisions"] *= 2
        with self.assertRaisesRegex(ValueError, "Duplicate step"):
            render.prepare(self.manifest)

    def test_missing_step_is_pending_and_on_needs_window(self):
        case, _ = self.ledger()
        case["control"] = {"evidence": [self.manifest["plan"]],
                           "decisions": [{"step_0based": 4, "on": True, "windows": []}]}
        with self.assertRaisesRegex(ValueError, "needs active windows"):
            render.prepare(self.manifest)
        case["control"]["decisions"][0]["windows"] = [[4, 19]]
        current, _ = render.prepare(self.manifest)
        result = render.control_html(current[0])
        self.assertEqual(result.count('class="step pending"'), 19)
        self.assertEqual(result.count('class="step on"'), 1)

    def test_event_interval_arithmetic_and_zero_are_preserved(self):
        self.assertEqual(render.delay([42, 45], [57, 60]),
                         {"midpoint": 15.0, "bounds": [12, 18]})
        self.assertEqual(render.delay([0, 0], [0, 0]),
                         {"midpoint": 0.0, "bounds": [0, 0]})
        self.assertIsNone(render.delay([0, 1], None))
        with self.assertRaisesRegex(ValueError, "Invalid frame interval"):
            render.interval([0, 105], 105)

    def test_text_is_escaped(self):
        self.manifest["title"] = '</title><script>alert("x")</script>'
        self.manifest["cases"][0]["conclusion"] = '<img src=x onerror="alert(1)">'
        page, _ = render.render(self.manifest, embed=False)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertNotIn('<img src=x', page)
        self.assertIn("&lt;script&gt;", page)

    def test_asset_bytes_embedded_and_hash_checked(self):
        case, _ = self.ledger()
        page, result = render.render(self.manifest)
        self.assertEqual(result["embedded_assets"], 1)
        self.assertIn("data:video/mp4;base64,", page)
        Path(case["media"]["automatic"]["file"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            render.render(self.manifest)

    def test_prompt_family_and_history_kind_cannot_be_silently_changed(self):
        self.manifest["cases"][1]["prompt_type"] = "P1"
        with self.assertRaisesRegex(ValueError, "Prompt family changed"):
            render.prepare(self.manifest)
        self.manifest = render.draft_manifest(render.PLAN)
        self.manifest["history"] = [{"kind": "r141b"}]
        with self.assertRaisesRegex(ValueError, "historical R138"):
            render.prepare(self.manifest)


if __name__ == "__main__":
    unittest.main()
