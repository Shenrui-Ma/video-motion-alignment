"""Pull only CPU results/media and embed a portable report. No tensor downloads or GPU calls."""
import argparse,subprocess,time
from common import *
from collect_pair import validate_intake
from make_showcase import build

def sync_once(output):
    paths=read(ROOT/'configs/paths.json');host=paths['ssh_alias'];remote=paths['remote_consumer']
    for folder in ('incoming','showcase','results'):
        dest=ROOT/folder;dest.mkdir(exist_ok=True)
        cmd=['rsync','-az','--exclude=*.pt','--exclude=*.npz','--exclude=.*']
        if folder!='results':cmd+=['--ignore-existing']
        cmd+=['-e','ssh -o BatchMode=yes -o ConnectTimeout=15',host+':'+remote+'/'+folder+'/',str(dest)+'/']
        subprocess.run(cmd,check=True,timeout=180)
    ready=[]
    for source in PAIRS:
        if (ROOT/'incoming'/source/'COLLECTION.json').exists():validate_intake(ROOT/'incoming'/source,source)
        p=ROOT/'showcase'/source/'PRESENTATION.json'
        if p.exists():
            row=read(p)
            for item in row['videos']:
                require(sha(p.parent/(item['name']+'.mp4'))==item['video']['sha256'],'presentation video changed')
            require(sha(p.parent/'six_times.png')==row['figure']['sha256'],'presentation figure changed');ready.append(source)
    result=build(output);result.update(ready_sources=ready,unix=time.time(),gpu_calls=0)
    replace(ROOT/'audit/LATEST_MEDIA_SYNC.json',result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--watch',action='store_true');p.add_argument('--start-confirmed',action='store_true');p.add_argument('--hours',type=float,default=18);a=p.parse_args()
    require(not a.watch or a.start_confirmed,'root launch confirmation required before watcher')
    verify_runtime(inputs=False)
    end=time.monotonic()+a.hours*3600
    with (ROOT/'audit/LOCAL_SYNC.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while True:
            try:
                result=sync_once(a.output);print(json.dumps(result),flush=True)
                if len(result['ready_sources'])==7:break
            except Exception as e:
                replace(ROOT/'audit/LATEST_SYNC_ERROR.json',{'error':repr(e),'unix':time.time()});print(repr(e),flush=True)
                if not a.watch:raise
            if not a.watch or time.monotonic()>=end:break
            time.sleep(60)
