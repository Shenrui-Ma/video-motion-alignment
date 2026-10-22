"""One explicit cached-conditioning capacity trial; stdlib and exact PID generations."""
import argparse
import hashlib
import json
import math
import os
import signal
import sys
import time
from contextlib import suppress
from pathlib import Path

GIB = 2**30
KEYS = ("pid", "uid", "start_ticks", "cmdline_sha256")
PROTECTED_PIDS = {1646285}
POLICY = {
    "entry_high": 34 * GIB, "entry_max": 46 * GIB, "entry_host": 64 * GIB,
    "stop_high": 8 * GIB, "stop_max": 20 * GIB, "stop_host": 40 * GIB,
    "raw_max_floor": 8 * GIB, "retained_cache": 6 * GIB,
    "psi_role": "diagnostic_only", "psi_diagnostic_reference": 1.0, "poll_seconds": .25,
}


def same_identity(left, right):
    return left is not None and all(str(left.get(k)) == str(right.get(k)) for k in KEYS)


def identity(pid, proc_root=Path("/proc")):
    p = Path(proc_root) / str(int(pid))
    try:
        before = (p / "stat").read_text().rsplit(") ", 1)[1].split()
        uid = p.stat().st_uid
        command = (p / "cmdline").read_bytes()
        after = (p / "stat").read_text().rsplit(") ", 1)[1].split()
        if before[0] == "Z" or after[0] == "Z" or not command:
            return None
        if before[19] != after[19] or p.stat().st_uid != uid:
            return None
        return {"pid": int(pid), "uid": uid, "start_ticks": int(after[19]),
                "cmdline_sha256": hashlib.sha256(command).hexdigest(),
                "cmdline": command.replace(b"\0", b" ").decode()}
    except (FileNotFoundError, ProcessLookupError):
        return None


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("missing/invalid nonnegative byte count")
    return value


def assess(snapshot, *, stage, baseline=None, previous_pressure_streak=0):
    """No policy mutation. R141b/R138 clean-unmapped-cache arithmetic is retained."""
    if stage not in ("entry", "running") or snapshot["uid"] != 1004:
        raise ValueError("unexpected trial stage/UID")
    parent = next(r for r in snapshot["ancestors"] if r["path"] == "/user.slice")
    if (parent["high_bytes"], parent["max_bytes"]) != (100 * GIB, 112 * GIB):
        raise ValueError("shared parent limits changed")
    old = {r["path"]: r for r in baseline["ancestors"]} if baseline else {}
    reasons, rows = [], []
    pressure = False
    host = integer(snapshot["host_available_bytes"])
    if (stage == "entry" and host < POLICY["entry_host"]) or (
            stage == "running" and host <= POLICY["stop_host"]):
        reasons.append("host MemAvailable threshold")
    for r in snapshot["ancestors"]:
        limits = {k: r[k + "_bytes"] for k in ("high", "max") if r.get(k + "_bytes") is not None}
        if not limits:
            continue
        current = integer(r["current_bytes"])
        s = r["stat"]
        for k in ("file", "shmem", "active_file", "inactive_file", "file_mapped",
                  "file_dirty", "file_writeback", "anon"):
            integer(s[k])
        disk = min(max(0, s["file"] - s["shmem"]), s["active_file"] + s["inactive_file"])
        clean = max(0, disk - s["file_mapped"] - s["file_dirty"] - s["file_writeback"])
        credit = min(current, max(0, clean - POLICY["retained_cache"]))
        adjusted = current - credit
        headroom = {k: integer(v) - adjusted for k, v in limits.items()}
        for k, free in headroom.items():
            bound = POLICY[("entry_" if stage == "entry" else "stop_") + k]
            rejected = free < bound if stage == "entry" else free <= bound
            if rejected:
                reasons.append(r["path"] + " adjusted " + k + " threshold")
        raw_max = limits.get("max")
        if raw_max is not None and raw_max - current <= POLICY["raw_max_floor"]:
            reasons.append(r["path"] + " raw max floor")
        for kind in ("some", "full"):
            value = r["pressure"][kind]["avg10"]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError("invalid PSI")
            pressure |= value > POLICY["psi_diagnostic_reference"]
        events_delta = {}
        if baseline is not None:
            if r["path"] not in old:
                raise ValueError("bounded cgroup ancestry changed")
            for k in ("max", "oom", "oom_kill"):
                d = integer(r["events"][k]) - integer(old[r["path"]]["events"][k])
                events_delta[k] = d
                if d != 0:
                    reasons.append(r["path"] + " event delta/reset: " + k)
        rows.append({"path": r["path"], "anon_bytes": s["anon"], "current_bytes": current,
                     "adjusted_current_bytes": adjusted, "credited_file_bytes": credit,
                     "adjusted_headroom_bytes": headroom,
                     "raw_max_headroom_bytes": None if raw_max is None else raw_max - current,
                     "pressure": r["pressure"], "events": r["events"], "events_delta": events_delta})
    if not rows:
        raise ValueError("no bounded cgroup")
    streak = previous_pressure_streak + 1 if pressure else 0
    return {"passed": not reasons, "stage": stage, "reasons": reasons,
            "pressure_streak": streak, "host_available_bytes": host, "ancestors": rows}


def signal_exact(expected, sig=signal.SIGTERM, *, lookup=identity,
                 pidfd_open=None, pidfd_signal=None, close=os.close, uid=None):
    """pidfd removes the identity-check/kill PID-reuse race; never signal a group."""
    uid = os.getuid() if uid is None else uid
    if expected["pid"] in PROTECTED_PIDS or expected["pid"] <= 1 or expected["uid"] != uid:
        return False
    if not same_identity(lookup(expected["pid"]), expected):
        return False
    opener = pidfd_open or os.pidfd_open
    sender = pidfd_signal or signal.pidfd_send_signal
    try:
        fd = opener(expected["pid"], 0)
    except ProcessLookupError:
        return False
    try:
        if not same_identity(lookup(expected["pid"]), expected):
            return False
        sender(fd, sig, None, 0)
        return True
    except ProcessLookupError:
        return False
    finally:
        close(fd)


