import unittest
from own_nvml import select_owned


class OwnNVML(unittest.TestCase):
    def test_records_only_exact_task_generations(self):
        owner = {"pid": 13, "uid": 1004, "start_ticks": 2, "cmdline_sha256": "a" * 64}
        rows = [{"pid": 13, "gpu_uuid": "own", "used_memory_mib": "123"},
                {"pid": 14, "gpu_uuid": "other", "used_memory_mib": "9000"}]
        result = select_owned(rows, [owner], lookup=lambda pid: owner)
        self.assertEqual([x["pid"] for x in result], [13])
        self.assertEqual(result[0]["used_memory_mib"], 123)

    def test_reused_pid_is_excluded(self):
        owner = {"pid": 13, "uid": 1004, "start_ticks": 2, "cmdline_sha256": "a" * 64}
        rows = [{"pid": 13, "gpu_uuid": "own", "used_memory_mib": "123"}]
        self.assertEqual(select_owned(rows, [owner], lookup=lambda pid: dict(owner, start_ticks=3)), [])


if __name__ == "__main__":
    unittest.main()
