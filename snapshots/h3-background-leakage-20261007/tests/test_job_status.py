import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comfy_job', ROOT / 'scripts/comfy_job.py')
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


class JobStatusTests(unittest.TestCase):
    def inspect(self, responses):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'logs').mkdir()
            record = root / 'logs/example_job.json'
            record.write_text(json.dumps({'prompt_id': 'ours', 'submitted_unix': 0}))
            output = io.StringIO()
            with patch.object(job, 'RUN', root), patch.object(job, 'request', side_effect=responses), \
                    contextlib.redirect_stdout(output):
                job.status('example')
            return json.loads(output.getvalue()), json.loads(record.read_text())

    def test_other_running_job_does_not_imply_ours_is_running(self):
        output, record = self.inspect([{}, {'queue_running': [[0, 'other']], 'queue_pending': []}, {}])
        self.assertEqual(output['status'], 'unknown_missing')
        self.assertEqual(record['status'], 'unknown_missing')

    def test_own_pending_job_is_present(self):
        output, _ = self.inspect([{}, {'queue_running': [], 'queue_pending': [[0, 'ours']]}])
        self.assertEqual(output['status'], 'pending_or_running')
        self.assertEqual(output['pending_ids'], ['ours'])

    def test_completion_race_rechecks_history(self):
        result = {'status': {'status_str': 'success'}, 'outputs': {'92': {'images': []}}}
        output, record = self.inspect([{}, {'queue_running': [], 'queue_pending': []}, {'ours': result}])
        self.assertEqual(output['status']['status_str'], 'success')
        self.assertEqual(record['status'], 'success')


if __name__ == '__main__':
    unittest.main()
