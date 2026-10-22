"""Exploratory role statistics only; never changes the frozen phase readout."""
import argparse
import json
import os
from pathlib import Path
import time
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch
from phase_calibration import sha, signature, timeline, pool, features, load_input


def stats(x):
    x=x.flatten().double()
    return dict(n=len(x),mean=float(x.mean()),median=float(x.median()),
                min=float(x.min()),max=float(x.max()),std_population=float(x.std(unbiased=False))) if len(x) else dict(n=0)


def latent_roles(z,valid_frames):
    starts,ends,centers,valid=timeline(z.shape[2],valid_frames);ids=valid.nonzero().flatten()
    raw=z[0,:,ids].double();p=pool(z)[ids]
    f,fi,fv,scale=features(p,ids,centers)
    dv=(p[2:]-p[:-2])/((centers[ids[2:]]-centers[ids[:-2]])/24)[:,None,None,None]
    means=raw.mean(dim=(2,3)).T
    out=[]
    for role in range(5):
        keep=ids%5==role;kf=fi%5==role
        rr=raw[:,keep]
        per_time_rms=rr.square().mean(dim=(0,2,3)).sqrt()
        out.append(dict(role=role,bins=ids[keep].tolist(),
                        raw_activation_mean=float(rr.mean()),raw_rms=float(rr.square().mean().sqrt()),
                        per_time_rms=stats(per_time_rms),channel_means=means[keep].mean(dim=0).tolist(),
                        pooled_vector_norm=stats(p[keep].flatten(1).norm(dim=1)),
                        temporal_derivative_norm=stats(dv[kf].flatten(1).norm(dim=1))))
    mv=torch.stack([means[ids%5==r].mean(dim=0) for r in range(5)])
    mn=mv/mv.norm(dim=1).clamp_min(1e-30)[:,None]
    return dict(role_statistics=out,role_mean_vector_cosine=(mn@mn.T).tolist(),
                positional_bin_count=len(ids),feature_bins=fi.tolist())


def cost_groups(cost,src_ids,target_ids):
    cost=torch.tensor(cost,dtype=torch.float64);si=torch.tensor(src_ids);ti=torch.tensor(target_ids)
    lag=ti[:,None]-si[None,:]
    out={}
    scopes={'all':torch.ones_like(lag,dtype=torch.bool),'band6':lag.abs()<=6,
            'band6_no_diagonal':(lag.abs()<=6)&(lag!=0),
            'band6_exclude_distance_le1':(lag.abs()<=6)&(lag.abs()>1)}
    for label,mask in scopes.items():
        out[label]=dict(by_modulo=[dict(target_minus_source_mod5=r,**stats(cost[mask&(lag.remainder(5)==r)])) for r in range(5)],
                        by_target_source_role=[[stats(cost[mask&(ti[:,None].remainder(5)==i)&(si[None,:].remainder(5)==j)]) for j in range(5)] for i in range(5)],
                        same_role=stats(cost[mask&(lag.remainder(5)==0)]),
                        different_role=stats(cost[mask&(lag.remainder(5)!=0)]))
    out['by_exact_lag']=[dict(target_minus_source_bin=k,**stats(cost[lag==k])) for k in range(-6,7)]
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--results',required=True);ap.add_argument('--host-key',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1);start=time.perf_counter()
    inputs=json.loads(Path(a.inputs).read_text());original=json.loads(Path(a.results).read_text())
    output=dict(schema='h3-posthoc-phase-role-analysis-v1',scope='posthoc descriptive analysis; no estimator parameter changes; not independent video samples',script_sha256=sha(__file__),frozen_readout_results_sha256=sha(a.results),inputs_sha256=sha(a.inputs),rows=[])
    for row in inputs['rows']:
        if row['host_key']!=a.host_key:continue
        old=next(x for x in original['rows'] if x['case']==row['case'] and x['method']==row['method'])
        src,ev=load_input(row['source_file'],row['shape'],row['source_tensor_sha256'],row['source_file_sha256'])
        src_self=next(x for x in old['source_calibration']['shifts'] if x['delta_bins']==0)
        rec=dict(case=row['case'],method=row['method'],source=dict(input=ev,latent=latent_roles(src,row['valid_frames']),
                 self_cost_groups=cost_groups(src_self['cost_matrix'],src_self['source_bins'],src_self['target_bins'])),snapshots=[])
        del src
        for oldsnap in old['snapshots']:
            z,ev=load_input(oldsnap['input']['file'],row['shape'],oldsnap['input']['tensor_signature']['sha256'],oldsnap['input']['file_sha256'],is_snapshot=True)
            selfrow=next(x for x in oldsnap['self_calibration']['shifts'] if x['delta_bins']==0);cross=oldsnap['cross_identity']
            rec['snapshots'].append(dict(name=oldsnap['name'],input=ev,latent=latent_roles(z,row['valid_frames']),
                self_cost_groups=cost_groups(selfrow['cost_matrix'],selfrow['source_bins'],selfrow['target_bins']),
                cross_cost_groups=cost_groups(cross['cost_matrix'],cross['source_bins'],cross['target_bins'])))
            del z
        output['rows'].append(rec)
    output['wall_seconds']=time.perf_counter()-start;output['cuda_initialized']=torch.cuda.is_initialized()
    Path(a.out).write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(out=a.out,rows=len(output['rows']),wall_seconds=output['wall_seconds'],cuda=output['cuda_initialized'])))


if __name__=='__main__':main()
