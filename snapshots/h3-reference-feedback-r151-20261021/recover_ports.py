"""Administrative port separation after the first case's socket shutdown."""
from pathlib import Path
import hashlib
import io
import json
import shlex
import shutil
import subprocess
import tarfile
import time

HERE = Path(__file__).resolve().parent
SSH = ["ssh", "-o", "ProxyCommand=none", "H3_SERVER_A"]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

for sid, port in (("short_0358", 8661), ("05_real_megumi_v", 8662)):
    case = HERE / "cases" / sid
    runtime_path = case / "configs/runtime.json"
    runtime = json.loads(runtime_path.read_text())
    root = runtime["remote_root"]
    history = case / "audit/port_update_history"
    history.mkdir(exist_ok=False)
    for rel in ("deploy_manifest.json", "configs/runtime.json", "audit/TARGET_CPU_VALIDATION.json"):
        shutil.copy2(case / rel, history / Path(rel).name)
    runtime["port"] = port
    runtime_path.write_text(json.dumps(runtime, indent=2) + "\n")
    manifest = json.loads((case / "deploy_manifest.json").read_text())
    manifest["created_unix"] = time.time()
    manifest["files"]["configs/runtime.json"] = {
        "sha256": sha(runtime_path), "bytes": runtime_path.stat().st_size
    }
    (case / "deploy_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    code = "ROOT=" + repr(root) + "\n" + r'''
from pathlib import Path
import json,sys,shutil,os,time
r=Path(ROOT);sys.path.insert(0,str(r/'scripts'));import service
assert not(r/'processes/service.json').exists()
h=r/'audit/port_update_history';h.mkdir(exist_ok=False)
for rel in ('deploy_manifest.json','configs/runtime.json','audit/TARGET_CPU_VALIDATION.json'):
 shutil.copy2(r/rel,h/Path(rel).name)
records=[]
for p in (r/'processes').glob('supervisor*.json'):
 d=json.loads(p.read_text());record=d.get('supervisor',d)
 if 'pid' in record and 'identity' in record:
  actual=service.current_identity(record['pid'])
  assert actual!=record['identity'],record
  records.append({'file':str(p),'owner':record,'current_identity':actual,'original_generation_absent':True})
if (r/'audit/LAUNCH.json').exists():
 d=json.loads((r/'audit/LAUNCH.json').read_text())
 assert service.current_identity(d['pid'])!=d['identity']
assert not list((r/'output').glob('*.mp4'))
archive=r/'audit/pre_cuda_attempt1_archive';archive.mkdir(exist_ok=False)
for rel in ('processes','logs','audit/LAUNCH.json','audit/ROOT_WRAPPER.log',
            'audit/ROOT_SCREEN_APPROVAL.json','audit/ROOT_PRELAUNCH_REVIEW.json','configs/admission.json'):
 p=r/rel
 if p.exists():
  target=archive/rel;target.parent.mkdir(parents=True,exist_ok=True);p.rename(target)
for folder in ('processes','logs'):(r/folder).mkdir(exist_ok=True)
(archive/'RECOVERY.json').write_text(json.dumps({'passed':True,'registered_service':False,
 'zero_forward':True,'exact_process_checks':records,'unix':time.time(),
 'reason':'Previous case completed; immediate port reuse failed before CUDA. Use distinct registered ports.'},indent=2)+'\n')
print(json.dumps({'archived':str(archive),'processes_verified':len(records)}))
'''
    subprocess.run(SSH + ["python3 -"], input=code, text=True, check=True)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for rel in ("configs/runtime.json", "deploy_manifest.json"):
            tar.add(case / rel, arcname=rel, recursive=False)
    subprocess.run(SSH + ["tar -xf - -C " + shlex.quote(root)],
                   input=buffer.getvalue(), check=True)
    code = "ROOT=" + repr(root) + "\nPORT=" + repr(port) + "\n" + r'''
from pathlib import Path
import json,hashlib,socket,sys,time
r=Path(ROOT);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((r/'audit/port_update_history/deploy_manifest.json').read_text())
new=json.loads((r/'deploy_manifest.json').read_text())
assert old['files'].keys()==new['files'].keys()
changed=[p for p in old['files'] if old['files'][p]!=new['files'][p]]
assert changed==['configs/runtime.json'],changed
assert all(sha(r/p)==v['sha256'] for p,v in new['files'].items())
a=json.loads((r/'audit/port_update_history/runtime.json').read_text())
b=json.loads((r/'configs/runtime.json').read_text())
assert {k for k in a if a[k]!=b[k]}=={'port'}
sys.path.insert(0,str(r/'scripts'));import service
assert service.PORT==PORT
with socket.socket() as s:s.bind(('127.0.0.1',PORT))
prior=r/'audit/port_update_history/TARGET_CPU_VALIDATION.json'
proof=json.loads(prior.read_text());assert proof['passed']
assert proof['producer_seal_sha256']==sha(r/'audit/port_update_history/deploy_manifest.json')
proof['producer_seal_sha256']=sha(r/'deploy_manifest.json')
proof['port_revalidation']={'passed':True,'changed_files':changed,'prior_CPU_proof_sha256':sha(prior),
 'old_port':a['port'],'new_port':PORT,'actual_service_port':service.PORT,
 'bind_probe_passed':True,'numerical_files_changed':False,'cached_tensor_reload':False,'unix':time.time()}
(r/'audit/TARGET_CPU_VALIDATION.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'passed':True,'port':PORT,'seal_sha256':proof['producer_seal_sha256']}))
'''
    subprocess.run(SSH + ["python3 -"], input=code, text=True, check=True)
    subprocess.run(["scp", "-o", "ProxyCommand=none",
                    "H3_SERVER_A:" + root + "/audit/TARGET_CPU_VALIDATION.json",
                    str(case / "audit/TARGET_CPU_VALIDATION.json")], check=True)
    launch = case / "audit/LAUNCH.json"
    if launch.exists():
        launch.rename(history / "LAUNCH.json")
    subprocess.run(["rsync", "-a", "-e", "ssh -o ProxyCommand=none",
                    "H3_SERVER_A:" + root + "/audit/pre_cuda_attempt1_archive/",
                    str(case / "audit/pre_cuda_attempt1_archive") + "/"], check=True)
    if sid == "short_0358":
        subprocess.run(["rsync", "-a", "-e", "ssh -o ProxyCommand=none",
                        "H3_SERVER_A:" + root + "/audit/root_r151_drink_attempt1/",
                        str(case / "audit/root_r151_drink_attempt1") + "/"], check=True)

handoff = json.loads((HERE / "HANDOFF.json").read_text())
for row in handoff["cases"]:
    case = HERE / "cases" / row["source_id"]
    row["seal_sha256"] = sha(case / "deploy_manifest.json")
    row["CPU_validation"] = json.loads((case / "audit/TARGET_CPU_VALIDATION.json").read_text())
(HERE / "HANDOFF.json").write_text(json.dumps(handoff, indent=2) + "\n")
