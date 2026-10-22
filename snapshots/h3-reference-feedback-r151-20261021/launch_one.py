"""Delegated root-authorized launch after exact target CPU and fresh admission."""
from pathlib import Path
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sid, attempt = sys.argv[1:3]
peer = sys.argv[3] if len(sys.argv) > 3 else None
case = HERE / "cases" / sid
runtime = json.loads((case / "configs/runtime.json").read_text())
script = "ROOT=" + repr(runtime["remote_root"]) + "\nPEER=" + repr(peer) + "\nATTEMPT=" + repr(attempt) + "\n" + r'''
from pathlib import Path
import sys,os,json,subprocess,time,hashlib
root=Path(ROOT);sys.path.insert(0,str(root/'scripts'));import service,cgroup_memory
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cpu=json.loads((root/'audit/TARGET_CPU_VALIDATION.json').read_text())
assert cpu['passed'] and cpu['producer_seal_sha256']==sha(root/'deploy_manifest.json')
assert not (root/'processes/service.json').exists()
owner=None
if PEER:
 owner=json.loads((Path(PEER)/'processes/service.json').read_text())
 assert service.current_identity(owner['pid'])==owner['identity']
 assert owner['gpu_uuid']!=service.GPU
stats=subprocess.check_output(['nvidia-smi','-i',service.GPU,'--query-gpu=uuid,memory.free,temperature.gpu,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip().split(', ')
assert stats[0]==service.GPU and int(stats[1])>=service.RUNTIME['minimum_free_mib'] and int(stats[2])<90
memory=cgroup_memory.check();assert memory['admitted']
rows=service.compute_processes()
mine=[x for x in rows if (service.current_identity(x['pid']) or {}).get('uid')==os.getuid()]
assert all(owner and x['pid']==owner['pid'] and x['gpu_uuid']==owner['gpu_uuid'] for x in mine),mine
review={'approved':True,'reviewed_by':'sage_adapter_prepare_v2 under root explicit R151 execution authorization',
 'producer_seal_sha256':sha(root/'deploy_manifest.json'),'predecessor_release_verified':True,
 'predecessor_release_evidence':{'fresh_own_compute':mine,'GPU3_own_compute':[],
  'scope':'earlier owned GPU3 service absent; exact current R150 peer preserved'},
 'peer_owner':owner,'GPU3':stats,'memory':memory,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'CPU_VALIDATION_sha256':sha(root/'audit/TARGET_CPU_VALIDATION.json'),
 'CPU_TESTS_sha256':sha(root/'audit/TARGET_CPU_TESTS.log'),'unix':time.time()}
service.write_json(root/'audit/ROOT_PRELAUNCH_REVIEW.json',review)
command=['python3','-u',str(root/'audit/root_run_batch.py'),'--execute','--attempt',ATTEMPT]
if PEER:command+=['--peer-root',PEER]
with (root/'audit/ROOT_WRAPPER.log').open('xb',buffering=0) as log:
 child=subprocess.Popen(command,cwd=root,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),
  stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
record={'pid':child.pid,'identity':service.bind_child(child,command),'command':command,
 'review_sha256':sha(root/'audit/ROOT_PRELAUNCH_REVIEW.json'),
 'seal_sha256':sha(root/'deploy_manifest.json'),'unix':time.time()}
service.write_json(root/'audit/LAUNCH.json',record);print(json.dumps(record))
'''
result = subprocess.run(["ssh", "-o", "ProxyCommand=none", "H3_SERVER_A", "python3 -"],
                        input=script, text=True, capture_output=True)
(case / "audit" / ("LAUNCH_COMMAND_" + attempt + ".log")).write_text(result.stdout + result.stderr)
print(result.stdout)
if result.returncode:
    print(result.stderr[-2500:])
    raise SystemExit(result.returncode)
(case / "audit/LAUNCH.json").write_text(result.stdout.strip() + "\n")