def task_command(command, root):
    root = str(Path(root))
    return isinstance(command, list) and any(
        isinstance(arg, str) and (arg == root or arg.startswith(root + "/")) for arg in command)


def bind_service(root, *, lookup=identity):
    row = json.loads((Path(root) / "processes/service.json").read_text())
    if not task_command(row["command"], root):
        raise ValueError("service command does not name this task")
    current = lookup(row["pid"])
    old = row["identity"]
    if current is None or row["pid"] in PROTECTED_PIDS:
        raise ValueError("service unavailable/protected")
    if any(str(current[k]) != str(old[k]) for k in ("uid", "start_ticks", "cmdline")):
        raise ValueError("service generation/command differs")
    if current["uid"] != os.getuid():
        raise ValueError("service UID differs")
    return {k: current[k] for k in KEYS}


def read_registration(path, *, clock=time.monotonic, sleep=time.sleep):
    """Existing observer writer uses open('x') + json.dump, so allow its short write."""
    deadline = clock() + .05
    while True:
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            remaining = deadline - clock()
            if remaining <= 0:
                raise
            sleep(min(.01, remaining))


def registered_targets(root, owner):
    """Only exact descendants recorded for this service; no ps/process-name lookup."""
    rows, accepted = [], [owner]
    for p in (Path(root) / "audit/observations").rglob("*.process.json"):
        row = read_registration(p)
        if task_command(row.get("command"), root):
            rows.append(row)
    changed = True
    while changed:
        changed = False
        for row in rows[:]:
            if row.get("uid") == owner["uid"] and any(
                    same_identity(row.get("parent"), parent) for parent in accepted):
                target = {k: row[k] for k in KEYS}
                if target["pid"] not in PROTECTED_PIDS and target not in accepted:
                    accepted.append(target)
                rows.remove(row)
                changed = True
    return accepted


def process_memory(targets):
    rows = []
    for target in targets:
        if not same_identity(identity(target["pid"]), target):
            continue
        try:
            text = Path("/proc", str(target["pid"]), "status").read_text()
        except FileNotFoundError:
            continue
        fields = {k: v.strip() for k, v in (x.split(":", 1) for x in text.splitlines() if ":" in x)}
        rows.append({**target, "status": {k: fields.get(k) for k in
                                        ("VmRSS", "VmHWM", "RssAnon", "RssFile", "VmSwap")}})
    return rows


def monitor(root, output, ready):
    root, output, ready = Path(root).resolve(), Path(output), Path(ready)
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise RuntimeError("Linux pidfd support required before admission")
    owner = bind_service(root)
    try:
        return monitor_bound(root, output, ready, owner)
    except BaseException:
        # Includes baseline, mkdir/open/write/close, READY publication, and interrupt
        # failures. The controller also watches us, including uncatchable SIGKILL.
        try:
            signal_exact(owner)
        except (OSError, ValueError) as cleanup_error:
            with suppress(OSError, ValueError):
                print("exact service stop failed: " + repr(cleanup_error), file=sys.stderr)
        raise


def monitor_bound(root, output, ready, owner):
    if output.exists() or ready.exists():
        raise FileExistsError("preserve previous trial telemetry/readiness")
    sys.path.insert(0, str(root / "scripts"))
    import cgroup_memory
    baseline = cgroup_memory.snapshot(proc=Path("/proc", str(owner["pid"]), "cgroup"))
    output.parent.mkdir(parents=True, exist_ok=True)
    ready.parent.mkdir(parents=True, exist_ok=True)
    streak, stage = 0, "entry"
    with output.open("x", buffering=1) as log:
        while same_identity(identity(owner["pid"]), owner):
            tick = time.monotonic()
            try:
                current = baseline if stage == "entry" else cgroup_memory.snapshot(
                    proc=Path("/proc", str(owner["pid"]), "cgroup"))
                decision = assess(current, stage=stage, baseline=baseline if stage == "running" else None,
                                  previous_pressure_streak=streak)
                targets = registered_targets(root, owner)
                row = {"unix": time.time(), "owner": owner, "decision": decision,
                       "processes": process_memory(targets)}
            except Exception as error:  # noqa: BLE001 -- Any telemetry failure must stop this trial.
                decision = {"passed": False, "reasons": ["telemetry failure: " + repr(error)]}
                row = {"unix": time.time(), "owner": owner, "decision": decision}
                targets = [owner]
            if not decision["passed"]:
                row["signalled_exact_targets"] = [x for x in targets if signal_exact(x)]
                row["root_controller_owns_final_cleanup"] = True
                log.write(json.dumps(row) + "\n")
                return 2
            log.write(json.dumps(row) + "\n")
            streak = decision["pressure_streak"]
            if stage == "entry":
                temporary = ready.with_name(ready.name + ".tmp")
                with temporary.open("x") as f:
                    json.dump({"passed": True, "owner": owner, "policy": POLICY,
                               "monitor_identity": identity(os.getpid()), "entry": decision}, f)
                os.replace(temporary, ready)
                stage = "running"
            time.sleep(max(0, POLICY["poll_seconds"] - (time.monotonic() - tick)))
        log.write(json.dumps({"unix": time.time(), "owner": owner,
                              "original_service_generation_absent": True,
                              "root_controller_owns_final_cleanup": True}) + "\n")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--ready", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(monitor(args.root, args.output, args.ready))
