"""One bounded read-only gate check; call at most once per 60 seconds."""
import base64
import hashlib
import json
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "audit/online_monitor"
REMOTE = """import json,hashlib,pathlib,sys
items=json.loads(sys.argv[1]);out=[]
for x in items:
 p=pathlib.Path(x['root'])/x['relative']
 r={'case':x['case'],'role':x['role'],'path':str(p),'exists':p.is_file()}
 if p.is_file():
  b=p.read_bytes();j=json.loads(b)
  r.update(sha256=hashlib.sha256(b).hexdigest(),passed=j.get('passed'),
   run_id=j.get('run_id'),video=j.get('video',{}).get('file'),
   video_sha256=j.get('video',{}).get('sha256'))
 out.append(r)
print(json.dumps(out))
"""


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    latest = DEST / "LATEST.json"
    previous = json.loads(latest.read_text()) if latest.exists() else {}
    if time.time() - previous.get("checked_unix", 0) < 60:
        print("Previous bounded check is less than 60 seconds old.")
        return
    hosts = {}
    for path in sorted((ROOT / "runtime").glob("*/*.json")):
        b = json.loads(path.read_text())
        if b.get("status") != "READY":
            continue
        hosts.setdefault(b["host"], []).append({
            "case": b["source_id"], "role": b["role"],
            "root": b["remote_root"], "relative": b["gate_relative_file"],
            "binding_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {"checked_unix": time.time(), "scope": "Existing JSON gates only; no GPU or process operation.",
              "hosts": {}, "errors": {}}
    for host, entries in hosts.items():
        payload = base64.b64encode(REMOTE.encode()).decode()
        code = "exec(__import__('base64').b64decode(" + repr(payload) + "))"
        command = "python3 -c " + shlex.quote(code) + " " + shlex.quote(json.dumps(entries))
        proc = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host, command],
                              capture_output=True, text=True, timeout=45)
        if proc.returncode:
            result["errors"][host] = proc.stderr[-1000:]
        else:
            result["hosts"][host] = json.loads(proc.stdout)
    latest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (DEST / (str(int(result["checked_unix"])) + ".json")).write_bytes(latest.read_bytes())
    old = {r["path"]: r.get("sha256") for rows in previous.get("hosts", {}).values() for r in rows}
    ready = [r for rows in result["hosts"].values() for r in rows if r.get("passed") is True]
    changed = [r for r in ready if old.get(r["path"]) != r["sha256"]]
    print(json.dumps({"passed_gate_count": len(ready), "new_or_changed": changed,
                      "errors": result["errors"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
