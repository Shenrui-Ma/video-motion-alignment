import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "mf_import", Path(__file__).with_name("import_verified_mf.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class JobDomainTests(unittest.TestCase):
    def plan(self, sid, roles):
        return {"groups": [sid], "jobs": [{"case": sid, "role": r} for r in roles],
                "unique_targets": len([r for r in roles if r != "source"])}

    def test_cached_ive_and_musk_counts(self):
        for sid, roles in (("short_0274", module.ARMS),
                           ("musk05", ("native", "fixed") + module.ARMS)):
            self.assertEqual(module.expected_jobs(sid, self.plan(sid, roles)),
                             (roles, len(roles)))

    def test_new_source_release_is_required(self):
        roles = ("native", "fixed") + module.ARMS
        for sid in ("firefly06", "sam07"):
            self.assertEqual(module.expected_jobs(sid, self.plan(sid, ("source",) + roles)),
                             (roles, 7))
            with self.assertRaises(Exception):
                module.expected_jobs(sid, self.plan(sid, roles))

    def test_missing_native_or_duplicate_roles_rejected(self):
        for roles in (("fixed",) + module.ARMS, ("early",) * 6):
            with self.assertRaises(Exception):
                module.expected_jobs("musk05", self.plan("musk05", roles))

    def stream(self, sid, role):
        return {"schema": "r150-completed-video-stream-input-v1", "passed": True,
                "case": sid, "role": role}

    def test_single_completed_target_and_first_source(self):
        for sid, role, source in (("long_0059", "early", False),
                                  ("sam07", "native", True),
                                  ("sam07", "fixed", False)):
            roles = ("source", role) if source else (role,)
            plan = self.plan(sid, roles)
            plan.update(new_source_trackers=int(source), source_cache_count=int(not source))
            self.assertEqual(module.expected_jobs(sid, plan, self.stream(sid, role)),
                             ((role,), len(roles)))

    def test_stream_rejects_extra_or_unregistered_target_and_wrong_case(self):
        stream = self.stream("long_0059", "early")
        plan = self.plan("long_0059", ("early",))
        plan.update(new_source_trackers=0, source_cache_count=1)
        for changed in (dict(stream, case="long_0039"), dict(stream, role="native"),
                        dict(stream, passed=False)):
            with self.assertRaises(Exception):
                module.expected_jobs("long_0059", plan, changed)
        plan["jobs"].append({"case": "long_0059", "role": "late"})
        with self.assertRaises(Exception):
            module.expected_jobs("long_0059", plan, stream)

    def test_stream_rejects_source_after_target(self):
        plan = self.plan("sam07", ("native", "source"))
        plan.update(new_source_trackers=1, source_cache_count=0)
        with self.assertRaises(Exception):
            module.expected_jobs("sam07", plan, self.stream("sam07", "native"))


if __name__ == "__main__":
    unittest.main()
