"""Single-GPU metrics queue: subprocess isolation, atomic state, retry and resume."""
import argparse, fcntl, json, os, signal, subprocess, sys, time
from pathlib import Path
from metric_worker import METRICS, atomic, applicability

def main(a):
    root=Path(a.root).resolve();root.mkdir(parents=True,exist_ok=True)
    lock=open(root/'worker.lock','a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return
    metrics=a.metrics or list(METRICS)
    while True:
        jobs=json.loads(Path(a.manifest).read_text())['jobs'];attempted=0;pending=0
        for job in jobs:
            for metric in metrics:
                folder=root/'results'/job['id'];target=folder/(metric+'.json');state=root/'states'/(job['id']+'__'+metric+'.json')
                if target.exists() and json.loads(target.read_text()).get('status') in ['done','not_applicable']:continue
                old=json.loads(state.read_text()) if state.exists() else {'attempts':0}
                if old.get('attempts',0)>=a.retries:continue
                reason=applicability(metric,job['metadata'])
                if reason:
                    atomic(target,{**{k:job[k] for k in ['task_id','dataset','method']},'job_id':job['id'],'cohort':job.get('cohort','main'),'metric':metric,'status':'not_applicable','score':None,'reason':reason});continue
                if not Path(job['metadata_file']).exists() or not Path(job['target_frames_parent'],Path(job['metadata']['src_video_name']).stem).exists():pending+=1;continue
                if old.get('retry_after',0)>time.time():pending+=1;continue
                # Admission happens immediately before each CUDA child, preserving other users' work.
                if a.gpu:
                    free=int(subprocess.check_output(['nvidia-smi','-i',a.gpu,'--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())
                    if free<a.min_free_mib:pending+=1;continue
                folder.mkdir(parents=True,exist_ok=True);jf=folder/'job.json';atomic(jf,job)
                cmd=[sys.executable,str(Path(__file__).with_name('metric_worker.py')),'--job',str(jf),'--metric',metric,'--official',a.official,'--model-paths',a.model_paths,'--result',str(target),'--device',a.device]
                old.update(attempts=old.get('attempts',0)+1,status='running',started=time.time());atomic(state,old)
                env=dict(os.environ,OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
                for k in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:env.pop(k,None)
                if a.gpu:env['CUDA_VISIBLE_DEVICES']=a.gpu
                with open(folder/(metric+'.log'),'a') as log:
                    proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
                    try:rc=proc.wait(timeout=a.timeout)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGTERM)
                        try:proc.wait(timeout=15)
                        except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                        rc=124
                old.update(status='done' if rc==0 else 'retry',exit_code=rc,finished=time.time(),retry_after=time.time()+a.backoff);atomic(state,old);attempted+=1
                atomic(root/'heartbeat.json',{'time':time.time(),'last_job':job['id'],'last_metric':metric,'exit_code':rc})
        if a.once or (not pending and attempted==0):break
        time.sleep(a.poll)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--manifest',required=True);p.add_argument('--official',required=True);p.add_argument('--model-paths',required=True);p.add_argument('--metrics',nargs='+',choices=METRICS);p.add_argument('--gpu');p.add_argument('--device',default='cuda');p.add_argument('--min-free-mib',type=int,default=12000);p.add_argument('--retries',type=int,default=3);p.add_argument('--timeout',type=int,default=3600);p.add_argument('--backoff',type=int,default=120);p.add_argument('--poll',type=int,default=60);p.add_argument('--once',action='store_true');main(p.parse_args())
