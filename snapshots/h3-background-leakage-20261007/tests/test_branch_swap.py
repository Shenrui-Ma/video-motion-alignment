"""CPU-only contract tests; run with an existing PyTorch environment."""

import copy
import importlib.util
from pathlib import Path
import unittest

import torch


MODULE_PATH = Path(__file__).resolve().parents[1] / "extensions/H3ReferenceBranchSwap/__init__.py"
SPEC = importlib.util.spec_from_file_location("h3_branch_swap", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
swap = MODULE.swap_reference_latent


def image_ref(value):
    return {"kind": "image", "latent_h": 2, "latent_w": 3,
            "latent": torch.full((1, 24, 1, 2, 3), value, dtype=torch.float32)}


def conditioning():
    return [[torch.ones(1, 5, 8), {
        "pooled_output": torch.ones(1, 8),
        "minimax_token_tags": torch.tensor([1, 0, 0, 1, 1], dtype=torch.long),
        "minimax_refs": [image_ref(2), {
            "kind": "video_audio", "latent_h": 2, "latent_w": 3, "latent_t": 4,
            "ref_audio_t": 6, "latent": torch.ones(1, 24, 4, 2, 3),
            "audio_latent": torch.ones(1, 32, 2, 6)}, image_ref(3)],
    }]]


class BranchSwapTests(unittest.TestCase):
    def test_identity_preserves_tensors_and_copies_containers(self):
        base = conditioning()
        out = MODULE.H3ReferenceBranchSwap().swap(base, base, 0)[0]
        self.assertIsNot(out, base)
        self.assertIsNot(out[0], base[0])
        self.assertIs(out[0][0], base[0][0])
        self.assertIsNot(out[0][1], base[0][1])
        self.assertIsNot(out[0][1]["minimax_refs"], base[0][1]["minimax_refs"])
        for actual, original in zip(out[0][1]["minimax_refs"], base[0][1]["minimax_refs"]):
            self.assertIsNot(actual, original)
            self.assertIs(actual["latent"], original["latent"])

    def test_only_selected_latent_changes_inputs_untouched(self):
        base, donor = conditioning(), conditioning()
        donor[0][0].fill_(7)
        donor[0][1]["pooled_output"].fill_(9)
        donor[0][1]["minimax_refs"][0]["latent"].fill_(11)
        original_base, original_donor = copy.deepcopy(base), copy.deepcopy(donor)
        out = swap(base, donor, 0)
        self.assertIs(out[0][0], base[0][0])
        self.assertIs(out[0][1]["pooled_output"], base[0][1]["pooled_output"])
        self.assertIs(out[0][1]["minimax_token_tags"], base[0][1]["minimax_token_tags"])
        self.assertIs(out[0][1]["minimax_refs"][0]["latent"], donor[0][1]["minimax_refs"][0]["latent"])
        self.assertIs(out[0][1]["minimax_refs"][1]["latent"], base[0][1]["minimax_refs"][1]["latent"])
        self.assertIs(out[0][1]["minimax_refs"][1]["audio_latent"], base[0][1]["minimax_refs"][1]["audio_latent"])
        self.assert_nested_equal(base, original_base)
        self.assert_nested_equal(donor, original_donor)

    def assert_nested_equal(self, actual, expected):
        if isinstance(expected, torch.Tensor):
            self.assertTrue(torch.equal(actual, expected))
        elif isinstance(expected, dict):
            self.assertEqual(actual.keys(), expected.keys())
            for key in expected:
                self.assert_nested_equal(actual[key], expected[key])
        elif isinstance(expected, list):
            self.assertEqual(len(actual), len(expected))
            for a, e in zip(actual, expected):
                self.assert_nested_equal(a, e)
        else:
            self.assertEqual(actual, expected)

    def test_image_index_counts_images_not_all_references(self):
        base, donor = conditioning(), conditioning()
        donor[0][1]["minimax_refs"][2]["latent"].fill_(17)
        out = swap(base, donor, 1)
        self.assertIs(out[0][1]["minimax_refs"][2]["latent"], donor[0][1]["minimax_refs"][2]["latent"])
        self.assertIs(out[0][1]["minimax_refs"][0]["latent"], base[0][1]["minimax_refs"][0]["latent"])

    def test_mismatches_rejected_without_mutating_base(self):
        def changed_embedding(d):
            d[0][0] = torch.ones(1, 6, 8)

        def changed_tags(d):
            d[0][1]["minimax_token_tags"][0] = 0

        def changed_kind(d):
            refs = d[0][1]["minimax_refs"]
            refs[0], refs[1] = refs[1], refs[0]

        def changed_latent_shape(d):
            d[0][1]["minimax_refs"][0]["latent"] = torch.ones(1, 24, 1, 4, 3)
            d[0][1]["minimax_refs"][0]["latent_h"] = 4

        def changed_geometry(d):
            d[0][1]["minimax_refs"][0]["latent_h"] = 3

        def changed_video(d):
            d[0][1]["minimax_refs"][1]["latent"].fill_(2)

        def changed_audio(d):
            d[0][1]["minimax_refs"][1]["audio_latent"].fill_(2)

        def changed_unselected_image(d):
            d[0][1]["minimax_refs"][2]["latent"].fill_(2)

        def changed_dtype(d):
            ref = d[0][1]["minimax_refs"][0]
            ref["latent"] = ref["latent"].half()

        def extra_ref_metadata(d):
            d[0][1]["minimax_refs"][0]["unknown"] = True

        for mutation in (changed_embedding, changed_tags, changed_kind, changed_latent_shape,
                         changed_geometry, changed_video, changed_audio,
                         changed_unselected_image, changed_dtype, extra_ref_metadata):
            with self.subTest(mutation=mutation.__name__):
                base, donor = conditioning(), conditioning()
                before = copy.deepcopy(base)
                mutation(donor)
                with self.assertRaises(ValueError):
                    swap(base, donor, 0)
                self.assert_nested_equal(base, before)

    def test_unsupported_metadata_rejected_even_if_matching(self):
        base = conditioning()
        base[0][1]["minimax_keyframes"] = []
        with self.assertRaisesRegex(ValueError, "unsupported"):
            swap(base, copy.deepcopy(base), 0)

    def test_invalid_index_and_missing_metadata_rejected(self):
        for index in (-1, 2, True, 0.0):
            with self.subTest(index=index), self.assertRaises(ValueError):
                swap(conditioning(), conditioning(), index)
        base = conditioning()
        del base[0][1]["minimax_token_tags"]
        with self.assertRaises(ValueError):
            swap(base, copy.deepcopy(base), 0)

    def test_silent_video_and_standalone_audio_supported(self):
        base = conditioning()
        video = base[0][1]["minimax_refs"][1]
        video.update(kind="video", ref_audio_t=0, audio_latent=None)
        base[0][1]["minimax_refs"].append({"kind": "audio", "ref_audio_t": 7,
                                        "audio_latent": torch.ones(1, 32, 2, 7)})
        self.assert_nested_equal(swap(base, copy.deepcopy(base), 0), base)


if __name__ == "__main__":
    unittest.main()
