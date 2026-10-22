import unittest
from copy import deepcopy
from import_mf import validate_score
from prepare_comparison import ROOT, read


class MFImportTests(unittest.TestCase):
    def setUp(self):
        self.case = read(ROOT / "EVALUATION_MANIFEST.json")["cases"][0]
        self.value = dict(case="short_0252", role="fixed_phase", actual_generated_video_sha256="new",
                          source_full_sha256=self.case["media"]["source"]["sha256"],
                          valid_frames=98, evaluation_frames=98, evaluation_fps=24,
                          official_numerics_unchanged=True, cuda_initialized=False,
                          motion_fidelity=.75)
        self.inputs = dict(crop_xywh=[16, 8, 1280, 720])

    def check(self):
        return validate_score(self.case, "fixed_phase", "new", self.value, self.inputs)

    def test_exact_domain(self):
        self.assertEqual(self.check(), .75)

    def test_wrong_video(self):
        self.value["actual_generated_video_sha256"] = "old"
        with self.assertRaisesRegex(ValueError, "video"):
            self.check()

    def test_wrong_crop_or_padding(self):
        for key, val in (("valid_frames", 107), ("evaluation_fps", 25)):
            old = deepcopy(self.value)
            self.value[key] = val
            with self.assertRaisesRegex(ValueError, "domain"):
                self.check()
            self.value = old
        self.inputs["crop_xywh"] = [0, 0, 1312, 736]
        with self.assertRaisesRegex(ValueError, "domain"):
            self.check()

    def test_nonfinite(self):
        self.value["motion_fidelity"] = float("nan")
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            self.check()


if __name__ == "__main__":
    unittest.main()
