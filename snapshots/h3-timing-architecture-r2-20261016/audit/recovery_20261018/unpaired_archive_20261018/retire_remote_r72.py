from pathlib import Path
import os,json,signal,time
pid=531146
root=Path('/data3/researcher/h3_runs/timing_flexiact_prompt_pair_r72_20261018')
expected=['/data3/researcher/ComfyUI/.venv/bin/python','audit/consumer/watch_remote.py','--watch-hours','12']
def identity():
 p=Path('/proc')/str(pid)
 if not p.exists():return None
 return {'argv':p.joinpath('cmdline').read_bytes().rstrip(b'\0').decode().split('\0'),'start':p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],'uid':p.stat().st_uid,'cwd':str(p.joinpath('cwd').resolve())}
a=identity()
if a is not None:
 assert a['argv']==expected and a['start']=='6766328' and a['uid']==os.getuid() and a['cwd']==str(root),a
 children=Path(f'/proc/{pid}/task/{pid}/children').read_text().strip();assert not children,children
 assert identity()==a
 os.kill(pid,signal.SIGTERM)
 deadline=time.monotonic()+10
 while identity()==a and time.monotonic()<deadline:time.sleep(.1)
 assert identity()!=a
r={'pid':pid,'before':a,'original_process_absent':identity()!=a if a else True,'current_identity':identity(),'scope':'R72 CPU observer waiting for held pending P1','GPU_calls':0,'unix':time.time()}
(root/'audit/task_scope_review_hold_20261018/CPU_REMOTE_WATCHER_RETIRED.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
