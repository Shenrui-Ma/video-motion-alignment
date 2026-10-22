"""Whole-clip current-endpoint scan using frozen metrics and pairwise gain."""
import argparse,hashlib,json,time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"extensions"))
from H3AutomaticWindowRouter.geometry import LEGACY,Geometry
from pose_domain import validate_pose
from arm_features import features
import timing_metrics as m
from pairwise_gain import compare
FEATURES=('arm_direction','left_arm_direction','right_arm_direction')
CONFIDENCE=(.3,.5)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def valid_pose(path,geometry=LEGACY):
    return validate_pose(path,geometry)

def observe(source,target,index,geometry=LEGACY):
    if type(index) is not int or not 0<=index<20:raise ValueError('current physical index')
    raw={"source":valid_pose(source,geometry),"target":valid_pose(target,geometry)};start=time.monotonic()
    result={'schema':'r27-whole-timeline-observation-v1','physical_index':index,
            'source_pose_sha256':sha(source),'edited_pose_sha256':sha(target),
            'status':'measured','reasons':[],'windows':[],'thresholds':[.3,.5],
            'lag_sign':'positive means edited motion later','descriptor_scope':'bilateral/left/right arms only','observation_domain':geometry.domain_record}
    loaded={}
    for name,path in [('source',source),('target',target)]:
        for c in CONFIDENCE:
            loaded[name,c]=features(raw[name],geometry,c)
    for window in geometry.windows():
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
    result['complete_scan']={'descriptor_version':'r56-arm-bone-unit-v1',
                             'expected_rows':len(list(geometry.windows()))*len(FEATURES),
                             'actual_rows':len(result['windows']),'complete':True}
    result['scan_seconds']=time.monotonic()-start
    return m.clean(result)

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--pose',required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--output',required=True);p.add_argument('--geometry-case',help='frozen case JSON; absent only for141 compatibility');a=p.parse_args()
    geometry=Geometry.from_case(json.loads(Path(a.geometry_case).read_text())) if a.geometry_case else LEGACY
    result=observe(a.source,a.pose,a.index,geometry)
    with Path(a.output).open('x') as f:json.dump(result,f,allow_nan=False)
if __name__=='__main__':main()
