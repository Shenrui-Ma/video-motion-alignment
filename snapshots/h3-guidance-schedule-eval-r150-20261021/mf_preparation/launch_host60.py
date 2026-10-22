"""Launch one reviewed batch after the existing fresh admission; never retry."""
import argparse
import json
import subprocess
from pathlib import Path

from deploy_host60_cpu import ROOT, HOST, PYTHON, BASE, sha, save, remote


def launch(key, attempt):
    assert Path(key).name == key and attempt.replace("_", "").isalnum()
    package = ROOT / "host60_batches" / key
    review = json.loads((package / "ROOT_REVIEW.json").read_text())
    cpu = json.loads((package / "audit/TARGET_CPU_VERIFIED.json").read_text())
    digest = sha(package / "SEAL.json")
    assert review["passed"] and review["GPU_execution_authorized"]
    assert review["seal_sha256"] == cpu["seal"]["sha256"] == digest and cpu["passed"]
    target = BASE + "/" + key
    subprocess.run(["rsync", "-a", "-e", "ssh -o ProxyCommand=none -o BatchMode=yes",
                    str(package / "ROOT_REVIEW.json"), HOST + ":" + target + "/"], check=True)
    code = """
import os,sys,json,subprocess,time
from pathlib import Path
task_root=Path(TARGET)
task_attempt=ATTEMPT
os.environ['PATH']='/home/researcher/es/bin:'+os.environ.get('PATH','')
os.chdir(task_root);sys.path.insert(0,str(task_root/'scripts'))
from common import read,sha,save,verify_seal,resource_check,identity
verify_seal()
review=read(task_root/'ROOT_REVIEW.json')
assert sha(task_root/'SEAL.json')==DIGEST==review['seal_sha256']
assert review['passed'] and review['GPU_execution_authorized']
gpu=read(task_root/'configs/RUNTIME.json')['gpu_uuid']
assert gpu==review['gpu']
assert not(task_root/'audit'/task_attempt).exists()
launch_file=task_root/'audit'/(task_attempt+'_LAUNCH.json')
assert not launch_file.exists()
os.environ['CUDA_VISIBLE_DEVICES']=gpu
fresh=resource_check(gpu)
command=[PYTHON,str(task_root/'scripts/run_batch.py'),'--attempt',task_attempt,
         '--gpu',gpu,'--review',str(task_root/'ROOT_REVIEW.json')]
with(task_root/'audit'/(task_attempt+'.log')).open('xb')as log:
 child=subprocess.Popen(command,cwd=task_root,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),
                        stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 ident=identity(child.pid)
 assert ident is not None and child.poll() is None
 row={'identity':ident,'launch_unix':time.time(),'fresh_resource':fresh,
      'command':command,'producer_jobs_untouched':True}
 save(launch_file,row)
 print(json.dumps(row))
"""
    prefix = ("TARGET=" + repr(target) + "\nATTEMPT=" + repr(attempt) +
              "\nDIGEST=" + repr(digest) + "\nPYTHON=" + repr(PYTHON) + "\n")
    row = json.loads(remote(prefix + code))
    save(package / "audit/LOCAL_LAUNCH.json", row)
    print(json.dumps({"key": key, "attempt": attempt, "identity": row["identity"],
                      "free_mib": row["fresh_resource"]["memory_free_mib"],
                      "launch_unix": row["launch_unix"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", required=True)
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    launch(args.key, args.attempt)
