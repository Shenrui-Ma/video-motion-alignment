"""Whole-clip current-endpoint scan using frozen metrics and pairwise gain."""
import argparse,hashlib,json,time
from pathlib import Path
import timing_metrics as m
from pairwise_gain import compare
FEATURES=('arm_direction','left_arm_direction','right_arm_direction')
CONFIDENCE=(.3,.5)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def valid_pose(path):
    raw=json.loads(Path(path).read_text())
    v=raw['video']
    if (v['fps'],v['width'],v['height'],v['container_frame_count'])!=(24,1312,736,141):raise ValueError('pose geometry/timebase mismatch')
    frames=raw['frames']
    if len(frames)!=141 or [r['frame'] for r in frames]!=list(range(141)) or any(abs(r['time_s']-i/24)>1e-8 for i,r in enumerate(frames)):
        raise ValueError('pose frame/time index mismatch')
    for row in frames:
        selected=row['selected_person']
        if selected is not None:
            p=row['persons'][selected]
            if len(p['coco17_xy'])!=17 or any(len(v)!=2 for v in p['coco17_xy']) or len(p['coco17_score'])!=17:raise ValueError('malformed pose joints')
    return raw

def observe(source,target,index):
    if type(index) is not int or not 0<=index<20:raise ValueError('current physical index')
    valid_pose(source);valid_pose(target);start=time.monotonic()
    result={'schema':'r27-whole-timeline-observation-v1','physical_index':index,
            'source_pose_sha256':sha(source),'edited_pose_sha256':sha(target),
            'status':'measured','reasons':[],'windows':[],'thresholds':[.3,.5],
            'lag_sign':'positive means edited motion later','descriptor_scope':'bilateral/left/right arms only'}
    loaded={}
    for name,path in [('source',source),('target',target)]:
        for c in CONFIDENCE:
            try:loaded[name,c]=m.load_pose(path,c)
            except ValueError as e:
                if str(e)!='Insufficient reliable torso anchors for scale normalization':raise
                result['reasons'].append({'input':name,'confidence':c,'reason':str(e)})
    if result['reasons']:
        return result|{'status':'unknown_visibility','scan_seconds':time.monotonic()-start}
    for length in (16,32):
        starts=sorted(set(range(0,141-length+1,4))|{141-length})
        for startframe in starts:
            window=[startframe,startframe+length-1]
            for feature in FEATURES:
                ds={str(c):m.local_diagnostic(loaded['source',c],loaded['target',c],window,24,feature) for c in CONFIDENCE}
                lags=[d['reliable_lag_frames'] for d in ds.values()];baseline='unknown'
                if all(x is not None for x in lags) and abs(lags[0]-lags[1])<=2:
                    if min(lags)>2:baseline='delayed_candidate'
                    elif max(lags)<-2:baseline='advanced_candidate'
                    elif all(abs(x)<=2 for x in lags):baseline='aligned'
                out={'window':window,'feature':feature,'baseline':baseline,'measurements':ds}
                if baseline in ('delayed_candidate','advanced_candidate'):
                    gain={str(c):compare(loaded['source',c],loaded['target',c],window,ds[str(c)]['reliable_lag_frames'],feature) for c in CONFIDENCE}
                    out['comparison']=gain
                    if any(d['status']=='unknown' for d in gain.values()):out['status']='unknown'
                    else:out.update(status='measured',min_gain=min(d['min_gain'] for d in gain.values()))
                else:out['status']='baseline_'+baseline
                result['windows'].append(out)
    result['scan_seconds']=time.monotonic()-start
    return m.clean(result)

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--pose',required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result=observe(a.source,a.pose,a.index)
    with Path(a.output).open('x') as f:json.dump(result,f,allow_nan=False)
if __name__=='__main__':main()
