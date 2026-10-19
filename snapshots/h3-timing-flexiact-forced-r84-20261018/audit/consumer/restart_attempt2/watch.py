"""CPU-only consumer of root's exact restarted one-leg completion and release receipts."""
import argparse,hashlib,json,os,shlex,subprocess,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE));import consume
SOURCE='one_leg__movie_man_9';RUN='r84_'+SOURCE+'_seed2026101701_forced'
ATTEMPT='root_one_leg_restart_v2_attempt1'
REMOTE=str(consume.REMOTE)
SSH=['ssh','-S','/tmp/h3-codex-41-recovery-20261018.sock','-o','BatchMode=yes','-o','ConnectTimeout=30','H3_SERVER_B']
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'


def save(name,value):
    path=HERE/name;tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)


def observe():
    code="""from pathlib import Path
import json,hashlib
r=Path(REMOTE);a=r/'audit'/ATTEMPT
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
start=a/'STARTED.json'
if not start.exists():print(json.dumps({'phase':'WAIT_START'}))
else:
 packet={'phase':'WAIT_COMPLETE','start':read(start),'start_sha256':sha(start)}
 current=r/'processes/service.json'
 if current.exists():packet['current_owner']=read(current)
 failure=a/'FAILURE.json';done=a/'COMPLETE_REVIEW_HOLD.json'
 if failure.exists():packet.update(phase='ROOT_FAILURE',failure=read(failure))
 elif done.exists():
  gate=r/'analysis/postrun'/SOURCE/'PAIR_RUNTIME_GATE.json';release=a/'ROOT_EXIT_RECEIPT.json'
  packet.update(phase='COMPLETE',complete=read(done),release=read(release),gate=read(gate),gate_sha256=sha(gate))
 else:
  p=r/'audit/x0'/RUN/'manifest.json'
  if p.exists():
   m=read(p);packet['saved_progress']={'callback_count':m.get('callback_count'),'status':m.get('status')}
 print(json.dumps(packet))
""".replace('Path(REMOTE)','Path('+repr(REMOTE)+')').replace("/'audit'/ATTEMPT","/'audit'/"+repr(ATTEMPT)).replace('/SOURCE/', '/'+repr(SOURCE)+'/').replace('/RUN/', '/'+repr(RUN)+'/')
    raw=subprocess.check_output(SSH+['python3 -u -c '+shlex.quote(code)],stderr=subprocess.STDOUT,timeout=150)
    return json.loads(raw.decode().strip().splitlines()[-1])


def validate(packet,expected_start=None):
    if packet['phase']=='WAIT_START':return None
    start=packet['start'];owner=start['owner']
    consume.require(start['run_id']==RUN and start.get('single_service_trial') is True,'root start differs')
    consume.require(type(owner['pid']) is int and owner.get('identity') and owner['gpu_uuid']=='GPU-REDACTED' and owner['port']==8548,'actual service binding differs')
    if expected_start is not None:consume.require(packet['start_sha256']==expected_start,'root start replaced')
    consume.require(packet.get('current_owner')==owner,'registered service generation changed')
    if packet['phase']=='ROOT_FAILURE':raise RuntimeError('root attempt failed: '+repr(packet['failure']))
    if packet['phase']=='COMPLETE':
        done,release=packet['complete'],packet['release']
        consume.require(done['passed'] is True and done['run_id']==RUN and done['GPU_released'] is True and done['fitness_submitted'] is False,'root completion differs')
        consume.require(release['passed'] is True and release['owner']==owner and release['process_absent'] is True and release['CUDA_allocation_absent'] is True,'exact release receipt differs')
        consume.require(done['pair_gate_sha256']==packet['gate_sha256'],'completion/gate SHA differs')
        consume.checked_gate(packet['gate'],SOURCE)
    return packet['start_sha256']


def main():
    p=argparse.ArgumentParser();p.add_argument('--start-confirmed',action='store_true',required=True);a=p.parse_args()
    first=observe();binding=validate(first);consume.require(binding is not None,'actual root STARTED required')
    save('WATCH_STARTED.json',{'pid':os.getpid(),'source':SOURCE,'root_attempt':ATTEMPT,'root_start_sha256':binding,'owner':first['start']['owner'],'CPU_only':True,'unix':time.time()})
    deadline=time.monotonic()+8*3600;packet=first
    while True:
        validate(packet,binding)
        save('WATCH_STATE.json',{'pid':os.getpid(),'phase':packet['phase'],'saved_progress':packet.get('saved_progress'),'unix':time.time(),'GPU_calls':0})
        if packet['phase']=='COMPLETE':
            save('ACTUAL_COMPLETION_PACKET.json',packet)
            consume.collect(SOURCE)
            actual=consume.HERE/'incoming'/SOURCE/'PAIR_RUNTIME_GATE.json'
            consume.require(consume.sha(actual)==packet['gate_sha256'],'collected gate changed')
            presentation=consume.render(SOURCE);delivery=consume.publish()
            save('COMPLETE.json',{'passed':True,'source':SOURCE,'presentation':presentation,'delivery':delivery,'GPU_calls':0,'unix':time.time()})
            return
        if time.monotonic()>=deadline:raise TimeoutError('eight-hour CPU observation budget expired')
        time.sleep(60)
        try:packet=observe()
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError,ConnectionError) as error:
            save('LATEST_TRANSPORT_UNKNOWN.json',{'error':repr(error),'unix':time.time(),'deadline_reset':False});continue

if __name__=='__main__':
    try:main()
    except BaseException as error:
        save('FAILURE.json',{'error':repr(error),'traceback':traceback.format_exc(),'unix':time.time(),'GPU_calls':0});raise
