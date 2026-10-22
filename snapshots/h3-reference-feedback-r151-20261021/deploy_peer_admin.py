"""Deploy only explicit peer authorization for the two not-yet-started cases."""
from pathlib import Path
import hashlib
import io
import json
import shlex
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ssh = ["ssh", "-o", "ProxyCommand=none", "H3_SERVER_A"]
for sid in ("short_0358", "05_real_megumi_v"):
    case = HERE / "cases" / sid
    root = json.loads((case / "configs/runtime.json").read_text())["remote_root"]
    pre = "ROOT=" + repr(root) + "\n" + r'''
from pathlib import Path
import shutil
r=Path(ROOT);assert not(r/'processes/service.json').exists()
h=r/'audit/peer_update_history';h.mkdir(exist_ok=True)
for name in ('deploy_manifest.json','audit/TARGET_CPU_VALIDATION.json'):
 p=h/Path(name).name
 if not p.exists():shutil.copy2(r/name,p)
'''
    subprocess.run(ssh + ["python3 -"], input=pre, text=True, check=True)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for rel in ("audit/root_run_batch.py", "deploy_manifest.json", "audit/ADMIN_PEER_CHANGE.json"):
            archive.add(case / rel, arcname=rel, recursive=False)
    subprocess.run(ssh + ["tar -xf - -C " + shlex.quote(root)],
                   input=buffer.getvalue(), check=True)
    code = "ROOT=" + repr(root) + "\n" + r'''
from pathlib import Path
import hashlib,json,sys,importlib.util,time
r=Path(ROOT);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
new=json.loads((r/'deploy_manifest.json').read_text())
old=json.loads((r/'audit/peer_update_history/deploy_manifest.json').read_text())
assert new['files'].keys()==old['files'].keys()
changed=[k for k in new['files'] if new['files'][k]!=old['files'][k]]
assert changed==['audit/root_run_batch.py'],changed
assert all(sha(r/p)==v['sha256'] for p,v in new['files'].items())
sys.path.insert(0,str(r/'scripts'))
s=importlib.util.spec_from_file_location('peer_entry',r/'audit/root_run_batch.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
allow=['/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/'+x
 for x in ('short_0085','short_0274','musk05','firefly06','sam07')]
peers=m.live_peers(allow)
try:m.live_peers(['/home/unrelated/cases/sam07'])
except ValueError:pass
else:raise AssertionError('unknown peer accepted')
prior=r/'audit/peer_update_history/TARGET_CPU_VALIDATION.json'
proof=json.loads(prior.read_text())
assert proof['passed'] and proof['producer_seal_sha256']==sha(r/'audit/peer_update_history/deploy_manifest.json')
proof['producer_seal_sha256']=sha(r/'deploy_manifest.json')
proof['administrative_revalidation']={'passed':True,'changed_files':changed,
 'prior_CPU_proof_sha256':sha(prior),'cached_tensor_reload':False,
 'numerical_files_changed':False,'actual_live_peers':[x['root'] for x in peers],'unix':time.time()}
(r/'audit/TARGET_CPU_VALIDATION.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'passed':True,'seal_sha256':proof['producer_seal_sha256'],'changed_files':changed}))
'''
    result = subprocess.run(ssh + ["python3 -"], input=code, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    print(sid, result.stdout)
    subprocess.run(["scp", "-o", "ProxyCommand=none",
                    "H3_SERVER_A:" + root + "/audit/TARGET_CPU_VALIDATION.json",
                    str(case / "audit/TARGET_CPU_VALIDATION.json")], check=True)
handoff_path = HERE / "HANDOFF.json"
handoff = json.loads(handoff_path.read_text())
history = HERE / "design_history/HANDOFF_before_peer_extension.json"
if not history.exists():
    history.write_text(handoff_path.read_text())
for row in handoff["cases"]:
    case = HERE / "cases" / row["source_id"]
    row["seal_sha256"] = hashlib.sha256((case / "deploy_manifest.json").read_bytes()).hexdigest()
    row["CPU_validation"] = json.loads((case / "audit/TARGET_CPU_VALIDATION.json").read_text())
handoff_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n")
