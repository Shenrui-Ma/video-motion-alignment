"""CPU-only conditional equality check, not a second inference."""
from pathlib import Path
import fcntl,hashlib,json,os,time
ROOT=Path('/data5/researcher/h3_runs/timing_pose_feedback_r19_20261016')
PARENT=Path('/data5/researcher/h3_runs/timing_fixed_stop_r18_20261016')
RUN='r19_s05_pose_observer';OLD='r18_s05_full_6to11'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    os.environ['CUDA_VISIBLE_DEVICES']=''
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='4'
    out=ROOT/'analysis/pose/replication'
    gate=json.loads((out/(RUN+'_integrity.json')).read_text());assert gate['passed']
    result={'run_id':RUN,'parent_run':OLD,'observed_mask':gate['active_indices'],'comparison':'same-mask replay check, no new inference','applicable':gate['same_fixed_mask_as_R18']}
    path=out/'same_mask_R18_replay.json'
    if not result['applicable']:
        result['reason']='Different actual mask; exact replay is not expected. Preserve final pose/common-support comparison.'
        path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return
    with Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        import torch,cv2
        torch.set_num_threads(4);cv2.setNumThreads(1)
        started=time.time();rows=[]
        for filename in [f'x0_step{i:03d}.pt' for i in [5,6,7,8,9,10,11,12,15,19]]+['sampler_final.pt']:
            ap=ROOT/'audit/x0'/RUN/filename;bp=PARENT/'audit/x0'/OLD/filename
            a=torch.load(ap,map_location='cpu',weights_only=True);b=torch.load(bp,map_location='cpu',weights_only=True)
            rows.append({'file':filename,'actual_file_sha256':sha(ap),'parent_file_sha256':sha(bp),
                         'video_exact':torch.equal(a['video'],b['video']),'audio_exact':torch.equal(a['audio'],b['audio'])})
        videos=[]
        for root,run in [(ROOT,RUN),(PARENT,OLD)]:
            history=json.loads((root/'logs'/f'{run}_history.json').read_text());assert history['status']['completed'] and history['status']['status_str']=='success'
            items=[v for k,node in history['prompt'][2].items() if node['class_type']=='SaveVideo' for v in history['outputs'].get(k,{}).get('images',[]) if v.get('type')=='output' and v.get('filename','').endswith('.mp4')]
            assert len(items)==1
            v=root/'output'/items[0].get('subfolder','')/items[0]['filename'];assert v.resolve().is_relative_to((root/'output').resolve())
            videos.append(v)
        captures=[cv2.VideoCapture(str(p)) for p in videos]
        metadata=[{'fps':c.get(cv2.CAP_PROP_FPS),'frames':int(c.get(cv2.CAP_PROP_FRAME_COUNT)),'width':int(c.get(cv2.CAP_PROP_FRAME_WIDTH)),'height':int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))} for c in captures]
        rgb=[]
        while True:
            aa,bb=[c.read() for c in captures]
            if not aa[0] and not bb[0]:break
            assert aa[0] and bb[0],'Frame counts differ'
            hs=[hashlib.sha256(cv2.cvtColor(x[1],cv2.COLOR_BGR2RGB).tobytes()).hexdigest() for x in [aa,bb]]
            rgb.append({'frame':len(rgb),'actual_sha256':hs[0],'parent_sha256':hs[1],'equal':hs[0]==hs[1]})
        for c in captures:c.release()
        assert len(rgb)==141 and all(m=={'fps':24.,'frames':141,'width':1312,'height':736} for m in metadata)
        result.update(tensors=rows,all_AV_tensors_exact=all(r['video_exact'] and r['audio_exact'] for r in rows),decoded_RGB=rgb,
                      decoded_RGB_equal_frames=sum(r['equal'] for r in rgb),decoded_RGB_all_exact=all(r['equal'] for r in rgb),geometry=metadata,
                      source_videos=[{'path':str(p),'sha256':sha(p)} for p in videos],cpu_seconds=time.time()-started,no_GPU_initialized=not torch.cuda.is_initialized(),
                      interpretation='If exact, the online interface reproduces R18 on this selected case; no adaptive superiority demonstrated. Any mismatch remains explicitly reported.')
        path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['tensors','decoded_RGB']}))
if __name__=='__main__':main()
