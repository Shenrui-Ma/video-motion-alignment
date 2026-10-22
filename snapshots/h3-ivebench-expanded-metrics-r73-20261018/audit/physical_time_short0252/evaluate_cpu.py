"""Exploratory final-video pose diagnostic; frozen numerical functions, no GPU."""
from pathlib import Path
import copy, hashlib, importlib.util, json, sys
from collections import Counter
import numpy as np
B=Path(__file__).resolve().parent
P=json.loads((B/'PROTOCOL.json').read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for relative, expected in P['bindings'].items():
    if sha(B/relative)!=expected: raise ValueError('Frozen dependency changed: '+relative)
sys.path[:0]=[str(B/'vendor/physical'),str(B/'vendor/visible/scripts'),str(B/'vendor/visible/extensions'),str(B)]
import evaluate90 as ev
import timing_metrics as metrics
import arm_features
import pose_domain
from H3AutomaticWindowRouter.geometry import Geometry
from independent_targets import independent_targets
G=Geometry(width=1312,height=736,frames=107,fps=24,valid_frames=98)
paths={'source':B/'poses/source/short_0252_video.pose.json','native':B/'poses/native/native.pose.json','forced':B/'poses/forced/forced.pose.json'}
raw={k:pose_domain.validate_pose(p,G) for k,p in paths.items()}
receipts={}
for k,a in raw.items():
    if a['video']['sha256']!=P['media'][k]['sha256']:raise ValueError('Video binding mismatch')
    rejects=[];centres=[]
    for r in a['frames']:
        selected=r['selected_person']
        if selected is None:continue
        person=r['persons'][selected];box=person['box_xyxy'];cx=(box[0]+box[2])/2/G.width
        centres.append(cx)
        if not .40<=cx<=.75:rejects.append(r['frame']);r['selected_person']=None
    receipts[k]={'raw_pose_sha256':sha(paths[k]),'raw_file':str(paths[k]),'full_frames':107,'valid_frames':98,'adult_rejected_frames':rejects,'selected_box_centre_normalized_range':[min(centres),max(centres)] if centres else None}
(B/'derived_adult_only').mkdir(exist_ok=True)
for k,a in raw.items():(B/'derived_adult_only'/f'{k}.pose.json').write_text(json.dumps(a,allow_nan=False))
# The adapter changes only registered geometry/domain; original numerical code remains byte-frozen.
ev.P=copy.deepcopy(ev.P)
ev.P.update(cases=[{'pair_id':'short_0252','effective_frames':98,'windows_inclusive':P['windows']}],features=P['features'],confidence_thresholds=P['thresholds']['confidence'])
results={}
for representation,features in [('original_torso',pose_domain.features),('visible_wholearm',arm_features.features)]:
    def valid_view(a,count,threshold,features=features):
        if count!=G.valid_frames or len(a['frames'])!=G.frames:raise ValueError('Unexpected registered geometry')
        return features(a,G,threshold)
    ev.valid_view=valid_view
    paired=ev.evaluate(raw['source'],raw['native'],raw['forced'],'short_0252')
    independent=independent_targets(ev.evaluate,raw['source'],{k:raw[k] for k in ['native','forced']},'short_0252')
    # Explicitly bind the new protocol rather than inherited five-case protocol metadata.
    for r in [paired,*independent.values()]:
        r['original_evaluator_protocol_sha256']=r['protocol_sha256']
        r['protocol_sha256']=sha(B/'PROTOCOL.json')
        r['scope']='Final-video exploratory diagnostic; fixed physical indices; not online observations'
    results[representation]={'paired':paired,'independent':independent}

def load_scan(name,folder):
    spec=importlib.util.spec_from_file_location(name,B/'vendor'/folder/'scripts/scan_current_pose.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
scans={}
for label,folder in [('r55_original','original'),('r59_visible_wholearm','visible')]:
    module=load_scan(label,folder);scans[label]={}
    for k in ['native','forced']:
        x=module.observe(B/'derived_adult_only/source.pose.json',B/'derived_adult_only'/f'{k}.pose.json',19,G)
        x['scope']='Final-video frozen scanner diagnostic at label19; no inference policy executed'
        scans[label][k]=x
summary={'schema':'r73-short0252-final-pose-exploratory-v1','protocol_sha256':sha(B/'PROTOCOL.json'),'fixed_case_denominator':1,'pose_bindings':receipts,'results':{},'scans':{},'warning':'Rows are overlapping windows/features, not independent samples. UNKNOWN is not synchronization.'}
for rep,data in results.items():
    summary['results'][rep]={k:{'qualified_rows':[x for x in val['lag_summary'] if x['status']=='qualified_exploratory'],'unknown_rows':sum(x['status']=='unknown' for x in val['lag_summary'])} for k,val in data['independent'].items()}
for label,arms in scans.items():
    summary['scans'][label]={k:{'status':x['status'],'row_count':len(x['windows']),'baseline_counts':dict(Counter(r['baseline'] for r in x['windows'])),'qualifying_gain_rows':[{'window':r['window'],'feature':r['feature'],'baseline':r['baseline'],'min_gain':r.get('min_gain')} for r in x['windows'] if r.get('status')=='measured' and r.get('min_gain',0)>.5]} for k,x in arms.items()}
for name,obj in [('PHYSICAL_RESULTS.json',results),('FROZEN_SCAN_RESULTS.json',scans),('SUMMARY.json',summary)]:
    (B/name).write_text(json.dumps(metrics.clean(obj),ensure_ascii=False,indent=2,allow_nan=False))
print(json.dumps(summary,ensure_ascii=False,indent=2))
