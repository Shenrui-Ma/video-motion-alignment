import copy
import unittest
from rebind_gpu import check_change


class GPURebind(unittest.TestCase):
    def setUp(self):
        self.before = {"gpu_index": 1, "expected_gpu_index": 1, "gpu_uuid": "GPU-old",
                       "port": 8640, "models": "/existing/models"}

    def test_only_gpu_binding_allowed(self):
        after = dict(self.before, gpu_index=2, expected_gpu_index=2, gpu_uuid="GPU-new")
        self.assertEqual(set(check_change(self.before, after)),
                         {"gpu_index", "expected_gpu_index", "gpu_uuid"})

    def test_other_runtime_changes_rejected(self):
        after = dict(self.before, gpu_index=2, expected_gpu_index=2, gpu_uuid="GPU-new", port=9000)
        with self.assertRaises(ValueError):
            check_change(self.before, after)

    def test_inconsistent_index_rejected(self):
        after = dict(self.before, gpu_index=2, gpu_uuid="GPU-new")
        with self.assertRaises(ValueError):
            check_change(self.before, after)


if __name__ == "__main__":
    unittest.main()
