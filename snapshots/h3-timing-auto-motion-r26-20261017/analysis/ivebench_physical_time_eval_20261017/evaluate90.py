"""Evaluate the preregistered valid physical-time views with unchanged metrics."""
import copy, hashlib, json
from pathlib import Path
import numpy as np
import timing_metrics as metrics
from shared_support import common_error
HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'PROTOCOL.json').read_text())

def valid_view(raw, count, threshold):
    records=raw['frames'];video=raw['video']
    if [video[k] for k in ['width','height','container_frame_count','fps']] != [1312,736,90,24]:
        raise ValueError('Full90 geometry differs')
    if len(records)!=90 or [r['frame'] for r in records]!=list(range(90)):
        raise ValueError('Full90 sample sequence differs')
    times=np.asarray([r['time_s'] for r in records])
    if not np.isfinite(times).all() or not np.allclose(times,np.arange(90)/24,rtol=0,atol=1e-6):
        raise ValueError('Physical timestamps differ')
    if count not in [c['effective_frames'] for c in P['cases']]:raise ValueError('Unregistered valid prefix')
    # Validate the entire stored raw record; derive normalization only from valid frames.
    for row in records:
        if row['selected_person'] is not None:
            x=row['persons'][row['selected_person']]
            xy,cf=np.asarray(x['coco17_xy']),np.asarray(x['coco17_score'])
            if xy.shape!=(17,2) or cf.shape!=(17,) or not np.isfinite(xy).all() or not np.isfinite(cf).all():
                raise ValueError('Malformed or nonfinite pose')
    view=copy.deepcopy(raw);view['frames']=view['frames'][:count]
    xy=np.full((count,17,2),np.nan);confidence=np.zeros((count,17))
    for i,row in enumerate(view['frames']):
        if row['selected_person'] is not None:
            person=row['persons'][row['selected_person']]
            xy[i],confidence[i]=person['coco17_xy'],person['coco17_score']
    return metrics.pose_features(xy,confidence,np.arange(count)/24,np.arange(count),view,threshold)

def evaluate(reference, native, auto, pair):
    case=next(c for c in P['cases'] if c['pair_id']==pair)
    result={'pair_id':pair,'effective_frames':case['effective_frames'],'physical_time_step_ms':1000/24,
            'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.json').read_bytes()).hexdigest(),
            'confidence_results':{},'paired_lag_summary':[]}
    for confidence in P['confidence_thresholds']:
        try:
            source=valid_view(reference,case['effective_frames'],confidence)
            edits={name:valid_view(raw,case['effective_frames'],confidence) for name,raw in [('native',native),('auto',auto)]}
        except ValueError as exc:
            if str(exc)!='Insufficient reliable torso anchors for scale normalization':raise
            result['confidence_results'][str(confidence)]={'status':'unknown_visibility','rows':[]};continue
        rows=[]
        for window in case['windows_inclusive']:
            for feature in P['features']:
                rows.append({'window':window,'feature':feature,
                    'diagnostics':{name:metrics.local_diagnostic(source,edit,window,24,feature) for name,edit in edits.items()},
                    'common_support':common_error(source,edits,window,feature)})
        result['confidence_results'][str(confidence)]={'status':'measured','rows':rows}
    for window in case['windows_inclusive']:
        for feature in P['features']:
            entry={'window':window,'feature':feature,'methods':{}}
            for method in P['methods']:
                lags=[]
                for confidence in P['confidence_thresholds']:
                    rows=result['confidence_results'][str(confidence)]['rows']
                    row=next((r for r in rows if r['window']==window and r['feature']==feature),None)
                    lags.append(row['diagnostics'][method]['reliable_lag_frames'] if row else None)
                valid=all(x is not None for x in lags) and abs(lags[0]-lags[1])<=3
                entry['methods'][method]={'status':'qualified_exploratory' if valid else 'unknown',
                    'lag_frames_at_confidence_03_05':lags,'lag_ms_at_confidence_03_05':[None if x is None else x*1000/24 for x in lags]}
            result['paired_lag_summary'].append(entry)
    return metrics.clean(result)
