import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[1])]
import prepare_stream_batch as stream
from common import case_and_schedule, read
from ingest import validate_job


class CompletedVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.case, cls.schedule = case_and_schedule("long_0059", "early")
        cls.proof = read(stream.ROOT / "review/long_0059/early/PRESENTATION.json")["validated_execution"]
        cls.binding = read(cls.proof["binding"]["file"])

    def test_passed_job_is_usable_while_producer_continues(self):
        video, run_id, evidence = stream.validate_completed_target(self.case, "early")
        self.assertEqual(video, self.proof["video"])
        self.assertEqual(run_id, self.binding["run_id"])
        self.assertTrue(evidence["generation_batch_release_pending"])
        self.assertIsNone(evidence["generation_batch_release"])

    def test_failed_or_wrong_role_job_rejected(self):
        for field, value in (("passed", False), ("role", "late"),
                             ("producer_seal_sha256", "0" * 64)):
            gate = copy.deepcopy(self.proof["run_record"])
            gate[field] = value
            with self.assertRaises(Exception):
                validate_job(self.case, self.schedule, self.binding, gate)

    def test_wrong_media_sha_rejected(self):
        original = stream.validate.__globals__["bound"]
        def wrong_media(path):
            row = original(path)
            if str(path) == self.proof["video"]["file"]:
                row = dict(row, sha256="0" * 64)
            return row
        with patch.dict(stream.validate.__globals__, bound=wrong_media):
            with self.assertRaises(Exception):
                stream.validate_completed_target(self.case, "early")


if __name__ == "__main__":
    unittest.main()
