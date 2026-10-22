import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).with_name("native_review_gate.py")
spec = importlib.util.spec_from_file_location("native_review_gate", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeReviewTests(unittest.TestCase):
    def setUp(self):
        self.request = dict(source_id="sam07", run_id="native", native_gate_sha256="g",
                            video_sha256="v", producer_seal_sha256="s")
        self.review = dict(self.request, schema="r150-native-visual-review-v1",
                           reviewer="continue_metrics", passed=True, task_completed=True)

    def test_exact_positive_review(self):
        module.validate_review(self.review, self.request)

    def test_rejects_other_or_stale_native(self):
        for field in self.request:
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.validate_review(dict(self.review, **{field: "other"}), self.request)

    def test_rejects_failed_editing(self):
        for field in ("passed", "task_completed"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.validate_review(dict(self.review, **{field: False}), self.request)

    def test_requires_identified_reviewer_and_schema(self):
        for field in ("schema", "reviewer"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.validate_review(dict(self.review, **{field: ""}), self.request)


if __name__ == "__main__":
    unittest.main()
