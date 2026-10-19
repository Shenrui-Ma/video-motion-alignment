import copy
import unittest
from remote_one import validate_pose


class Contract(unittest.TestCase):
    def setUp(self):
        self.p = {'geometry': {'frames': 158, 'fps': 24, 'width': 1152, 'height': 768}, 'extraction': {'start': 0, 'end': None, 'stride': 1}}
        self.raw = {'video': {'sha256': 'a', 'container_frame_count': 158, 'fps': 24.0, 'width': 1152, 'height': 768}, 'frames': [{'frame': i, 'time_s': i/24} for i in range(158)], 'extraction': copy.deepcopy(self.p['extraction']), 'provenance': {'device': 'cpu', 'providers': ['CPUExecutionProvider'], 'threads': 4}}

    def test_all158(self):
        self.assertIs(validate_pose(self.raw, 'a', self.p), self.raw)

    def test_141_rejected(self):
        self.raw['frames'] = self.raw['frames'][:141]
        with self.assertRaises(ValueError): validate_pose(self.raw, 'a', self.p)

    def test_147_cropped_rejected(self):
        self.raw['frames'] = self.raw['frames'][:147]
        with self.assertRaises(ValueError): validate_pose(self.raw, 'a', self.p)

    def test_nan_time_rejected(self):
        self.raw['frames'][3]['time_s'] = float('nan')
        with self.assertRaises(ValueError): validate_pose(self.raw, 'a', self.p)

    def test_wrong_input_rejected(self):
        with self.assertRaises(ValueError): validate_pose(self.raw, 'wrong', self.p)

    def test_source8fps_rejected(self):
        self.raw['video']['fps'] = 8
        with self.assertRaises(ValueError): validate_pose(self.raw, 'a', self.p)

    def test_duplicate_index_rejected(self):
        self.raw['frames'][3]['frame'] = 2
        with self.assertRaises(ValueError): validate_pose(self.raw, 'a', self.p)

    def test_cuda_rejected(self):
        self.raw['provenance']['providers'] = ['CUDAExecutionProvider']
        with self.assertRaises(ValueError): validate_pose(self.raw, 'a', self.p)


if __name__ == '__main__': unittest.main()
