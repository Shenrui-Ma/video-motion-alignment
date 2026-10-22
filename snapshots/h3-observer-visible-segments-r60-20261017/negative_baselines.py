"""Frozen same cross-case pairs through original and torso-free whole-arm scans."""
import argparse
import gzip
import json
from pathlib import Path
import time
import numpy as np
import diagnose as d
import negative_control as nc

HERE=Path(__file__).resolve().parent
WHOLE={'arm_direction':['left_upper_5_7','left_forearm_7_9','right_upper_6_8','right_forearm_8_10'],
       'left_arm_direction':['left_upper_5_7','left_forearm_7_9'],
       'right_arm_direction':['right_upper_6_8','right_forearm_8_10']}


def freeze():
    p=nc.verify()
    d.write(HERE/'NEGATIVE_BASELINE_PROTOCOL.json',{
        'schema':'r60-same-pair-original-whole-arm-control-v1',
        'negative_protocol_sha256':d.sha(HERE/'NEGATIVE_PROTOCOL.json'),
        'script_sha256':d.sha(__file__),'pairs':p['pairs'],
        'versions':['r55_original','r56_whole_arm'],
        'features':WHOLE,'threshold_policy_and_time_domain':'same frozen R55 signed thresholds and original physical valid-prefix intersection',
        'span':'report maximum pairwise direction angle per actual bone over each selected source/proposed-target window; descriptive only',
        'new_thresholds':False,'GPU_calls':0,'new_pose_calls':0})
    print(d.sha(HERE/'NEGATIVE_BASELINE_PROTOCOL.json'))


def verify():
    nc.verify();p=d.read(HERE/'NEGATIVE_BASELINE_PROTOCOL.json')
    assert p['script_sha256']==d.sha(__file__)
    assert p['negative_protocol_sha256']==d.sha(HERE/'NEGATIVE_PROTOCOL.json')
    assert p['pairs']==d.read(HERE/'NEGATIVE_PROTOCOL.json')['pairs']
    return p


def spans(features,indices,feature,names):
    rows=[]
    for i,name in enumerate(names):
        vector=features[feature][indices,i];okay=np.isfinite(vector).all(-1);v=vector[okay]
        pair=okay[1:]&okay[:-1]
        delta=np.linalg.norm(vector[1:]-vector[:-1],axis=-1)
        rows.append({'segment':name,'physical_frames':indices.tolist(),'valid_vectors':int(okay.sum()),
                     'max_pairwise_angle_degrees':float(np.degrees(np.arccos(np.clip(v@v.T,-1,1))).max()) if len(v) else None,
                     'chord_total_variation':float(delta[pair].sum()),'adjacent_valid_pairs':int(pair.sum())})
    return rows


def selected_spans(scanner,feature_fn,source_path,target_path,geometry,selected,names):
    source=feature_fn(scanner.valid_pose(source_path,geometry),geometry,.5)
    target=feature_fn(scanner.valid_pose(target_path,geometry),geometry,.5)
    out=[]
    for row in selected:
        a,b=row['window'];f=row['feature'];lag=row['lags']['0.5']
        indices=np.arange(a,b+1)
        mapped=indices+int(lag);valid=(mapped>=0)&(mapped<geometry.valid_frames)
        out.append({'selection':row,'source':spans(source,indices,f,names[f]),
                    'target_at_proposed_shift':spans(target,mapped[valid],f,names[f]),
                    'out_of_domain_match_frames':int((~valid).sum())})
    return out


def run(version):
    p=verify();scanner,policy,helper,_=d.load('r55');original=scanner.features
    if version=='r56_whole_arm':scanner.features=helper.features
    d.NAMES['whole_arm']=WHOLE
    output=HERE/'results'/('cross_case_'+version);output.mkdir(exist_ok=False)
    records=[];start=time.monotonic()
    try:
        for pair in p['pairs']:
            geometry=scanner.Geometry(frames=90,valid_frames=pair['valid_frames'])
            scan=scanner.observe(pair['source_pose'],pair['target_pose'],0,geometry)
            summary=d.summary_record(scan,policy,'whole_arm',None)
            decisions=summary.pop('repetition_decisions')
            evidence=selected_spans(scanner,scanner.features,pair['source_pose'],pair['target_pose'],geometry,decisions[1]['selected'],WHOLE) if decisions[1]['selected'] else []
            artifact=d.save_gz(output/(pair['source_id']+'__'+pair['target_id']+'.json.gz'),
                               {'observation':scan,'decisions':decisions})
            records.append({**pair,**summary,'selected_direction_spans':evidence,'artifact':artifact})
        result={'version':version,'source_pairs':5,'records':records,'cpu_seconds':time.monotonic()-start,
                'baseline_protocol_sha256':d.sha(HERE/'NEGATIVE_BASELINE_PROTOCOL.json'),
                'ON_pairs':sum(r['possible_ON_after_identical_repeat'] for r in records),
                'GPU_calls':0,'new_pose_calls':0,'no_groundtruth_temporal_lag':True}
        verify();d.write(output/'SUMMARY.json',result);print(json.dumps({k:v for k,v in result.items() if k!='records'}))
    finally:scanner.features=original


def segment_spans():
    verify();scanner,_,helper,_=d.load('r55');rows=[]
    for family in ('upper','forearm'):
        summary=d.read(HERE/'results'/('cross_case_'+family)/'SUMMARY.json')
        for row in summary['records']:
            path=HERE/row['artifact']['path'];assert d.sha(path)==row['artifact']['sha256']
            with gzip.open(path,'rt') as f:payload=json.load(f)
            selected=payload['decisions'][1]['selected']
            geometry=scanner.Geometry(frames=90,valid_frames=row['valid_frames'])
            feature_fn=d.make(helper,family)
            rows.append({'family':family,'source_id':row['source_id'],'target_id':row['target_id'],
                         'artifact_sha256':d.sha(path),
                         'selected_direction_spans':selected_spans(scanner,feature_fn,row['source_pose'],row['target_pose'],geometry,selected,d.NAMES[family]) if selected else []})
    d.write(HERE/'NEGATIVE_SEGMENT_SPANS.json',{'rows':rows,'baseline_protocol_sha256':d.sha(HERE/'NEGATIVE_BASELINE_PROTOCOL.json')})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--version',choices=['r55_original','r56_whole_arm']);p.add_argument('--segment-spans',action='store_true');a=p.parse_args()
    if a.freeze:freeze()
    elif a.segment_spans:segment_spans()
    else:run(a.version)
