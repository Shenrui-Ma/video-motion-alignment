"""CPU-only gate, collection, crops and rendering after root's actual STARTED receipt."""
import argparse,os,subprocess,sys,time,traceback
from common import *
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'

def started_receipt(producer,path):
    producer=Path(producer).resolve();path=Path(path).resolve()
    require(path.is_relative_to(producer/'audit') and path.name=='STARTED.json','root STARTED receipt required')
    value=read(path);owner=read(producer/'processes/service.json');runtime=read(producer/'configs/runtime.json')
    require(value['owner']==owner and owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'],'root service receipt binding differs')
    require(isinstance(owner['pid'],int) and owner.get('identity') and value.get('controller'),'root service/controller actual binding missing')
    return bound(path)

def generation_status(producer,source):
    rows={}
    for method in METHODS:
        path=producer/'logs'/(run_id(source,method)+'_job.json')
        if path.exists():
            job=read(path);rows[method]={'status':job['status'],'job':bound(path)}
        else:rows[method]={'status':'PENDING'}
    failed=any(row['status'] in ('error','failed','submission_uncertain','unknown_missing','cancelled') for row in rows.values())
    complete=all(row['status']=='success' for row in rows.values())
    return {'source':source,'generation':'GENERATION_FAILED' if failed else 'COMPLETE' if complete else 'RUNNING_OR_PENDING','runs':rows}

def locked(fn,seconds=600):
    end=time.monotonic()+seconds
    while True:
        try:
            with cpu_lock():return fn()
        except BlockingIOError:
            if time.monotonic()>end:raise TimeoutError('CPU consumer lock remained busy')
            time.sleep(5)

def process(producer,source,ffmpeg,ffprobe,font,attempt):
    from collect_pair import collect,validate_gate,validate_intake
    from prepare_sources import prepare as source_prepare
    from prepare_pair import prepare as pair_prepare
    from render_pair import render,choose_font
    gate=producer/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json'
    logs=ROOT/'audit/watcher'/attempt;logs.mkdir(parents=True,exist_ok=True)
    def actual_intake():
        if not gate.exists():
            with (logs/(source+'_verify.log')).open('x') as f:
                subprocess.run([sys.executable,str(producer/'analysis/postrun/verify_pair.py'),'--source',source],cwd=producer,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
        validate_gate(read(gate),source);collect(producer,source)
    locked(actual_intake)
    ready=ROOT/'prepared'/source/'READY.json'
    if not ready.exists():
        def prepare():
            if not (ROOT/'prepared'/source/'SOURCE_INPUTS.json').exists():source_prepare(source,ffmpeg,ffprobe)
            pair_prepare(source,ffmpeg,ffprobe)
        locked(prepare)
    require(read(ready)['passed'] is True,'pair preparation has not passed')
    if not (ROOT/'showcase'/source/'PRESENTATION.json').exists():locked(lambda:render(source,ffmpeg,ffprobe,choose_font(font)))
    actual=validate_intake(ROOT/'incoming'/source,source)
    efficiency={'source':source,'fixed_denominator':7,'gate':bound(gate),'methods':{m:{key:actual['runs'][m][key] for key in ('run_id','NFE','Euler_updates','routed_blocks','job_wall_seconds','capture_seconds')} for m in METHODS},'scope':'Whole-job observed elapsed includes loading/conditioning/sampling/snapshots/decoding and polling; not steady denoising time or measured peak VRAM.'}
    efficiency_path=ROOT/'results'/source/'EFFICIENCY.json'
    if not efficiency_path.exists():save(efficiency_path,efficiency)
    return {'source':source,'status':'PRESENTATION_READY','pair_gate':bound(gate),'ready':bound(ready),'presentation':bound(ROOT/'showcase'/source/'PRESENTATION.json'),'official_MF':'PENDING_ROOT_GPU_SCHEDULING','unix':time.time()}

def main(a):
    verify_runtime();producer=Path(a.producer_root).resolve()
    require(a.start_confirmed,'explicit root launch confirmation required')
    receipt=started_receipt(producer,a.root_started_receipt)
    require(Path(a.attempt).name==a.attempt,'plain attempt name required')
    attempt=ROOT/'audit/watcher'/a.attempt;attempt.mkdir(parents=True,exist_ok=False)
    save(attempt/'STARTED.json',{'pid':os.getpid(),'root_actual_start':receipt,'consumer_freeze':bound(ROOT/'CONSUMER_FREEZE.json'),'CUDA_VISIBLE_DEVICES':'','gpu_calls':0,'unix':time.time()})
    end=time.monotonic()+a.hours*3600;done=set()
    with (ROOT/'audit/WATCHER.lock').open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while time.monotonic()<end:
            for source in PAIRS:
                if source in done:continue
                state=generation_status(producer,source)
                if state['generation']=='GENERATION_FAILED':
                    state.update(status='GENERATION_FAILED',unix=time.time());save(attempt/(source+'_GENERATION_FAILURE.json'),state);replace(ROOT/'results'/source/'STATUS.json',state);done.add(source)
                elif state['generation']=='COMPLETE':
                    try:result=process(producer,source,a.ffmpeg,a.ffprobe,a.font,a.attempt)
                    except Exception as error:
                        result={'source':source,'status':'CONSUMER_FAILED','error':repr(error),'traceback':traceback.format_exc(),'unix':time.time()};save(attempt/(source+'_CONSUMER_FAILURE.json'),result)
                    replace(ROOT/'results'/source/'STATUS.json',result);done.add(source);print(json.dumps(result),flush=True)
                else:
                    state.update(status=state['generation'],unix=time.time());replace(ROOT/'results'/source/'STATUS.json',state)
            replace(attempt/'PROGRESS.json',{'fixed_denominator':7,'terminal_sources':list(s for s in PAIRS if s in done),'unix':time.time(),'gpu_calls':0})
            if len(done)==len(PAIRS):break
            time.sleep(a.interval)
    save(attempt/'FINISHED.json',{'fixed_denominator':7,'terminal_count':len(done),'timed_out':len(done)<7,'gpu_calls':0,'unix':time.time()})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--producer-root',required=True);p.add_argument('--root-started-receipt',required=True);p.add_argument('--start-confirmed',action='store_true');p.add_argument('--attempt',required=True);p.add_argument('--hours',type=float,default=18);p.add_argument('--interval',type=float,default=45);p.add_argument('--ffmpeg',default='/usr/bin/ffmpeg');p.add_argument('--ffprobe',default='/usr/bin/ffprobe');p.add_argument('--font');main(p.parse_args())
