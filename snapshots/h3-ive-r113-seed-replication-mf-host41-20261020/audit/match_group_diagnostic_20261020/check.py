"""CPU diagnostic of existing official MF assignments; no new tracking."""
import os,sys,json,hashlib
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/'runtime/ive/metric_runtime'
sys.path.insert(0,str(RUNTIME))
import numpy as np
import torch
from scipy.optimize import linear_sum_assignment
import score_cached_tracks as cache
load_cache=cache.load_cache
from ive_mf_adapter import official_class,verify_vendor

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(p),'sha256':sha(p)}
def assignment(e,st,sv,tt,tv):
    a,av,b,bv=e.synchronize_videos(st[0].numpy(),sv[0].numpy(),tt[0].numpy(),tv[0].numpy())
    si=[i for i in range(a.shape[1])if av[:,i].mean()>.3 and (av[:,i]>.5).sum()>=5]
    ti=[i for i in range(b.shape[1])if bv[:,i].mean()>.3 and (bv[:,i]>.5).sum()>=5]
    mat=np.array([[e.compute_frame_by_frame_similarity(a[:,i],b[:,j],av[:,i],bv[:,j])for j in ti]for i in si])
    rr,cc=linear_sum_assignment(-mat)
    rows=[]
    for r,c in zip(rr,cc):
        i,j=si[r],ti[c];score=float(mat[r,c]);v0=sv[0,:,i].numpy()>.5;v1=tv[0,:,j].numpy()>.5
        rows.append({'source_id':int(i),'target_id':int(j),'score':score,'included':bool(score>.3),'source_visible_frames':int(v0.sum()),'target_visible_frames':int(v1.sum()),'common_visible_frames':int((v0&v1).sum()),'source_ever_invisible':bool(not v0.all()),'target_ever_invisible':bool(not v1.all())})
    official=float(e._compute_similarity_from_tracks(st,sv,tt,tv));keep=[r['score']for r in rows if r['included']]
    assert abs(official-float(np.mean(keep)))<1e-12
    return {'official_MF':official,'valid_source_tracks':len(si),'valid_target_tracks':len(ti),'matched':len(rows),'included':len(keep),'assignments':rows}

def main():
    out=Path(__file__).parent/'RESULT.json';assert not out.exists()
    torch.set_num_threads(2);vendor=verify_vendor();cls=official_class();e=cls.__new__(cls)
    sf=ROOT/'cases/short_0252/tracks/source';manifest=json.loads((ROOT/'cases/short_0252/INPUTS.json').read_text());cache.SELECTION_SHA=manifest['selection_sha256'];sr,st,sv=load_cache(sf)
    assert sha(sf/'REPORT.json')==manifest['source_cache']['report_sha256'] and sr['tracks_sha256']==manifest['source_cache']['tracks_sha256']
    targetroot=ROOT/'audit/actual_r113_mf_attempt1/tracks/short_0252'
    results={};bindings={'source':{'report':bound(sf/'REPORT.json'),'tracks':bound(sf/'tracks.npz')}}
    for role,suffix in [('native','native'),('guided','fixed')]:
        d=targetroot/f'seed2026101703_{suffix}';tr,tt,tv=load_cache(d)
        for k in ['pair_id','selection_sha256','source_prepared_sha256','source_score_sha256','effective_frame_count','score_frame_indices','tracker','checkpoint_sha256','official_commit']:assert sr[k]==tr[k],k
        results[role]=assignment(e,st,sv,tt,tv);bindings[role]={'report':bound(d/'REPORT.json'),'tracks':bound(d/'tracks.npz')}
    assert abs(results['native']['official_MF']-.8073502815483832)<1e-12
    assert abs(results['guided']['official_MF']-.7959751758810603)<1e-12
    labels=json.loads((Path(__file__).parent/'SOURCE_GROUPS.json').read_text());pointgroup={i:g for g,ids in labels['groups'].items()for i in ids}
    by={k:{r['source_id']:r for r in v['assignments']}for k,v in results.items()}
    rows=[]
    for i in range(100):
        n=by['native'].get(i);g=by['guided'].get(i)
        nc=0 if not n or not n['included'] else n['score']/results['native']['included']
        gc=0 if not g or not g['included'] else g['score']/results['guided']['included']
        rows.append({'source_id':i,'source_frame0_group':pointgroup[i],'native':n,'guided':g,'contribution_native':nc,'contribution_guided':gc,'contribution_delta':gc-nc,'assignment_changed':bool(n and g and n['target_id']!=g['target_id'])})
    def summary(selected):
        return {'source_points':len(selected),'matched_native':sum(r['native'] is not None for r in selected),'matched_guided':sum(r['guided'] is not None for r in selected),'included_native':sum(bool(r['native'] and r['native']['included'])for r in selected),'included_guided':sum(bool(r['guided'] and r['guided']['included'])for r in selected),'global_MF_contribution_native':sum(r['contribution_native']for r in selected),'global_MF_contribution_guided':sum(r['contribution_guided']for r in selected),'global_MF_contribution_delta':sum(r['contribution_delta']for r in selected),'assignment_changed':sum(r['assignment_changed']for r in selected)}
    groups={g:summary([r for r in rows if r['source_frame0_group']==g])for g in labels['groups']}
    # Visibility grouping uses the original physical-frame visibility before the official interpolation.
    visgroups={}
    for name in ['all_three_visible_every_frame','any_original_track_has_invisible_frames','missing_assignment']:
        selected=[]
        for r in rows:
            n,g=r['native'],r['guided']
            category='missing_assignment' if not n or not g else ('any_original_track_has_invisible_frames' if n['source_ever_invisible'] or n['target_ever_invisible'] or g['target_ever_invisible'] else 'all_three_visible_every_frame')
            if category==name:selected.append(r)
        visgroups[name]=summary(selected)
    assert abs(sum(g['global_MF_contribution_delta']for g in groups.values())-(results['guided']['official_MF']-results['native']['official_MF']))<1e-12
    assert not torch.cuda.is_initialized()
    record={'passed':True,'scope':'Post-hoc diagnostic of one existing generated pair. Source-frame labels, not segmentation ground truth or new benchmark metrics.','seed':2026101703,'source_id':'short_0252','frames':98,'fps':24,'official_vendor':vendor,'inputs':bindings,'source_labels':bound(Path(__file__).parent/'SOURCE_GROUPS.json'),'script':bound(__file__),'official_scores':{k:v['official_MF']for k,v in results.items()},'counts':{k:{x:v[x]for x in ['valid_source_tracks','valid_target_tracks','matched','included']}for k,v in results.items()},'source_frame0_groups':groups,'physical_visibility_groups':visgroups,'per_source_assignment':rows,'CUDA_initialized':False,'notes':['The official visible-point interpolation, Hungarian assignment, threshold and full-image MF are unchanged.','Each group contribution sums its kept similarities divided by that method total kept-pair count. Contributions therefore exactly sum to full MF; group means are not independent benchmark scores.','Visibility flags are tracker outputs and may reflect occlusion, tracking errors or out-of-view points. They do not establish an occlusion cause.','Semantic labels refer only to source frame 0. Hungarian assignment can match different target semantic regions.']}
    out.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'official_scores':record['official_scores'],'counts':record['counts'],'groups':groups,'visibility':visgroups},indent=2))
if __name__=='__main__':main()
