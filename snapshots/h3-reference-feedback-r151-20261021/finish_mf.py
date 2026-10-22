"""Run the authorized six new official MF trackers only after all R151 releases."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tarfile
import time

HERE = Path(__file__).resolve().parent
MF = HERE / "mf"
CASES = ("short_0252", "short_0358", "05_real_megumi_v")
ATTEMPT = "actual_r151_mf_attempt1"
SSH = ["ssh", "-o", "ProxyCommand=none", "-o", "BatchMode=yes", "H3_SERVER_A"]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())


def remote(code):
    result = subprocess.run(SSH + ["python3 -"], input=code, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stdout[-3000:] + result.stderr[-3000:])
    return result.stdout


def main():
    assert read(HERE / "INFERENCE_DRIVER_COMPLETE.json")["passed"]
    assert not (HERE / "STOP_BEFORE_MF").exists()
    for sid in CASES:
        subprocess.run([sys.executable, str(HERE / "prepare_mf.py"), "--case", sid], check=True)
    subprocess.run([sys.executable, str(HERE / "prepare_mf.py"), "--seal"], check=True)
    runtime = read(MF / "configs/RUNTIME.json")
    root = runtime["remote_root"]
    reuse = {}
    for sid in CASES:
        producer = HERE / "cases" / sid
        rt = read(producer / "configs/runtime.json")
        recipe = read(producer / "configs/scientific_contract.json")
        reuse[f"cases/{sid}/source_full.mp4"] = rt["remote_root"] + "/inputs/" + recipe["cases"][0]["video"]
        for row in recipe["cases"]:
            gate = read(producer / "analysis/postrun" / sid / (row["run_id"] + "_GATE.json"))
            reuse[f"cases/{sid}/{row['arm']}/full.mp4"] = gate["video"]["file"]
    # Model and numerical runtime are reused in place, never downloaded.
    runtime_source = "/home/researcher/h3_runs/ive_caption_scrubs_mf_host9_20261020/runtime/ive"
    manifest = read(MF / "SEAL.json")
    upload = [x for x in manifest["files"] if x not in reuse] + ["SEAL.json"]
    archive = HERE / "mf_package.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in upload:
            tar.add(MF / rel, arcname=rel, recursive=False)
    with archive.open("rb") as stream:
        subprocess.run(SSH + ["umask 077; mkdir -p " + shlex.quote(root) +
                              "; tar -xzf - -C " + shlex.quote(root)],
                       stdin=stream, check=True)
    code = "ROOT=" + repr(root) + "\nRUNTIME=" + repr(runtime) + "\nREUSE=" + repr(reuse) + \
           "\nRUNTIME_SOURCE=" + repr(runtime_source) + "\n" + r'''
from pathlib import Path
import os,json,hashlib,errno,shutil,subprocess
r=Path(ROOT);seal=json.loads((r/'SEAL.json').read_text())
for rel,source in REUSE.items():
 p=r/rel;p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():
  try:os.link(source,p)
  except OSError as e:
   if e.errno!=errno.EXDEV:raise
   shutil.copyfile(source,p)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==seal['files'][rel],rel
p=r/'runtime/ive';p.parent.mkdir(exist_ok=True)
if not p.exists():p.symlink_to(RUNTIME_SOURCE,target_is_directory=True)
assert p.resolve()==Path(RUNTIME_SOURCE).resolve()
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
c=subprocess.run([RUNTIME['python'],str(r/'scripts/cpu_verify.py')],cwd=r,env=env,capture_output=True,text=True)
(r/'audit/TARGET_CPU_VERIFIED.log').write_text(c.stdout+c.stderr)
assert c.returncode==0,c.stdout+c.stderr
(r/'audit/TARGET_CPU_VERIFIED.json').write_text(c.stdout)
print(c.stdout)
'''
    print(remote(code), flush=True)
    # The existing launcher performs another exact resource check before each
    # tracker. This review binds all actual producer releases and current seal.
    last = HERE / "cases/05_real_megumi_v"
    last_runtime = read(last / "configs/runtime.json")
    last_attempt = next((last / "actual").glob("root_r151*"))
    prerequisite = last_runtime["remote_root"] + "/audit/" + last_attempt.name + "/ROOT_EXIT_RECEIPT.json"
    review = {"passed": True, "GPU_execution_authorized": True,
              "reviewed_by": "sage_adapter_prepare_v2 under root R151 six-target MF authorization",
              "seal_sha256": sha(MF / "SEAL.json"), "gpu": runtime["gpu_uuid"],
              "prerequisite_release": {"file": prerequisite,
                                       "sha256": sha(last_attempt / "ROOT_EXIT_RECEIPT.json")},
              "producer_releases_sha256": sha(MF / "configs/PRODUCER_RELEASES.json"),
              "new_trackers": 6, "new_source_trackers": 0,
              "official_numerics_unchanged": True, "unix": time.time()}
    (MF / "ROOT_REVIEW.json").write_text(json.dumps(review, indent=2) + "\n")
    subprocess.run(["scp", "-o", "ProxyCommand=none", str(MF / "ROOT_REVIEW.json"),
                    "H3_SERVER_A:" + root + "/ROOT_REVIEW.json"], check=True)
    code = "ROOT=" + repr(root) + "\nRUNTIME=" + repr(runtime) + "\nATTEMPT=" + repr(ATTEMPT) + "\n" + r'''
from pathlib import Path
import subprocess,os,json,time
r=Path(ROOT)
env=dict(os.environ,CUDA_VISIBLE_DEVICES=RUNTIME['gpu_uuid'],PYTHONDONTWRITEBYTECODE='1')
probe=subprocess.run([RUNTIME['python'],'-c',
 "import sys;sys.path.insert(0,'scripts');from common import *;print(resource_check(read(ROOT/'configs/RUNTIME.json')['gpu_uuid']))"],
 cwd=r,env=env,capture_output=True,text=True)
(r/'audit/FRESH_ADMISSION.log').write_text(probe.stdout+probe.stderr)
assert probe.returncode==0,probe.stdout+probe.stderr
command=[RUNTIME['python'],str(r/'scripts/run_batch.py'),'--attempt',ATTEMPT,'--gpu',RUNTIME['gpu_uuid'],'--review',str(r/'ROOT_REVIEW.json')]
with(r/'audit'/('WRAPPER_'+ATTEMPT+'.log')).open('xb',buffering=0)as log:
 c=subprocess.Popen(command,cwd=r,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
import sys;sys.path.insert(0,str(r/'scripts'));import process_identity
owner=process_identity.bind_or_reap(c,command)
record={'pid':c.pid,'identity':process_identity.hashed_record(owner),'command':command,'unix':time.time()}
(r/'audit/MF_LAUNCH.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
'''
    launch = remote(code)
    (MF / "audit/MF_LAUNCH.json").write_text(launch)
    print("MF_LAUNCHED", launch, flush=True)


if __name__ == "__main__":
    main()
