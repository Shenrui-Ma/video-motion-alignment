import copy
import unittest
from partial_release import validate_boundary, validate_partial


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.owner = {"pid": 123, "identity": {"uid": 1016, "start_ticks": "456", "cmdline": "owned"}}
        self.manifest = {
            "segments": {"host9_prefix": {"service_owner": self.owner, "run_ids": ["early", "late", "split"],
                "roles": ["early", "late", "split"], "producer_seal_sha256": "seal"}},
            "science": {"noise_file_sha256": "noise"},
        }
        self.job = {"name": "split", "service_pid": 123, "service_identity": self.owner["identity"],
                    "prompt_id": "accepted"}
        self.queue = {"queue_running": [[0, "accepted"]], "queue_pending": []}

    def boundary(self, **changes):
        args = dict(manifest=self.manifest, owner=self.owner, actual=self.owner["identity"],
                    job=self.job, queue=self.queue, global_exists=False,
                    approval={"root_approved": True})
        args.update(changes)
        return validate_boundary(**args)

    def test_only_running_split_boundary(self):
        self.boundary()
        for queue in [
            {"queue_running": [], "queue_pending": []},
            {"queue_running": [[0, "another"]], "queue_pending": []},
            {"queue_running": [[0, "accepted"]], "queue_pending": [[1, "global"]]},
        ]:
            with self.assertRaises(ValueError):
                self.boundary(queue=queue)
        with self.assertRaises(ValueError):
            self.boundary(job={**self.job, "name": "late"})

    def test_reused_pid_or_foreign_uid_never_admitted(self):
        for actual in [None, {**self.owner["identity"], "start_ticks": "457"},
                       {**self.owner["identity"], "uid": 1025},
                       {**self.owner["identity"], "cmdline": "other"}]:
            with self.assertRaises(ValueError):
                self.boundary(actual=actual)

    def test_global_started_or_withdrawn_rejected(self):
        with self.assertRaises(ValueError):
            self.boundary(global_exists=True)
        with self.assertRaises(ValueError):
            self.boundary(approval={"root_approved": False})

    def test_partial_requires_three_gates_exact_owner_and_real_release(self):
        gates = {role: {"passed": True, "service_owner": self.owner,
            "producer_seal_sha256": "seal", "run_id": role, "role": role,
            "NFE": 20, "Euler_updates": 20, "routed_blocks": 450, "alpha": 1,
            "phase_displacement": 0, "physical_query_window": [50, 65],
            "noise_sha256": "noise"} for role in ["early", "late", "split"]}
        cleanup = {"service_record": self.owner, "pid": 123, "process_absent": True,
                   "own_compute_absent": True, "child_compute_absent": True}
        kwargs = dict(manifest=self.manifest, owner=self.owner, gates=gates,
            cleanup=cleanup, failure={"error": "ValueError('root admission pending')", "unix": 20},
            request={"created_unix": 10}, monitor={"exit_code": 0, "exact_generation_absent": True})
        validate_partial(**kwargs)
        for field, value in [
            ("gates", {k: v for k, v in gates.items() if k != "split"}),
            ("cleanup", {**cleanup, "own_compute_absent": False}),
            ("failure", {"error": "unexpected OOM", "unix": 20}),
            ("monitor", {"exit_code": 1, "exact_generation_absent": True}),
        ]:
            with self.assertRaises(ValueError):
                validate_partial(**{**kwargs, field: value})
        wrong = copy.deepcopy(gates)
        wrong["split"]["service_owner"]["identity"]["start_ticks"] = "999"
        with self.assertRaises(ValueError):
            validate_partial(**{**kwargs, "gates": wrong})


if __name__ == "__main__":
    unittest.main()
