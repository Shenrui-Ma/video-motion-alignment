"""Sequential experiments, durable histories, warmup gate and final GPU release."""
import json
import subprocess
import time
import re
import job
import service

def state(**v):
    service.write_json(service.RUN/'logs/controller_state.json',dict(unix=time.time(),**v))

def run():
    deadline=time.monotonic()+8*3600
    completed=[]
    current=None
    idle=None
    try:
        while time.monotonic()<deadline:
            plan=json.loads((service.RUN/'configs/queue.json').read_text())
            names=plan['jobs']
            assert len(names)<=18 and len(names)==len(set(names))
            pending=[n for n in names if n not in completed]
            if not pending:
                if plan.get('sealed'):
                    state(status='all_queued_jobs_complete',completed=completed);return
                idle=idle or time.monotonic()
                if time.monotonic()-idle>300:
                    state(status='review_idle_timeout_releasing_gpu',completed=completed);return
                state(status='awaiting_review',completed=completed)
                time.sleep(15);continue
            idle=None
            current=pending[0]
            if not (service.RUN/'logs'/f'{current}_job.json').exists():job.submit(current)
            started=time.monotonic()
            while time.monotonic()<deadline:
                result=job.status(current)
                status=result['status']
                if isinstance(status,dict):status=status['status_str']
                stats=subprocess.run(['nvidia-smi','-i',service.GPU,'--query-gpu=memory.used,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20)
                with (service.RUN/'logs/resources.jsonl').open('a') as f:
                    f.write(json.dumps({'unix':time.time(),'job':current,'gpu':stats.stdout.strip()})+'\n')
                state(status=status,current=current,completed=completed)
                if status=='success':
                    completed.append(current)
                    if current.endswith('bench2'):
                        text=(service.RUN/'logs/comfyui.log').read_text(errors='replace')
                        values=[float(x) for x in re.findall(r'(\d+\.\d+)s/it',text)]
                        report={'job':current,'seconds_per_iteration_seen':values[-3:],'limit':100.0,'kind':'two-call timing only: first formal sigma then terminal jump to zero; no X0; not a quality sample'}
                        service.write_json(service.RUN/'audit/warmup_gate.json',report)
                        if not values or values[-1]>100:raise RuntimeError('warmup too slow or sampling timing missing; inspect before continuing')
                    current=None;break
                if status in ('error','unknown_missing','submission_uncertain'):raise RuntimeError(f'{current}: {status}')
                if time.monotonic()-started>3600:raise TimeoutError('one job exceeded hour')
                time.sleep(20)
            else:raise TimeoutError('batch deadline')
        raise TimeoutError('8-hour batch deadline')
    except BaseException as e:
        state(status='failed',current=current,completed=completed,error=repr(e));raise
    finally:service.stop()

if __name__=='__main__':run()
