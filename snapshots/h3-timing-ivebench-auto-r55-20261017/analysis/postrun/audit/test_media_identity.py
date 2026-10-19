import unittest
import numpy as np
from prove_media_identity import compare_arrays


class ExactMediaTests(unittest.TestCase):
    def test_same_values(self):
        a = np.arange(72, dtype=np.uint8).reshape(2, 3, 4, 3)
        self.assertTrue(compare_arrays(a, a.copy())['exact'])

    def test_single_channel_difference(self):
        a = np.zeros((2, 3, 4, 3), dtype=np.uint8)
        b = a.copy(); b[1, 1, 2, 2] = 1
        result = compare_arrays(a, b)
        self.assertFalse(result['exact'])
        self.assertEqual(result['frames'][1]['differing_channels'], 1)
        self.assertEqual(result['frames'][1]['maximum_absolute_channel_error'], 1)

    def test_wrapping_unsigned_difference(self):
        a = np.zeros((1, 1, 1, 3), dtype=np.uint8)
        b = np.full_like(a, 255)
        self.assertEqual(compare_arrays(a, b)['frames'][0]['maximum_absolute_channel_error'], 255)

    def test_shape_rejected(self):
        a = np.zeros((2, 3, 4, 3), dtype=np.uint8)
        self.assertFalse(compare_arrays(a, a[:1])['exact'])

    def test_frame_order_matters(self):
        a = np.arange(72, dtype=np.uint8).reshape(2, 3, 4, 3)
        self.assertFalse(compare_arrays(a, a[::-1])['exact'])


if __name__ == '__main__':
    unittest.main()
