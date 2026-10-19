import unittest
import torch
from metric_adapter import scoring_functions, score_tracks


class OfficialMetricSemantics(unittest.TestCase):
    def test_identity_index_penalty_is_preserved(self):
        # An identical diagonal and orthogonal off-diagonal both score zero
        # after the official identity-matrix subtraction.
        matrix = torch.eye(2)
        self.assertEqual(scoring_functions()["get_score"](matrix)["average_score"], 0.0)

    def test_different_points_with_equal_motion_score_one(self):
        frames = torch.arange(5, dtype=torch.float32)
        tracks = torch.stack([torch.stack([frames, frames * 0], -1), torch.stack([frames + 10, frames * 0 + 5], -1)])
        record, matrix = score_tracks(tracks, tracks)
        self.assertTrue(torch.equal(matrix, torch.ones(2, 2)))
        self.assertEqual(record["score"], 1.0)

    def test_static_tracks_remain_undefined(self):
        record, matrix = score_tracks(torch.zeros(2, 5, 2), torch.zeros(2, 5, 2))
        self.assertIsNone(record["score"])
        self.assertEqual(record["nonfinite_similarity_entries"], 4)
        self.assertTrue(torch.isnan(matrix).all())

    def test_unequal_timebase_is_rejected(self):
        with self.assertRaises(ValueError):
            score_tracks(torch.zeros(2, 5, 2), torch.zeros(2, 4, 2))

    def test_adapter_matches_direct_official_function_calls(self):
        generator = torch.Generator().manual_seed(42)
        edited = torch.randn(9, 49, 2, generator=generator).cumsum(1)
        reference = torch.randn(9, 49, 2, generator=generator).cumsum(1)
        functions = scoring_functions()
        original = functions["get_similarity_matrix"](edited, reference)
        record, matrix = score_tracks(edited, reference)
        self.assertTrue(torch.equal(original, matrix))
        self.assertEqual(record["score"], functions["get_score"](original)["average_score"])


if __name__ == "__main__":
    torch.set_num_threads(1)
    unittest.main()
