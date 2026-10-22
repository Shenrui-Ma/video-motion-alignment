"""Bounded three-case sequencing through the already reviewed case launchers.

No scientific files are edited. Each next case requires the previous actual
COMPLETE and exact owner release. STOP_BEFORE_NEXT_CASE pauses future launches.
"""
from pathlib import Path
import fcntl
import json
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ORDER = [("short_0252", "root_r151_cabin_attempt1"),
         ("short_0358", "root_r151_drink_attempt3"),
         ("05_real_megumi_v", "root_r151_sam_attempt1")]
PEERS = ["/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/" + sid
         for sid in ("short_0085", "short_0274", "musk05", "firefly06", "sam07")]
lock = (HERE / "DRIVER.lock").open("a")
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def run(name, *args):
    return subprocess.run([sys.executable, str(HERE / name), *args],
                          cwd=HERE, capture_output=True, text=True, check=True)


def current_peer():
    code = "ROOTS=" + repr(PEERS) + "\n" + r'''
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(ROOTS[0])/'scripts'));import service
live=[]
for root in ROOTS:
 p=Path(root)/'processes/service.json'
 if p.exists():
  owner=json.loads(p.read_text())
  if service.current_identity(owner['pid'])==owner['identity']:live.append(root)
assert len(live)<=1,live
print(json.dumps(live))
'''
    result = subprocess.run(["ssh", "-o", "ProxyCommand=none", "H3_SERVER_A", "python3 -"],
                            input=code, capture_output=True, text=True, check=True)
    peers = json.loads(result.stdout)
    return peers[0] if peers else None


try:
    for sid, attempt in ORDER:
        case = HERE / "cases" / sid
        contract = json.loads((case / "configs/scientific_contract.json").read_text())
        arms = {x["run_id"]: x["arm"] for x in contract["cases"]}
        if not (case / "audit/LAUNCH.json").exists():
            if (HERE / "STOP_BEFORE_NEXT_CASE").exists():
                raise RuntimeError("Future launch paused by STOP_BEFORE_NEXT_CASE")
            peer = current_peer()
            command = [sid, attempt] + ([peer] if peer else [])
            result = run("launch_one.py", *command)
            print("LAUNCHED", sid, result.stdout.strip(), flush=True)
        deadline = time.monotonic() + 43200
        previous = None
        while True:
            if time.monotonic() > deadline:
                raise RuntimeError("Monitoring deadline reached; no process was signaled")
            state = json.loads(run("monitor_case.py", sid).stdout)
            status = [(x["run_id"], x["completed_forward_calls"]) for x in state["jobs"]]
            if status != previous:
                print("PROGRESS", sid, status, flush=True)
                previous = status
            for gate in state["gates"]:
                run_id = gate["run"]
                if run_id in arms and not (case / "actual" / run_id / "COLLECTED.json").exists():
                    result = run("collect_job.py", sid, arms[run_id])
                    print("COLLECTED", sid, arms[run_id], result.stdout.strip(), flush=True)
            terminal = {Path(x["file"]).name: x for x in state["terminal"]
                        if Path(x["file"]).parent.name == attempt}
            if "FAILURE.json" in terminal:
                raise RuntimeError("Case failure: " + json.dumps(terminal["FAILURE.json"]))
            if "ROOT_EXIT_RECEIPT.json" in terminal and "COMPLETE.json" in terminal:
                release = terminal["ROOT_EXIT_RECEIPT.json"]["record"]
                complete = terminal.get("COMPLETE.json", {}).get("record", {})
                assert release["passed"] and release["process_absent"] and release["CUDA_allocation_absent"], release
                assert complete["passed"], complete
                assert not state["service"]["exact_generation_alive"]
                for item in terminal.values():
                    name = Path(item["file"]).name
                    out = case / "actual" / attempt / name
                    out.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["scp", "-o", "ProxyCommand=none",
                                    "H3_SERVER_A:" + item["file"], str(out)], check=True)
                    import hashlib
                    assert hashlib.sha256(out.read_bytes()).hexdigest() == item["sha256"]
                print("RELEASED", sid, terminal["ROOT_EXIT_RECEIPT.json"]["sha256"], flush=True)
                break
            time.sleep(45)
    (HERE / "INFERENCE_DRIVER_COMPLETE.json").write_text(
        json.dumps({"passed": True, "cases": ORDER, "unix": time.time(),
                    "new_videos": 6, "MF_started": False}, indent=2) + "\n")
    if not (HERE / "mf/audit/MF_LAUNCH.json").exists():
        result = run("finish_mf.py")
        print("MF_PREPARED_AND_LAUNCHED", result.stdout, flush=True)
    mf = HERE / "mf"
    runtime = json.loads((mf / "configs/RUNTIME.json").read_text())
    remote_root = runtime["remote_root"]
    deadline = time.monotonic() + 7200
    while True:
        code = "ROOT=" + repr(remote_root) + "\n" + r'''
from pathlib import Path
import json,sys
r=Path(ROOT);sys.path.insert(0,str(r/'scripts'));from common import identity
launch=json.loads((r/'audit/MF_LAUNCH.json').read_text())
expected=dict(pid=launch['pid'],**launch['identity'])
out={'wrapper_exact_alive':identity(launch['pid'])==expected,
 'results':[str(p.relative_to(r)) for p in (r/'results').glob('*/*.json')]}
p=r/'audit/actual_r151_mf_attempt1/COMPLETE.json'
if p.exists():out['complete']=json.loads(p.read_text())
print(json.dumps(out))
'''
        result = subprocess.run(["ssh", "-o", "ProxyCommand=none", "H3_SERVER_A", "python3 -"],
                                input=code, capture_output=True, text=True, check=True)
        state = json.loads(result.stdout)
        print("MF_PROGRESS", state, flush=True)
        if not state["wrapper_exact_alive"]:
            assert state.get("complete", {}).get("passed") and not state["complete"]["remaining"], state
            command = "cd " + shlex.quote(remote_root) + \
                " && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 " + \
                shlex.quote(runtime["python"]) + \
                " audit/final_release.py --attempt actual_r151_mf_attempt1"
            subprocess.run(["ssh", "-o", "ProxyCommand=none", "H3_SERVER_A", command], check=True)
            subprocess.run([sys.executable, str(mf / "audit/collect.py")], cwd=mf, check=True)
            release = json.loads((mf / "audit/FINAL_RELEASE_VERIFIED.json").read_text())
            scores = json.loads((mf / "audit/RESULTS_VERIFIED.json").read_text())
            assert release["passed"] and release["completed_generated_scores"] == 6
            assert scores["completed_targets"] == 6
            (HERE / "TASK_COMPLETE.json").write_text(json.dumps({
                "passed": True, "new_videos": 6, "new_MF_scores": 6,
                "GPU3_released": True, "scores": scores["results"], "unix": time.time()
            }, indent=2) + "\n")
            print("TASK_COMPLETE", flush=True)
            break
        if time.monotonic() > deadline:
            raise RuntimeError("MF observation deadline; no unrelated process was signaled")
        time.sleep(45)
except BaseException as error:
    (HERE / "INFERENCE_DRIVER_FAILURE.json").write_text(
        json.dumps({"error": repr(error), "unix": time.time(),
                    "scope": "Driver stopped; existing case controller retains its lifecycle."}, indent=2) + "\n")
    raise
