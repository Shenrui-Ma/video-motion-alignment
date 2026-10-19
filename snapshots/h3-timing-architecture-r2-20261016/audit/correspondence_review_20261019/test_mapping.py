import unittest
from render_bank_view import spans, representative_frames, token_center


class MappingTests(unittest.TestCase):
    def test_all_valid_frames_covered_once(self):
        self.assertEqual([i for a, b in spans(43) for i in range(a, b + 1)], list(range(145)))

    def test_h3_period_and_display_centers(self):
        self.assertEqual(spans(6), [(0, 0), (1, 4), (5, 8), (9, 12), (13, 16), (17, 17)])
        self.assertEqual(representative_frames(6), [0, 2, 6, 10, 14, 17])
        self.assertEqual(representative_frames(43)[-1], 142)

    def test_spatial_grid_maps_to_padded_input(self):
        self.assertEqual(token_center(0), (16, 16))
        self.assertEqual(token_center(942), (1296, 720))
        self.assertEqual(token_center(41), (16, 48))
        for index in (-1, 943):
            with self.assertRaises(ValueError): token_center(index)


if __name__ == '__main__':
    unittest.main()
