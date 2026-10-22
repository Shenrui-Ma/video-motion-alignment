"""One authorized CPU view; durable failure attempts and exact complete reuse."""
import argparse,fcntl,os,sys,time,subprocess,traceback
from pathlib import Path
from contract import ROOT,REMOTE_ROOT,read,sha,require,save,item,authorize,video_pose_gate,validate_pose,online_pending,verify_model_files
from phase_artifacts import identity,completed_or_recover,create_attempt


def main():
    p=argparse.ArgumentParser();p.add_argument('--item',required=True);p.add_argument('--view',choices=['flip','pad16'],required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print('Prepared CPU view; execution requires root allocation');return
    phase=f'pose:{a.item}:{a.view}';authorize(phase);require(str(ROOT)==REMOTE_ROOT,'Designated CPU root')
    require(not os.environ.get('CUDA_VISIBLE_DEVICES',''),'CUDA must be hidden')
    lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    with lock.open('a') as lf:
        try:fcntl.flock(lf,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        if online_pending():raise SystemExit(75)
        e=item(a.item);model_files=verify_model_files([e]);video,pose,raw_identity=video_pose_gate(e,remote=True)
        dest=ROOT/'results/views'/a.item/a.view
        complete=completed_or_recover(dest,e,a.view)
        if complete is not None:print('Reused verified complete '+phase);return
        attempt=create_attempt(dest);start=time.monotonic();child=None
        save(attempt/'RUNNING.json',{'phase':phase,'identity':identity(os.getpid()),'started_unix':time.time(),'previous_attempts_preserved':True})
        try:
            command=[sys.executable,str(ROOT/'scripts/pose_probe_tta.py'),'--video',str(video),'--output-dir',str(attempt/'raw'),'--threads','4','--stride','1','--r36-view',a.view]
            with (attempt/'pose.log').open('x') as log:
                # Child inherits the CPU lock: parent loss cannot allow a duplicate
                # pose worker while the original child is still alive.
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4'),pass_fds=(lf.fileno(),))
                save(attempt/'CHILD.json',{'identity':identity(child.pid),'command':command,'lock_inherited':True})
                try:code=child.wait(timeout=240)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait();raise
            save(attempt/'EXIT.json',{'returncode':code,'wall_seconds':time.monotonic()-start,'child_exited':True})
            require(code==0,'Technical pose failure, not scientific UNKNOWN')
            raw_path=attempt/'raw'/(video.stem+'.pose.json');raw=read(raw_path);validate_pose(raw)
            require(raw['r36_view']==a.view and raw['extraction']=={'start':0,'end':None,'stride':1},'Actual view/full extraction binding')
            expected=e['identity_provenance'];prov=raw['provenance']
            require({k:v for k,v in prov.items() if k!='script_sha256'}=={k:v for k,v in expected.items() if k!='script_sha256'},'Pose/model/runtime/selection changed')
            require(prov['script_sha256']==sha(ROOT/'scripts/pose_probe_tta.py') and raw['video']['sha256']==e['video_sha256'],'Adapter/video binding')
            from view_output import inverse_pose
            save(attempt/'inverse.pose.json',inverse_pose(raw,raw_identity,a.view))
            require(len(raw['r36_preprocess_checks'])==141,'All preprocessing frames')
            expected_shape=[736,1312,3] if a.view=='flip' else [768,1344,3]
            require(all(row['frame']==i and row['view']==a.view and row['view_rgb_shape']==expected_shape for i,row in enumerate(raw['r36_preprocess_checks'])),'Actual preprocessing view/frame/geometry')
            differing=sum(r['identity_preprocessed_sha256']!=r['view_preprocessed_sha256'] for r in raw['r36_preprocess_checks'])
            require(differing>0,'View fully cancelled by preprocessing')
            video_pose_gate(e,remote=True);require(verify_model_files([e])==model_files,'Model/code changed during pose')
            record={'status':'complete','phase':phase,'attempt':str(attempt.relative_to(dest)),
                    'freeze_sha256':sha(ROOT/'FREEZE.json'),'input_video_sha256':e['video_sha256'],'identity_pose_sha256':e['identity_pose_sha256'],
                    'view':a.view,'model_files':model_files,'files':{str(q.relative_to(attempt)):sha(q) for q in attempt.rglob('*') if q.is_file()},
                    'elapsed_seconds':time.monotonic()-start,'preprocessed_different_frames':differing,'frames':141,'GPU':False,'inverse_pose_sha256':sha(attempt/'inverse.pose.json')}
            save(attempt/'VALIDATED.json',record)
            completed_or_recover(dest,e,a.view);print('Completed '+phase)
        except BaseException as exc:
            if child is not None and child.poll() is None:
                child.kill();child.wait()
            failure={'phase':phase,'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),'elapsed_seconds':time.monotonic()-start,'child_exited':child is None or child.poll() is not None,'scientific_UNKNOWN':False,'retry':'separate attempt; root bounded phase call; no completed work repeated'}
            if not (attempt/'FAILURE.json').exists():save(attempt/'FAILURE.json',failure)
            raise


if __name__=='__main__':main()
