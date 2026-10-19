"""One root-authorized CPU view, remote shared lock, no GPU or daemon."""
import argparse,fcntl,os,sys,time,subprocess
from pathlib import Path
from contract import ROOT,REMOTE_ROOT,read,sha,require,save,item,authorize,video_pose_gate,validate_pose,online_pending,require_pruning_allows_pose

def main():
    p=argparse.ArgumentParser();p.add_argument('--item',required=True);p.add_argument('--view',choices=['flip','pad16'],required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print('Prepared CPU view; execution requires root allocation');return
    phase=f'pose:{a.item}:{a.view}';authorize(phase);require_pruning_allows_pose();require(str(ROOT)==REMOTE_ROOT,'Actual pose only on designated CPU host/root')
    require(not os.environ.get('CUDA_VISIBLE_DEVICES',''),'CUDA must be hidden')
    lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock');lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        if online_pending():raise SystemExit(75)
        e=item(a.item);video,pose,identity=video_pose_gate(e,remote=True)
        dest=ROOT/'results/views'/a.item/a.view;require(not dest.exists(),'Existing or partial phase: preserve and review before retry')
        dest.mkdir(parents=True);start=time.monotonic()
        command=[sys.executable,str(ROOT/'scripts/pose_probe_tta.py'),'--video',str(video),'--output-dir',str(dest/'raw'),'--threads','4','--stride','1','--r36-view',a.view]
        with (dest/'pose.log').open('x') as log:
            proc=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4'),timeout=240)
        require(proc.returncode==0,'Technical pose failure, not scientific UNKNOWN')
        raw_path=dest/'raw'/(video.stem+'.pose.json');raw=read(raw_path);validate_pose(raw)
        expected=e['identity_provenance'];prov=raw['provenance']
        require({k:v for k,v in prov.items() if k!='script_sha256'}=={k:v for k,v in expected.items() if k!='script_sha256'},'Pose code/models/runtime/selection changed')
        require(prov['script_sha256']==sha(ROOT/'scripts/pose_probe_tta.py'),'Actual adapter source SHA')
        require(raw['video']['sha256']==e['video_sha256'],'Transformed input video binding')
        from view_output import inverse_pose
        restored=inverse_pose(raw,identity,a.view);path=dest/'inverse.pose.json';save(path,restored)
        require(len(raw['r36_preprocess_checks'])==141,'All frame preprocessing recorded')
        differing=sum(x['identity_preprocessed_sha256']!=x['view_preprocessed_sha256'] for x in raw['r36_preprocess_checks'])
        require(differing>0,'View completely cancelled by preprocessing; diagnostic invalid')
        video_pose_gate(e,remote=True)
        files={str(q.relative_to(dest)):sha(q) for q in dest.rglob('*') if q.is_file()}
        save(dest/'COMPLETE.json',{'phase':phase,'status':'complete','input_video_sha256':e['video_sha256'],'identity_pose_sha256':e['identity_pose_sha256'],'freeze_sha256':sha(ROOT/'FREEZE.json'),'view':a.view,'files':files,'elapsed_seconds':time.monotonic()-start,'preprocessed_different_frames':differing,'frames':141,'GPU':False,'inverse_pose_sha256':sha(path)})
        print('Completed '+phase)

if __name__=='__main__':main()
