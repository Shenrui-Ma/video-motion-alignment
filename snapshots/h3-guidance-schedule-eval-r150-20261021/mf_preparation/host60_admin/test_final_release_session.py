import copy
import unittest
from final_release_session import cross_session_delta


def baseline():
    return {"uid": 1015, "ancestors": [
        {"path": p, "failcnt": 0} for p in
        ["/user.slice/user-1015.slice/session-100.scope",
         "/user.slice/user-1015.slice", "/user.slice", "/"]]}


def delta(a, b):
    assert {x["path"] for x in a["ancestors"]} == {x["path"] for x in b["ancestors"]}
    return {"passed": all(x["failcnt"] == y["failcnt"]
                          for x, y in zip(a["ancestors"], b["ancestors"]))}


class ReleaseTests(unittest.TestCase):
    def test_same_scope_is_unchanged(self):
        a = baseline()
        self.assertEqual(cross_session_delta(delta, a, a), {"passed": True})

    def test_only_new_ssh_session_is_allowed(self):
        a, b = baseline(), baseline()
        b["ancestors"][0]["path"] = "/user.slice/user-1015.slice/session-200.scope"
        self.assertTrue(cross_session_delta(delta, a, b)["passed"])

    def test_common_oom_not_hidden(self):
        a, b = baseline(), baseline()
        b["ancestors"][0]["path"] = "/user.slice/user-1015.slice/session-200.scope"
        b["ancestors"][1]["failcnt"] = 1
        self.assertFalse(cross_session_delta(delta, a, b)["passed"])

    def test_wrong_uid_or_parent_rejected(self):
        for change in ("uid", "parent"):
            a, b = baseline(), baseline()
            b["ancestors"][0]["path"] = "/user.slice/user-1015.slice/session-200.scope"
            if change == "uid":
                b["uid"] = 1016
            else:
                b["ancestors"][1]["path"] = "/other.slice"
            with self.assertRaises(AssertionError):
                cross_session_delta(delta, a, b)


if __name__ == "__main__":
    unittest.main()
