"""Compare source RGB frames with actual archived VAE input tensors, without pickle."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
SWITCH=Path('/Users/researcher/DevProjects/h3-short-event-switching-20261013')
FAST=Path('/Users/researcher/DevProjects/h3-fast-motion-followup-20261013')
CASES=[(SWITCH,x) for x in ['05_real_megumi_v','06_anime_eye_insert','07_real_ary_v']]+[(FAST,'04_fast_motion')]


def read_exact(stream,n):
    chunks=[];total=0
    while total<n:
        x=stream.read(n-total)
        if not x:raise RuntimeError(f'short frame: {total}/{n}')
        chunks.append(x);total+=len(x)
    return b''.join(chunks)


rows=[]
for archive,case in CASES:
    audit=json.loads((archive/'audit'/f'{case}_a_s1_conditioning.json').read_text())
    prepared=next(x['prepared_frames'] for x in audit['native_vae_calls'] if x['prepared_frames']['shape'][0]>1)
    n,h,w,ch=prepared['shape'];assert ch==3 and prepared['dtype']=='torch.float32'
    source=archive/'inputs'/f'{case}.mp4';pt=archive/'audit'/prepared['tensor_file']
    info=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-count_frames','-select_streams','v:0',
      '-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration','-of','json',str(source)]))['streams'][0]
    assert [int(info['nb_read_frames']),info['height'],info['width'],3]==[n,h,w,ch]
    process=subprocess.Popen(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(source),'-map','0:v:0','-an',
      '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    digest=hashlib.sha256();full_mae=[];max_error=[];src_feature=[];prep_feature=[]
    with zipfile.ZipFile(pt) as z:
        storage=[x for x in z.infolist() if '/data/' in x.filename and x.filename.rsplit('/',1)[-1].isdigit()]
        assert len(storage)==1 and storage[0].file_size==n*h*w*ch*4
        with z.open(storage[0]) as raw:
            for index in range(n):
                b=read_exact(raw,h*w*ch*4);digest.update(b)
                values=np.frombuffer(b,dtype='<f4').reshape(h,w,ch)
                assert float(values.min())>=0 and float(values.max())<=1
                p=np.rint(values*255).astype(np.uint8)
                s=np.frombuffer(read_exact(process.stdout,h*w*ch),np.uint8).reshape(h,w,ch)
                delta=np.abs(s.astype(np.int16)-p.astype(np.int16))
                full_mae.append(float(delta.mean()));max_error.append(int(delta.max()))
                src_feature.append(s[8::16,8::16].reshape(-1).astype(np.float32))
                prep_feature.append(p[8::16,8::16].reshape(-1).astype(np.float32))
    assert process.stdout.read()==b''
    assert process.wait()==0,process.stderr.read().decode()
    assert digest.hexdigest()==prepared['sha256'],'raw tensor storage hash mismatch'
    # Close neighboring frames need float64 distance accumulation; float32
    # cancellation can change the ordering of nearly tied residuals.
    a=np.stack(src_feature).astype(np.float64);b=np.stack(prep_feature).astype(np.float64)
    distances=np.maximum(0,(a*a).mean(1)[:,None]+(b*b).mean(1)[None,:]-2*(a@b.T)/a.shape[1])
    matching=[]
    for i in range(n):
        lo,hi=max(0,i-24),min(n,i+25);sub=distances[lo:hi,i];best=float(sub.min())
        ties=(np.flatnonzero(sub<=best+1e-3)+lo).tolist()
        matching.append({'prepared_frame':i,'best_source_frames_within_plusminus24':ties,'same_index_is_best':i in ties,
                         'same_index_sample_mse':float(distances[i,i]),'best_sample_mse':best})
    r={'case':case,'source':str(source),'prepared_tensor':str(pt),'probe':info,'tensor_shape':prepared['shape'],
       'prepared_raw_storage_sha256_verified':True,'source_decoding':'local FFmpeg RGB24; archived tensor floats rounded back to8bit',
       'full_frame_aligned_mean_absolute_error_8bit':full_mae,'full_frame_aligned_max_error_8bit':max_error,
       'all_aligned_rgb_frames_exact':max(max_error)==0,'same_index_best_count':sum(x['same_index_is_best'] for x in matching),
       'frames':n,'local_temporal_match':matching,
       'limits':['Pixel alignment is for the unedited source versus actual preprocessing input, not for generated edited frames.',
                 'Sparse-grid temporal matching is a supplemental diagnostic; full-frame same-index errors are reported separately.',
                 'Different decoders may have small color rounding differences; this is not a denoising/output fidelity metric.']}
    rows.append(r);print(case,'frames',n,'meanMAE',float(np.mean(full_mae)),'maxError',max(max_error),'same_index_best',r['same_index_best_count'],flush=True)
(ROOT/'pixel_time_audit.json').write_text(json.dumps({'status':'complete','cases':rows},indent=2))
