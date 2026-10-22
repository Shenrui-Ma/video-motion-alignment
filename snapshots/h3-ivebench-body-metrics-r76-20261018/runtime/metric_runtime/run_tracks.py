"""Cache one video through the unchanged official IVEBench CoTracker3 path."""
import argparse,json,os,subprocess,time
from pathlib import Path
from ive_mf_adapter import (LITERATURE,SELECTION_SHA,WEIGHT_SHA,COMMIT,sha,read_json,
    verify_vendor,official_class,validate_source_row,validate_edited_entry,frame_hashes)

def check_gpu(uuid):
    if not isinstance(uuid,str) or not uuid.startswith('GPU-') or os.environ.get('CUDA_VISIBLE_DEVICES')!=uuid:
        raise ValueError('bind the exact root-admitted GPU UUID')
    raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True)
    owned=set();rows=[]
    for line in raw.strip().splitlines():
        pid,used=[s.strip() for s in line.split(',')]
        if used==uuid:raise ValueError('selected GPU already has a compute process')
        p=Path('/proc')/pid
        if p.exists() and p.stat().st_uid==os.getuid():owned.add(used)
        rows.append({'pid':int(pid),'gpu_uuid':used})
    if len(owned)>=2:raise ValueError('two own GPU cards already occupied')
    memory=int(subprocess.check_output(['nvidia-smi','-i',uuid,'--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
    if memory>1024:raise ValueError('selected GPU memory not released')
    return {'other_compute_processes':rows,'selected_memory_MiB':memory}

def select_pair(manifest,pair,selection):
    if sha(selection)!=SELECTION_SHA:raise ValueError('selection changed')
    e=next(x for x in read_json(selection)['pairs'] if x['pair_id']==pair)
    d=read_json(manifest)
    if 'pairs' in d:
        if d.get('schema') not in ['h3-ivebench-source-mf-inputs-v1','h3-ivebench-official-mf-source-inputs-v1','h3-ivebench-official-mf-inputs-v1'] or d.get('selection_sha256')!=SELECTION_SHA:
            raise ValueError('input manifest schema/selection mismatch')
        frozen={x['pair_id'] for x in read_json(selection)['pairs']}
        if len(d['pairs'])!=5 or {x['pair_id'] for x in d['pairs']}!=frozen:raise ValueError('full fixed source set required')
        row=next(x for x in d['pairs'] if x['pair_id']==pair)
    else:
        row=d
        if row.get('pair_id')!=pair:raise ValueError('released pair differs')
    return row,e

def main(a):
    row,e=select_pair(a.input_manifest,a.pair,a.selection)
    validate_source_row(row,e,a.ffprobe,a.ffmpeg)
    if a.method=='source':video=row['source_score_video']
    else:
        entry=row['edited'][a.method]
        validate_edited_entry(entry,e['input_protocol']['effective_frame_count'],a.ffprobe,a.ffmpeg)
        video=entry['score_video']
    checkpoint=LITERATURE/'weights/baseline_offline.pth'
    if sha(checkpoint)!=WEIGHT_SHA:raise ValueError('official checkpoint changed')
    vendor=verify_vendor();output=Path(a.output);output.mkdir(parents=True,exist_ok=False)
    report={'passed':False,'pair_id':a.pair,'method':a.method,'pid':os.getpid(),'uid':os.getuid(),
        'official_commit':COMMIT,'vendor':vendor,'checkpoint_sha256':WEIGHT_SHA,
        'input_manifest':{'file':str(Path(a.input_manifest).resolve()),'sha256':sha(a.input_manifest)},
        'selection_sha256':SELECTION_SHA,'source_prepared_sha256':row['source_prepared_video']['sha256'],
        'source_score_sha256':row['source_score_video']['sha256'],'score_video':video,
        'effective_frame_count':e['input_protocol']['effective_frame_count'],
        'score_frame_indices':row['score_frame_indices'],'gpu_uuid':a.gpu_uuid,
        'tracker':{'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60},
        'decoded_frame_md5':frame_hashes(video['file'],a.ffmpeg)}
    if a.check_only:
        report.update(passed=True,check_only=True,tracking_forwards=0,torch_imported=False)
        (output/'PREFLIGHT.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'passed':True,'pair_id':a.pair,'method':a.method,'tracking_forwards':0}));return
    started=time.monotonic()
    try:
        report['admission']=check_gpu(a.gpu_uuid)
        os.environ['OMP_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2'
        import numpy as np
        import torch
        torch.set_num_threads(2)
        if torch.cuda.is_initialized():raise ValueError('CUDA initialized before final admission')
        cls=official_class();evaluator=cls(str(checkpoint),device='cpu',grid_size=10,max_frames=None)
        report['admission_before_cuda']=check_gpu(a.gpu_uuid)
        evaluator.model=evaluator.model.to('cuda');evaluator.device='cuda'
        video_tensor=evaluator.load_video_data(video['file']).to('cuda')
        torch.cuda.synchronize();tick=time.monotonic()
        with torch.no_grad():
            tracks,visibility=evaluator.model(video_tensor,grid_size=10,grid_query_frame=0,backward_tracking=False)
        torch.cuda.synchronize();report['tracking_seconds']=time.monotonic()-tick
        count=e['input_protocol']['effective_frame_count']
        if list(tracks.shape)!=[1,count,100,2] or list(visibility.shape)!=[1,count,100]:raise ValueError('unexpected official tracker shape')
        if not torch.isfinite(tracks).all() or not torch.isfinite(visibility).all():raise ValueError('nonfinite tracker output')
        dest=output/'tracks.npz';np.savez(dest,tracks=tracks.cpu().numpy(),visibility=visibility.cpu().numpy())
        report.update(passed=True,tracks_sha256=sha(dest),tracks_shape=list(tracks.shape),visibility_shape=list(visibility.shape),
            torch_version=torch.__version__,cuda_version=torch.version.cuda,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
    except Exception as error:
        report['error']=repr(error);raise
    finally:
        report['wall_seconds']=time.monotonic()-started
        (output/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='decoded_frame_md5'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-manifest',required=True);p.add_argument('--selection',required=True);p.add_argument('--pair',required=True);p.add_argument('--method',required=True);p.add_argument('--gpu-uuid');p.add_argument('--check-only',action='store_true');p.add_argument('--output',required=True);p.add_argument('--ffmpeg',default='/usr/bin/ffmpeg');p.add_argument('--ffprobe',default='/usr/bin/ffprobe');main(p.parse_args())
