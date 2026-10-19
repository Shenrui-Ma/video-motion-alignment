import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r14_host9_service', ROOT / 'scripts/service.py')
service = importlib.util.module_from_spec(spec); spec.loader.exec_module(service)
A = {'scope':'own_user_gpu_limit', 'max_owned_gpus':2}
Q = {'queue_running':[], 'queue_pending':[]}

class Host9AdmissionTests(unittest.TestCase):
    def check(self, rows, uids, identities=None):
        if identities is None: identities = {pid:{'uid':uid,'start_ticks':'12','cmdline_sha256':'audit'} for pid,uid in uids.items()}
        with patch.object(service.os, 'getuid', return_value=1000), \
             patch.object(service, 'proc_uid', side_effect=lambda pid:uids.get(pid)), \
             patch.object(service, 'external_identity', side_effect=lambda pid:identities.get(pid)):
            return service.check_admission(A, rows, Q)

    def test_empty_and_other_users_unrestricted(self):
        self.check([], {})
        self.check([{'pid':p,'gpu_uuid':str(p)} for p in range(3)], {0:2000,1:2001,2:2002})

    def test_one_own_gpu_allowed_including_multiple_processes(self):
        self.check([{'pid':1,'gpu_uuid':'OTHER'}, {'pid':2,'gpu_uuid':'OTHER'}], {1:1000,2:1000})

    def test_two_distinct_owned_gpus_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'two GPUs'):
            self.check([{'pid':1,'gpu_uuid':'OTHER'}, {'pid':2,'gpu_uuid':'THIRD'}], {1:1000,2:1000})

    def test_selected_gpu_rejected_for_any_owner(self):
        for uid in [1000,2000,None]:
            with self.assertRaisesRegex(RuntimeError, 'Selected GPU'):
                self.check([{'pid':1,'gpu_uuid':service.GPU}], {1:uid})

    def test_unreadable_or_raced_identity_fails_closed(self):
        rows = [{'pid':1,'gpu_uuid':'OTHER'}]
        with self.assertRaisesRegex(RuntimeError, 'ownership unavailable'): self.check(rows, {})
        with self.assertRaisesRegex(RuntimeError, 'identity changed'): self.check(rows, {1:1000}, {})
        with self.assertRaisesRegex(RuntimeError, 'identity changed'): self.check(rows, {1:1000}, {1:{'uid':2000}})

    def test_queue_and_policy_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'queued/running'):
            service.check_admission(A, [], {'queue_running':[1],'queue_pending':[]})
        with self.assertRaisesRegex(RuntimeError, 'frozen'):
            service.check_admission(dict(A, max_owned_gpus=3), [], Q)

    def test_job_recheck_excludes_only_registered_owner(self):
        source = (ROOT / 'scripts/job.py').read_text()
        self.assertIn("if row['pid'] != owner['pid']", source)
        self.assertIn('service.check_admission(admission, other_processes, existing_queue)', source)

if __name__ == '__main__': unittest.main()
