"""Prespecified cross-case mismatch diagnostic and first-trigger evidence."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import time
import numpy as np

import diagnose as d
from segment_features import make, select

HERE = Path(__file__).resolve().parent


def freeze():
    d.verified()
    cases=d.read(HERE/'frozen/cases.json')['cases']
    pairs=[]
    for i,c in enumerate(cases):
        other=cases[(i+1)%len(cases)]
        pairs.append({'source_id':c['source_id'],'target_id':other['source_id'],
                      'valid_frames':min(c['valid_frame_count'],other['valid_frame_count']),
                      'source_pose':str(d.OLD/'source_snapshot'/c['source_pose_path']),
                      'source_sha256':c['source_pose_sha256'],
                      'target_pose':str(d.OLD/'source_snapshot'/other['source_pose_path']),
                      'target_sha256':other['source_pose_sha256']})
    d.write(HERE/'NEGATIVE_PROTOCOL.json',{
        'schema':'r60-fixed-cross-case-mismatch-v1','diagnostic_only':True,
        'main_protocol_sha256':d.sha(HERE/'PROTOCOL.json'),'script_sha256':d.sha(__file__),
        'pairs':pairs,'families':['upper','forearm'],
        'geometry':'original1312x736x90@24; common min(valid prefixes), original frame/time retained',
        'transformation':'none; compare different fixed source videos at original physical timestamps',
        'semantic_status':'different original tasks/videos; no known event correspondence or groundtruth lag',
        'policy':'original R55 signed and original thresholds; identical scan repeated twice only for persistence capability',
        'interpretation':'ON is a potential semantic-mismatch false alarm; no measured video improvement',
        'first_trigger_evidence':'existing R55 upper index5 fixed selection; unit direction variation and same/proposal/null costs',
        'GPU_calls':0,'new_pose_calls':0})
    print(d.sha(HERE/'NEGATIVE_PROTOCOL.json'))


def verify():
    d.verified();p=d.read(HERE/'NEGATIVE_PROTOCOL.json')
    assert p['script_sha256']==d.sha(__file__)
    assert p['main_protocol_sha256']==d.sha(HERE/'PROTOCOL.json')
    for row in p['pairs']:
        assert d.sha(row['source_pose'])==row['source_sha256']
        assert d.sha(row['target_pose'])==row['target_sha256']
    return p


def run(family):
    p=verify();scanner,policy,helper,_=d.load('r55')
    original=scanner.features;scanner.features=make(helper,family)
    output=HERE/'results'/('cross_case_'+family);output.mkdir(exist_ok=False)
    rows=[];start=time.monotonic()
    try:
        for pair in p['pairs']:
            geometry=scanner.Geometry(width=1312,height=736,frames=90,fps=24,valid_frames=pair['valid_frames'])
            observation=scanner.observe(pair['source_pose'],pair['target_pose'],0,geometry)
            summary=d.summary_record(observation,policy,family,None)
            artifact=d.save_gz(output/(pair['source_id']+'__'+pair['target_id']+'.json.gz'),
                               {'observation':observation,'decisions':summary.pop('repetition_decisions')})
            rows.append({**pair,**summary,'artifact':artifact})
        result={'family':family,'source_pairs':5,'records':rows,'cpu_seconds':time.monotonic()-start,
                'negative_protocol_sha256':d.sha(HERE/'NEGATIVE_PROTOCOL.json'),
                'ON_pairs':sum(r['possible_ON_after_identical_repeat'] for r in rows),
                'no_groundtruth_temporal_lag':True,'GPU_calls':0,'new_pose_calls':0}
        verify();d.write(output/'SUMMARY.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='records'}))
    finally:scanner.features=original


def variation(features,indices,feature):
    vectors=features[feature][indices]
    valid=np.isfinite(vectors).all(-1)
    # Every valid vector is recorded; only adjacent pairs with both visible enter total variation.
    angle=np.arctan2(vectors[...,1],vectors[...,0])
    pairs=valid[1:]&valid[:-1]
    angular_delta=np.arctan2(np.sin(angle[1:]-angle[:-1]),np.cos(angle[1:]-angle[:-1]))
    chord=np.linalg.norm(vectors[1:]-vectors[:-1],axis=-1)
    out={'physical_indices':indices.tolist(),'unit_vectors':d.scanner_clean(vectors) if hasattr(d,'scanner_clean') else None,
         'valid_vectors':int(valid.sum()),'adjacent_valid_pairs':int(pairs.sum()),
         'chord_total_variation':float(chord[pairs].sum()),
         'angular_total_variation_degrees':float(np.degrees(np.abs(angular_delta[pairs])).sum()),
         'mean_adjacent_chord':float(chord[pairs].mean()) if pairs.any() else None}
    good=vectors[valid]
    if len(good):
        dot=np.clip(good@good.T,-1,1)
        out['maximum_pairwise_angle_degrees']=float(np.degrees(np.arccos(dot)).max())
    return out


def first_trigger():
    verify();scanner,_,helper,_=d.load('r55')
    d.scanner_clean=scanner.m.clean
    summary_path=HERE/'results/replay_r55_upper/SUMMARY.json'
    summary=d.read(summary_path);index=summary['first_execution_divergence']
    record=summary['records'][index]
    artifact=HERE/record['artifact']['path']
    assert d.sha(artifact)==record['artifact']['sha256']
    with gzip.open(artifact,'rt') as f: payload=json.load(f)
    exported_path=Path(summary['export']);exported=d.read(exported_path)
    geometry=scanner.Geometry.from_case(exported['case'])
    source_path=d.checked(exported_path.parent,exported['source_pose'])
    target_path=d.check_row(exported_path.parent,exported,exported['rows'][index],geometry)
    raw_s,raw_t=scanner.valid_pose(source_path,geometry),scanner.valid_pose(target_path,geometry)
    details=[]
    for choice in record['candidate_decision']['selected']:
        window=choice['window'];feature=choice['feature'];lag=choice['lags']['0.5']
        row=next(r for r in payload['candidate']['windows'] if r['window']==window and r['feature']==feature)
        by_conf={}
        for c in (.3,.5):
            source=select(helper.features(raw_s,geometry,c),'upper')
            target=select(helper.features(raw_t,geometry,c),'upper')
            indices=np.arange(window[0],window[1]+1)
            mapped=indices+int(choice['lags'][str(c)])
            assert min(mapped)>=0 and max(mapped)<geometry.valid_frames
            by_conf[str(c)]={'source':variation(source,indices,feature),
                            'target_at_same_physical_time':variation(target,indices,feature),
                            'target_at_proposed_shift':variation(target,mapped,feature),
                            'local_diagnostic':{k:v for k,v in row['measurements'][str(c)].items() if k!='curve'},
                            'all_common_support_null_comparisons':row['comparison'][str(c)]}
        details.append({'selection':choice,'actual_segments':d.NAMES['upper'][feature],
                        'source_window':window,'target_content_window_for_match':[window[0]+lag,window[1]+lag],
                        'by_confidence':by_conf})
    d.write(HERE/'FIRST_TRIGGER_EVIDENCE.json',{
        'index':index,'summary_sha256':d.sha(summary_path),'scan_sha256':d.sha(artifact),
        'source_sha256':d.sha(source_path),'target_sha256':d.sha(target_path),'details':details,
        'interpretation':'unit-bone shape match is a numerical proposal, not verified event timing. Root reports original final edit changes standing presentation to sitting in another room; final semantic mismatch needs separate assessment.',
        'no_threshold_change':True})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--first-trigger',action='store_true');p.add_argument('--family',choices=['upper','forearm']);a=p.parse_args()
    if a.freeze:freeze()
    elif a.first_trigger:first_trigger()
    else:run(a.family)
