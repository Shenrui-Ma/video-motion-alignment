import unittest
from freeze_seed2 import scientific


class TestProvenance(unittest.TestCase):
    def test_only_path_ignored(self):
        a={'shape':[1,2],'dtype':'float32','sha256':'abc','tensor_file':'old/file'}
        b=dict(a,tensor_file='new/file')
        self.assertEqual(scientific(a),scientific(b))

    def test_raw_hash_mismatch_not_ignored(self):
        a={'video':{'shape':[1,2],'sha256':'a','tensor_file':'same'}}
        b={'video':{'shape':[1,2],'sha256':'b','tensor_file':'same'}}
        self.assertNotEqual(scientific(a),scientific(b))

    def test_timestamps_and_shape_not_ignored(self):
        a={'frames':[{'shape':[12,736,1312],'timestamp':.25}]}
        b={'frames':[{'shape':[12,736,1312],'timestamp':.5}]}
        self.assertNotEqual(scientific(a),scientific(b))


if __name__=='__main__':unittest.main()
