"""One bounded read-only sample of Sam's shared GPU and existing model load log."""
import json
from pathlib import Path
import subprocess

SCRIPT = r'''
import json, subprocess, time
from pathlib import Path
uuid = "GPU-REDACTED"
gpu = subprocess.check_output([
    "nvidia-smi", "-i", uuid,
    "--query-gpu=uuid,memory.total,memory.free,memory.used,utilization.gpu,temperature.gpu",
    "--format=csv,noheader,nounits"], text=True).strip()
rows = subprocess.check_output([
    "nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory",
    "--format=csv,noheader,nounits"], text=True).splitlines()
processes = []
for line in rows:
    fields = [field.strip() for field in line.split(",")]
    if fields[0] != uuid:
        continue
    pid = int(fields[1])
    uid = None
    try:
        uid = int(next(line.split()[1] for line in
            (Path("/proc") / str(pid) / "status").read_text().splitlines()
            if line.startswith("Uid:")))
    except (OSError, StopIteration):
        pass
    processes.append({"pid": pid, "uid": uid, "used_memory_mib": fields[2]})
root = Path("/home/researcher/h3_runs/guidance_schedule_r149_host9_20261020/cases/05_real_megumi_v")
log = (root / "logs/comfyui.log").read_text(errors="replace")
loads = [line for line in log.splitlines()
         if "loaded partially;" in line or "Requested to load MiniMaxH3" in line]
print(json.dumps({"unix": time.time(), "gpu_csv": gpu,
                  "compute": processes, "model_load_tail": loads[-8:]}))
'''

result = subprocess.run(
    ["ssh", "H3_SERVER_A", "python3 -"], input=SCRIPT,
    text=True, capture_output=True, check=True, timeout=25)
record = json.loads(result.stdout)
output = (Path(__file__).resolve().parent / "cases/05_real_megumi_v/audit/"
          "sam_attempt3_monitor/SHARED_GPU_OBSERVATIONS.jsonl")
with output.open("a") as handle:
    handle.write(json.dumps(record) + "\n")
print(json.dumps(record))
