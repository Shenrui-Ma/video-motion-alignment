import unittest
import copy
import numpy as np
from evaluate_probabilities import normalized_content, retrieval_probabilities, summarize, validate_replay_gate


class RetrievalTest(unittest.TestCase):
    def setUp(self):
        self.q = np.zeros((4, 2, 3, 4), dtype=np.float64)
        for t in range(4):
            self.q[t, :, :, t] = 8
        self.valid = np.array([True, True, True, False])
        self.spans = np.array([[0, 0], [1, 4], [5, 8], [9, 12]])
        self.case = {"case_id": "test", "frozen_events": [
            {"id": "event", "source": [1, 4], "native": [5, 8], "global_weak": [1, 4],
             "midpoint_offsets_frames": {"native": 4, "global_weak": 0},
             "offset_uncertainty_frames": {"native": [1, 7], "global_weak": [-3, 3]}}]}

    def test_sparse_lse_matches_full_spatial_softmax(self):
        rng = np.random.default_rng(51)
        q = rng.normal(size=(4, 2, 3, 4))
        k = rng.normal(size=q.shape)
        result = retrieval_probabilities(q, k, self.valid)
        score = q[1, 0, 2] @ k[:3, :, 2].reshape(6, 4).T / 2
        oracle = np.exp(score - score.max())
        oracle = (oracle / oracle.sum()).reshape(3, 2).sum(axis=1)
        np.testing.assert_allclose(result[2, 1, 0, :3], oracle, atol=1e-14)
        self.assertEqual(result[..., 3].sum(), 0)
        self.assertEqual(result[:, 3].sum(), 0)

    def test_known_delayed_content_and_all_heads_retained(self):
        delayed = self.q.copy()
        delayed[2] = self.q[1]
        p = retrieval_probabilities(delayed, self.q, self.valid)
        rp = retrieval_probabilities(self.q, self.q, self.valid)
        r = summarize(p, rp, self.spans, self.valid, self.case, "native")
        e = r["events"][0]
        self.assertEqual(r["all_head_count"], 3)
        self.assertEqual(e["signed_phase_frames"]["count"], 6)
        self.assertAlmostEqual(e["signed_phase_frames"]["mean"], 4, places=10)
        self.assertAlmostEqual(e["reference_event_mass"]["mean"], 1, places=10)

    def test_flat_and_bimodal_distributions_keep_ambiguity(self):
        p = retrieval_probabilities(np.zeros_like(self.q), self.q, self.valid)
        r = summarize(p, p, self.spans, self.valid, self.case, "native")["events"][0]
        self.assertAlmostEqual(r["normalized_entropy"]["mean"], 1)
        self.assertAlmostEqual(r["reference_event_mass"]["mean"], r["uniform_event_mass"])
        # A mean phase of zero is still accompanied by high entropy/zero event mass.
        p[:] = 0
        p[:, :3, :, 0] = 8 / 13
        p[:, :3, :, 2] = 5 / 13
        self.case["frozen_events"][0]["native"] = [1, 4]
        r = summarize(p, p, self.spans, self.valid, self.case, "native")["events"][0]
        self.assertAlmostEqual(r["signed_phase_frames"]["mean"], 0)
        self.assertEqual(r["reference_event_mass"]["mean"], 0)
        self.assertGreater(r["normalized_entropy"]["mean"], .5)

    def test_missing_mapping_remains_missing(self):
        p = retrieval_probabilities(self.q, self.q, self.valid)
        self.case["frozen_events"][0]["native"] = [100, 105]
        r = summarize(p, p, self.spans, self.valid, self.case, "native")["events"][0]
        self.assertEqual(r["status"], "missing_event_bin_support")
        self.assertNotIn("signed_phase_frames", r)

    def test_malformed_probability_or_span_is_rejected(self):
        p = retrieval_probabilities(self.q, self.q, self.valid)
        p[0, 1, 0, 0] += .1
        with self.assertRaises(ValueError):
            summarize(p, p, self.spans, self.valid, self.case, "native")
        with self.assertRaises(ValueError):
            retrieval_probabilities(self.q, self.q, [False] * 4)
        with self.assertRaises(ValueError):
            normalized_content(self.q, np.ones(3), 1e-6)

    def test_rms_matches_direct_definition_and_input_untouched(self):
        raw = self.q.astype(np.float32)
        before = raw.copy()
        w = np.arange(1, 5, dtype=np.float32)
        out = normalized_content(raw, w, 1e-6)
        np.testing.assert_array_equal(raw, before)
        np.testing.assert_allclose(out, raw / np.sqrt((raw * raw).mean(-1, keepdims=True) + 1e-6) * w)

    def test_failed_or_mismatched_replay_never_enters_analysis(self):
        identity = {k: k for k in ("state_file_sha256", "old_x0_file_sha256",
                                   "historical_capture_manifest_sha256", "packed_x")}
        case = {"case_id": "test", "video_provenance": {"native": {"sha256": "original"}}}
        gate = {"passed": True, "raw_full_AV_hook_exact_equal": True, "case": "test", "method": "native",
                "qk_sha256": "qk", "original_video_sha256": "original", "input_identity": identity,
                "streams": {s: {"hook_exact_equal": True, "historical_pass": True} for s in ("video", "audio")}}
        capture = {"forward_identity": identity}
        validate_replay_gate(capture, "qk", gate, case, "native")
        for key, value in (("passed", False), ("raw_full_AV_hook_exact_equal", False),
                           ("case", "different"), ("method", "global_weak"), ("qk_sha256", "different"),
                           ("original_video_sha256", "different"), ("input_identity", {})):
            broken = copy.deepcopy(gate)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_replay_gate(capture, "qk", broken, case, "native")
        for stream in ("video", "audio"):
            broken = copy.deepcopy(gate)
            broken["streams"][stream]["historical_pass"] = False
            with self.assertRaises(ValueError):
                validate_replay_gate(capture, "qk", broken, case, "native")


if __name__ == "__main__":
    unittest.main()
