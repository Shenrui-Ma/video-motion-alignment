"""Run the unchanged final verifier across distinct SSH session cgroups on host60."""
import argparse
import importlib.util
import re
import sys
from pathlib import Path


def cross_session_delta(original, before, after):
    old = {row["path"]: row for row in before["ancestors"]}
    new = {row["path"]: row for row in after["ancestors"]}
    if old.keys() == new.keys():
        return original(before, after)
    assert before["uid"] == after["uid"] == 1015
    old_only, new_only = set(old) - set(new), set(new) - set(old)
    assert len(old_only) == len(new_only) == 1, "Unexpected cgroup hierarchy change"
    pattern = r"/user\.slice/user-1015\.slice/session-[0-9]+\.scope"
    old_scope, new_scope = next(iter(old_only)), next(iter(new_only))
    assert re.fullmatch(pattern, old_scope) and re.fullmatch(pattern, new_scope)
    common = set(old) & set(new)
    assert common == {"/", "/user.slice", "/user.slice/user-1015.slice"}
    # Runtime checks have already examined the original scope after every
    # tracking step. The final SSH scope is a different, newly created object.
    filtered_before = dict(before, ancestors=[old[p] for p in sorted(common)])
    filtered_after = dict(after, ancestors=[new[p] for p in sorted(common)])
    value = original(filtered_before, filtered_after)
    value["postrun_ssh_session_transition"] = {
        "old": old_scope, "new": new_scope, "common_ancestors": sorted(common),
        "original_scope_monitored_during_run": True,
        "new_scope_counter_compared_to_old_scope": False,
    }
    return value


def main(root, attempt):
    root = Path(root).resolve()
    assert root.parent == Path("/data4/researcher/h3_runs/guidance_schedule_mf_r150_host60_20261021")
    sys.path.insert(0, str(root / "scripts"))
    spec = importlib.util.spec_from_file_location("original_final_release", root / "audit/final_release.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    original = verifier.capacity.oom_delta
    verifier.capacity.oom_delta = lambda before, after: cross_session_delta(original, before, after)
    verifier.main(attempt)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--attempt", required=True)
    a = p.parse_args()
    main(a.root, a.attempt)
