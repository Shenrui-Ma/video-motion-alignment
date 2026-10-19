"""Offline feasibility diagnostic, not a replacement for frozen pose endpoints.

Compare spatial maps of latent temporal-change magnitude. Fixed source-only
upper-body union ROI; no generated result chooses ROI, gain, or lag range.
No claim that latent change magnitude is optical flow or pure human motion.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import torch

HERE=Path(__file__).resolve().parent
OLD=Path('/Users/researcher/DevProjects/h3-timing-autoresearch-20261016')
SOURCE_POSE=OLD/'analysis/pose/old_sam/05_real_megumi_v.pose.json'
torch.set_num_threads(1)


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def geometry():
    spans=[(1,4,4,4,4)[i%5] for i in range(42)]
    starts=np.cumsum([0]+spans[:-1]);centers=starts+(np.array(spans)-1)/2
    return centers,(centers[1:]+centers[:-1])/2


def source_roi():
    d=json.loads(SOURCE_POSE.read_text());points=[]
    for f in d['frames']:
        idx=f['selected_person']
        if idx is None:continue
        p=f['persons'][idx]
        points.extend(p['coco17_xy'][j] for j in range(5,11) if p['coco17_score'][j]>=.5)
    xy=np.array(points);lo=xy.min(0);hi=xy.max(0);margin=.1*(hi-lo)
    lo=np.maximum(0,lo-margin);hi=np.minimum([1312,736],hi+margin)
    a=np.floor(lo/16).astype(int);b=np.ceil(hi/16).astype(int)
    return [int(a[1]),int(b[1]),int(a[0]),int(b[0])]


def energy(z,roi):
    if tuple(z.shape)!=(1,24,42,46,82):raise ValueError(z.shape)
    centers,edges=geometry();r0,r1,c0,c1=roi
    dz=z[0,:,1:]-z[0,:,:-1]
    magnitude=dz.square().mean(0).sqrt()/torch.tensor(np.diff(centers),dtype=z.dtype)[:,None,None]
    return edges,magnitude[:,r0:r1,c0:c1].reshape(41,-1).numpy()


def interpolate(times,values,queries):
    return np.stack([np.interp(queries,times,values[:,i]) for i in range(values.shape[1])],-1)


def scan(ref,generated,window):
    t=np.arange(window[0],window[1]+1,dtype=float)
    a=interpolate(ref[0],ref[1],t)
    records=[]
    for lag in range(-24,25):
        b=interpolate(generated[0],generated[1],t+lag)
        den=np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)
        valid=den>1e-10
        error=float(np.mean(1-np.sum(a[valid]*b[valid],axis=1)/den[valid])) if valid.any() else None
        records.append({'lag_frames':lag,'spatial_cosine_error':error,'valid_frames':int(valid.sum())})
    ranked=sorted((r for r in records if r['spatial_cosine_error'] is not None),key=lambda r:r['spatial_cosine_error'])
    if not ranked:return {'best':None,'curve':records}
    best=ranked[0];rival=next((x for x in ranked if abs(x['lag_frames']-best['lag_frames'])>=4),None)
    return {'best':best,'separated_runner_up':rival,
            'margin':None if rival is None else rival['spatial_cosine_error']-best['spatial_cosine_error'],
            'boundary_optimum':abs(best['lag_frames'])==24,'curve':records}


def main():
    reference_path=HERE/'reference_video_vae.pt'
    assert digest(reference_path)=='a2936536516cdad698bd553ea8b2654b49bca168fb5b59ab111f41a72be5fbb0'
    roi=source_roi();windows=[[50,65],[69,81],[80,92],[99,111]]
    protocol={'status':'diagnostic-only, no new primary metric or closed-loop sensor claim',
              'source_only_roi_yxyx':roi,'source_pose_sha256':digest(SOURCE_POSE),
              'geometry':'source VAE latent and x0 after_process_latent_out video, unchanged normalization',
              'signal':'per-pixel RMS across24channels of adjacent-bin differences divided by positional-center frame spacing',
              'comparison':'mean spatial cosine error, linearly interpolated in physical position-frame coordinates',
              'lag_search_frames':[-24,24],'windows_inclusive':windows,'rois':['source_upper_body_union','full_frame_sensitivity'],
              'limitations':['VAE positional spans are not exact receptive fields','No calibration from generated video','Magnitude loses signed movement direction','Flat or boundary optimum is not reliable phase evidence','Old results are used for feasibility, not held-out validation']}
    (HERE/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    ref=torch.load(reference_path,map_location='cpu',weights_only=True)
    report={'protocol':protocol,'runs':{}}
    for mode in ('native','mass'):
        directory=OLD/'audit/x0'/f's05_full_seed1_{mode}_x0'
        for filename in ('x0_step005.pt','x0_step010.pt','x0_step015.pt','x0_step019.pt','sampler_final.pt'):
            p=directory/filename;data=torch.load(p,map_location='cpu',weights_only=True)
            assert data['metadata']['normalization_stage']=='after_process_latent_out'
            entry={'file':str(p),'sha256':digest(p),'rois':{}}
            for name,region in [('source_upper_body_union',roi),('full_frame_sensitivity',[0,46,0,82])]:
                a=energy(ref,region);b=energy(data['video'],region)
                entry['rois'][name]=[scan(a,b,w) for w in windows]
            report['runs'][mode+'/'+filename]=entry
    (HERE/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    for name,v in report['runs'].items():
        print(name,[(label,[r['best']['lag_frames'] for r in runs]) for label,runs in v['rois'].items()])


if __name__=='__main__':main()
