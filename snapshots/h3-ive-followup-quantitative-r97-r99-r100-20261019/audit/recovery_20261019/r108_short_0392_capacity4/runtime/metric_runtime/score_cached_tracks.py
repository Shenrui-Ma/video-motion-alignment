"""Apply unchanged official MF matching to two provenance-bound tracking caches."""
import argparse,json,math,time
from pathlib import Path
from ive_mf_adapter import COMMIT,SELECTION_SHA,WEIGHT_SHA,read_json,sha,official_class,verify_vendor

TRACKER={'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60}

def load_cache(folder):
    import numpy as np
    import torch
    folder=Path(folder);report=read_json(folder/'REPORT.json');data=folder/'tracks.npz'
    expected={'passed':True,'official_commit':COMMIT,'checkpoint_sha256':WEIGHT_SHA,'selection_sha256':SELECTION_SHA,'tracker':TRACKER}
    for key,value in expected.items():
        if report.get(key)!=value:raise ValueError('cache contract mismatch: '+key)
    if sha(data)!=report['tracks_sha256']:raise ValueError('cache tensor file changed')
    count=report['effective_frame_count']
    if report['score_frame_indices']!=list(range(count)):raise ValueError('cache time sampling changed')
    with np.load(data,allow_pickle=False) as z:
        tracks=torch.from_numpy(z['tracks'].copy());vis=torch.from_numpy(z['visibility'].copy())
    if list(tracks.shape)!=[1,count,100,2] or list(vis.shape)!=[1,count,100]:raise ValueError('cache tensor shape differs')
    if not torch.isfinite(tracks).all() or not torch.isfinite(vis).all():raise ValueError('nonfinite cache')
    return report,tracks,vis

def score(source,target):
    import torch
    torch.set_num_threads(2)
    vendor=verify_vendor();s,st,sv=load_cache(source);t,tt,tv=load_cache(target)
    if s['method']!='source' or t['method']=='source':raise ValueError('source/generated cache roles required')
    for key in ['pair_id','selection_sha256','source_prepared_sha256','source_score_sha256','effective_frame_count','score_frame_indices','tracker','checkpoint_sha256','official_commit']:
        if s[key]!=t[key]:raise ValueError('source/generated tracking protocols differ: '+key)
    tick=time.monotonic();cls=official_class();evaluator=cls.__new__(cls)
    value=float(evaluator._compute_similarity_from_tracks(st,sv,tt,tv))
    if not math.isfinite(value):raise ValueError('nonfinite official MF')
    return {'schema':'h3-ivebench-official-mf-cached-result-v1','pair_id':s['pair_id'],'method':t['method'],
        'motion_fidelity':value,'official_vendor':vendor,'checkpoint_sha256':WEIGHT_SHA,
        'source_report':{'file':str(Path(source)/'REPORT.json'),'sha256':sha(Path(source)/'REPORT.json')},
        'target_report':{'file':str(Path(target)/'REPORT.json'),'sha256':sha(Path(target)/'REPORT.json')},
        'source_tracks_sha256':s['tracks_sha256'],'target_tracks_sha256':t['tracks_sha256'],
        'score_seconds':time.monotonic()-tick,'device':'cpu','cuda_initialized':torch.cuda.is_initialized(),
        'scope':'one adapted official task; cached exact official tracker path; unchanged official MF matching'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--target',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    out=Path(a.output)
    if out.exists():raise FileExistsError('preserve prior score; use a new output path')
    result=score(a.source,a.target);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
