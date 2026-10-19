import argparse,fcntl,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from observer_import import t
p=argparse.ArgumentParser();p.add_argument('mode');p.add_argument('--parent',required=True);p.add_argument('--root',required=True);p.add_argument('--timeout',type=float,default=60);p.add_argument('--lock');a=p.parse_args()
t.install_lifetime_guard(json.loads(a.parent));r=Path(a.root)
if a.mode=='controller':
 own=t.identity(os.getpid());t.write_new(r/'controller_ready.json',own)
 args=[sys.executable,__file__,'stage','--parent',json.dumps(own),'--root',str(r)]
 if a.lock:args+=['--lock',a.lock]
 t.run_child(args,dict(os.environ,CUDA_VISIBLE_DEVICES=''),r,'stage',a.timeout,own)
else:
 t.write_new(r/'stage_ready.json',t.identity(os.getpid()))
 if a.lock:
  with open(a.lock,'a') as f:
   fcntl.flock(f,fcntl.LOCK_EX);time.sleep(60)
 else:time.sleep(60)
