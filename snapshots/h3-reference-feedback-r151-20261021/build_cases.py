"""Build only new R151 packages from frozen R149 inputs and host9 lifecycle."""
from pathlib import Path
import copy
import ast
import hashlib
import json
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "h3-guidance-schedule-r149-20261020"
ADMIN = OLD / "fallback_host9/cases/05_real_megumi_v"
REMOTE = "/home/researcher/h3_runs/reference_feedback_r151_20261021"
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n")


def edit(p, pairs):
    t = p.read_text()
    for a, b in pairs:
        if a not in t:
            raise ValueError(f"rewrite anchor absent in {p}: {a[:90]}")
        t = t.replace(a, b)
    p.write_text(t)


def build(sid):
    src = OLD / ("cases" if sid == "short_0358" else "fallback_host9/cases") / sid
    dst = HERE / "cases" / sid
    if dst.exists():
        raise FileExistsError(dst)
    dst.mkdir(parents=True)
    # Copy the declared static files only; old mutable runtime evidence stays old.
    for rel in read(src / "deploy_manifest.json")["files"]:
        if rel.startswith("tests/"):
            continue
        p = dst / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, p)
    for name in ("logs", "processes", "input", "output", "temp", "user", "tests"):
        (dst / name).mkdir(exist_ok=True)
    for p in (ADMIN / "scripts").glob("*.py"):
        shutil.copy2(p, dst / "scripts" / p.name)
    shutil.copy2(ADMIN / "audit/root_run_batch.py", dst / "audit/root_run_batch.py")
    for n in ("cgroup_policy.json", "readonly_peer.json", "gpu_quarantine.json"):
        shutil.copy2(ADMIN / "configs" / n, dst / "configs" / n)
    cached = dst / "extensions/H3CachedCondition/__init__.py"
    # Preserve each case's actual reconstruction (Sam has a portrait; others do
    # not). Transplant only the already tested cross-filesystem publication.
    donor = (ADMIN / "extensions/H3CachedCondition/__init__.py").read_text()
    donor_lines = donor.splitlines(keepends=True)
    functions = {n.name: "".join(donor_lines[n.lineno-1:n.end_lineno])
                 for n in ast.parse(donor).body if isinstance(n, ast.FunctionDef)}
    current = cached.read_text()
    if "def publish_blob(" not in current:
        current = current.replace("import os\n", "import os\nimport errno\nimport shutil\nimport uuid\n")
        current = current.replace("def signature(", functions["publish_blob"] + "\n\n\ndef signature(")
    lines = current.splitlines(keepends=True)
    node = next(n for n in ast.parse(current).body if isinstance(n, ast.FunctionDef) and n.name == "publish_metadata")
    cached.write_text("".join(lines[:node.lineno-1]) + functions["publish_metadata"] + "\n" +
                      "".join(lines[node.end_lineno:]))
    shutil.copy2(HERE / "templates/reciprocal.py", dst / "extensions/H3TemporalRouter/reciprocal.py")
    shutil.copy2(HERE / "templates/test_reciprocal.py", dst / "tests/test_reciprocal.py")
    for n in ("test_host9.py", "test_parent_stop.py", "test_cross_device_cache.py"):
        shutil.copy2(ADMIN / "tests" / n, dst / "tests" / n)
    runtime = read(ADMIN / "configs/runtime.json")
    runtime.update(remote_root=REMOTE + "/cases/" + sid, port=8651, gpu_index=3,
                   expected_gpu_index=3, gpu_uuid="GPU-REDACTED",
                   minimum_free_mib=40960, profile="r151_host9_bidirectional_" + sid,
                   profile_scope="One service, two early arms; shared GPU with reserve8; original kernels")
    write(dst / "configs/runtime.json", runtime)
    s = read(src / "configs/scientific_contract.json")
    original = copy.deepcopy(next(x for x in s["cases"] if x["arm"] == "early"))
    s.update(schema="r151-bidirectional-same-time-v1", arms=["reverse_only", "combined"],
             scope="R149 early forward plus R25 reverse SAME; per-direction original group mass",
             original_forward_run=original["run_id"])
    s["cases"] = []
    for arm, alpha in (("reverse_only", 0.), ("combined", 1.)):
        c = copy.deepcopy(original)
        c.update(run_id=f"r151_{sid}_seed{c['seed']}_{arm}", arm=arm, alpha=alpha, beta=1.)
        s["cases"].append(c)
    s["case_order"] = [c["run_id"] for c in s["cases"]]
    s["execution_runtime"] = "host9 Torch2.5.1; original tensors and kernel source retained"
    write(dst / "configs/scientific_contract.json", s)
    write(dst / "configs/queue.json", {"jobs": s["case_order"], "finalize": True})
    for p in (dst / "configs/graphs").glob("*.json"):
        p.unlink()

    contract = dst / "scripts/r132_contract.py"
    edit(contract, [
        ('"early": list(range(9)), "late": list(range(11, 20)),\n             "split": list(range(4)) + list(range(15, 20)), "global_weak": list(range(20))',
         '"reverse_only": list(range(9)), "combined": list(range(9))'),
        ('"H3FixedSchedule"', '"H3ReciprocalTime"'),
        ('schedule=c["arm"])', 'schedule="early", beta=c["beta"], arm=c["arm"])'),
        ('len(set(order)) == 4', 'len(set(order)) == 2'),
        ('four ordered unique arms required', 'two ordered unique R151 arms required'),
        ('(20 if c["arm"] == "global_weak" else 9)', '9'),
        ('"05_real_megumi_v": (2026101311, 141, [50, 65])',
         '"05_real_megumi_v": (2026101311, 141, [50, 65]),\n                    "short_0358": (2026101701, 107, [0, 104])'),
        ('expected_window = [0, c["valid_frame_count"]-1] if c["arm"] == "global_weak" else expected[2]',
         'expected_window = expected[2]'),
        ('require(c["alpha"] == (.25 if c["arm"] == "global_weak" else 1.0), "arm alpha changed")',
         'require(c["alpha"] == (0.0 if c["arm"] == "reverse_only" else 1.0) and c["beta"] == 1.0, "arm strength changed")'),
        ('run_id, audit_path, schedule):', 'run_id, audit_path, schedule, beta, arm):'),
        ('block_end, step_start, step_end, schedule) ==', 'block_end, step_start, step_end, schedule, beta, arm) =='),
        ('0, 50, 0, 20, row["arm"])', '0, 50, 0, 20, "early", row["case"]["beta"], row["arm"])')
    ])
    init = dst / "extensions/H3TemporalRouter/__init__.py"
    edit(init, [
        ('from .schedule import ScheduleState, ScheduleBlockPatch, SCHEDULES',
         'from .reciprocal import ReciprocalState, ReciprocalBlockPatch\nSCHEDULES = {"early": tuple(range(9))}'),
        ('H3FixedSchedule', 'H3ReciprocalTime'),
        ('"schedule": (list(SCHEDULES),),',
         '"arm": (["reverse_only", "combined"],), "beta": ("FLOAT", {"default": 1.0, "min": 1.0, "max": 1.0}), "schedule": (list(SCHEDULES),),'),
        ('audit_dir, enabled=True):', 'audit_dir, enabled=True, beta=1.0, arm="combined"):'),
        ('run_id, audit_dir, schedule)', 'run_id, audit_dir, schedule, beta, arm)'),
        ('state = ScheduleState(', 'state = ReciprocalState('),
        ('run_id, audit_dir, schedule=schedule)', 'run_id, audit_dir, beta=beta, arm=arm)'),
        ('ScheduleBlockPatch(state, index)', 'ReciprocalBlockPatch(state, index)'),
        ('R149 requires original fixed mass-preserving attention', 'R151 requires original group-mass-preserving attention'),
        ('H3 fixed same-bin denoise schedule', 'H3 bidirectional same-time routing')
    ])
    smoke = dst / "scripts/cpu_runtime_smoke.py"
    edit(smoke, [
        ('H3FixedSchedule', 'H3ReciprocalTime'),
        ("apply(base,positive,c['arm'],'mass_preserve'", "apply(base,positive,'early','mass_preserve'"),
        ("'cpu_'+c['arm'],tmp,True)", "'cpu_'+c['arm'],tmp,True,beta=c['beta'],arm=c['arm'])"),
        ("len({id(x) for x in states})==4", "len({id(x) for x in states})==2"),
        ("actual_ModelPatcher_clone_isolated_four_arms", "actual_ModelPatcher_clone_isolated_two_arms")
    ])
    verifier = dst / "analysis/postrun/verify_schedule.py"
    edit(verifier, [
        ('"schedule": case["arm"]', '"schedule": "early", "arm": case["arm"], "beta": case["beta"]'),
        ('"started_calls": 1000', '"forward_routed_calls": 450 if case["alpha"] else 0, "reverse_routed_calls": 450,\n                "started_calls": 1000'),
        ('r149-schedule-job-gate-v1', 'r151-bidirectional-job-gate-v1'),
        ('"alpha": case["alpha"], "phase_displacement": 0,', '"alpha": case["alpha"], "beta": case["beta"], "phase_displacement": 0,\n            "reverse_ranges": router["reverse_ranges"], "forward_routed_calls": router["forward_routed_calls"],\n            "reverse_routed_calls": router["reverse_routed_calls"],'),
        ('r149-fixed-schedule-runtime-gate-v1', 'r151-bidirectional-runtime-gate-v1'),
        ('"historical_mid_reused": True', '"historical_native_and_r149_early_reused": True')
    ])
    root_run = dst / "audit/root_run_batch.py"
    edit(root_run, [
        ("ROOT/'analysis/postrun/05_real_megumi_v/SCHEDULE_RUNTIME_GATE.json'",
         f"ROOT/'analysis/postrun/{sid}/SCHEDULE_RUNTIME_GATE.json'"),
        ("r149-schedule-completion-v1", "r151-bidirectional-completion-v1"),
        ("root!=ROOT and root.parent in managed",
         "root!=ROOT and (root.parent in managed or str(root) in " +
         repr(["/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/" + x
               for x in ("short_0085", "short_0274")]) + ")")
    ])
    edit(dst / "scripts/execution_gate.py", [("r149-schedule-batch-seal-v1", "r151-bidirectional-batch-seal-v1")])
    for name in ("service.py", "start_controller.py"):
        p = dst / "scripts" / name
        p.write_text(p.read_text().replace("H3FixedSchedule", "H3ReciprocalTime"))
    # All original numerical files remain literally unchanged.
    write(dst / "audit/INHERITANCE.json", {
        "schema": "r151-reuse-v1", "scientific_parent": str(src),
        "scientific_parent_seal_sha256": sha(src / "deploy_manifest.json"),
        "lifecycle_parent": str(ADMIN), "lifecycle_parent_seal_sha256": sha(ADMIN / "deploy_manifest.json"),
        "new_operator": "extensions/H3TemporalRouter/reciprocal.py",
        "new_scope": "R149 unchanged forward + existing R25 reverse SAME algebra",
        "online_VAE_pose": False, "NFE": 20})
    policy = read(dst / "configs/storage_policy.json")
    policy.update(expected_new_runs=2, expected_total_frames=original["geometry"]["frames"]*2,
                  registered_frames_total=original["geometry"]["frames"]*2)
    write(dst / "configs/storage_policy.json", policy)
    # Import only the pure contract in a separate interpreter to avoid case bleed.
    subprocess.run([sys.executable, "-c",
        "import sys,json;from pathlib import Path;sys.path.insert(0,'scripts');import r132_contract as c;"
        "[(Path('configs/graphs')/(r+'.json')).write_text(json.dumps(c.expected_graph(r),indent=2)+'\\n') for r in c.science()['case_order']];"
        "print(c.registry()[1])"], cwd=dst, check=True)
    print("BUILT", sid, runtime["remote_root"])


if __name__ == "__main__":
    for sid in sys.argv[1:] or ["short_0252", "short_0358", "05_real_megumi_v"]:
        build(sid)
