"""CPU source support accounting. Does not select lags or change any policy."""
import argparse, hashlib, importlib.util, json
from pathlib import Path
from types import SimpleNamespace
import numpy as np

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def spans(mask):
    spans=[];start=None
    for i,yes in enumerate(list(mask)+[False]):
        if yes and start is None:start=i
        if not yes and start is not None:spans.append([start,i-1]);start=None
    return spans

def count(mask):
    seq=spans(mask);best=max(seq,key=lambda x:x[1]-x[0]+1) if seq else None
    return {'frames':int(np.sum(mask)),'longest_span_inclusive':best,'longest_length':0 if best is None else best[1]-best[0]+1,'all_spans_inclusive':seq}

def assess(path,valid,arm_path,metric_path):
    raw=json.loads(Path(path).read_text()); records=raw['frames'][:valid]
    assert len(records)==valid and [r['frame'] for r in records]==list(range(valid))
    assert all(abs(r['time_s']-i/24)<1e-6 for i,r in enumerate(records))
    base=module(arm_path,'audit_arm_features');metrics=module(metric_path,'audit_timing_metrics');g=SimpleNamespace(valid_frames=valid)
    rawfeat=base.features(raw,g,.3);xy=rawfeat['xy'];conf=rawfeat['conf'];finite=np.isfinite(xy).all(axis=-1)
    canvas=finite&(xy[...,0]>=0)&(xy[...,0]<1312)&(xy[...,1]>=0)&(xy[...,1]<736)
    content=finite&(xy[...,0]>=16)&(xy[...,0]<1296)&(xy[...,1]>=8)&(xy[...,1]<728)
    joints={};support=[];common={};scales={}
    for name in ['nose','left_eye','right_eye','left_shoulder','right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist']:
        idx=raw['joint_order'].index(name);joints[name]={}
        for t in [.3,.5]:joints[name][str(t)]={'confidence_only':count(conf[:,idx]>=t),'inside_canvas':count(canvas[:,idx]&(conf[:,idx]>=t)),'inside_content':count(content[:,idx]&(conf[:,idx]>=t))}
    joints['neck']={'available':False,'reason':'COCO17 has no neck landmark; no derived landmark substituted'}
    for t in [.3,.5]:
        common[str(t)]=count(content[:,0]&content[:,9]&(conf[:,0]>=t)&(conf[:,9]>=t))
        mask=content[:,5]&content[:,6]&(conf[:,5]>=t)&(conf[:,6]>=t);d=np.linalg.norm(xy[:,5]-xy[:,6],axis=-1)[mask]
        scales[str(t)]={'count':len(d),'median_px':float(np.median(d)) if len(d) else None,'min_px':float(d.min()) if len(d) else None,'max_px':float(d.max()) if len(d) else None,'p10_px':float(np.quantile(d,.1)) if len(d) else None,'p90_px':float(np.quantile(d,.9)) if len(d) else None}
        for mode in ['confidence_only_original','content_valid_diagnostic']:
            features=base.features(raw,g,t)
            if mode=='content_valid_diagnostic':
                c=conf.copy();c[~content]=0;features=base.arm_features(xy,c,features['times'],features['frames'],raw,t)
            for length in [16,32]:
                starts=sorted(set(range(0,valid-length+1,4))|{valid-length})
                for feature in ['arm_direction','left_arm_direction','right_arm_direction']:
                    qualifying=[]
                    for start in starts:
                        row=metrics.pair_error(features,features,[start,start+length-1],0,feature)
                        if np.isfinite(row['error']) and row['coverage']>=.8 and row['valid_frame_count']>=8:
                            qualifying.append({'window':[start,start+length-1],'coverage':row['coverage'],'valid_frame_count':row['valid_frame_count']})
                    support.append({'mode':mode,'confidence':t,'window_length':length,'feature':feature,'possible_windows':len(starts),'qualifying_source_support_windows':len(qualifying),'windows':qualifying})
    examples=[]
    for frame in [95,112] if valid==144 else []:
        selected=records[frame]['selected_person'];person=records[frame]['persons'][selected];pts={}
        for name in ['nose','left_eye','right_eye','left_shoulder','right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist']:
            j=raw['joint_order'].index(name);a=person['coco17_xy'][j]
            pts[name]={'canvas_xy':a,'content_relative_xy':[a[0]-16,a[1]-8],'confidence':person['coco17_score'][j],'inside_content':bool(content[frame,j])}
        examples.append({'frame':frame,'time_s':frame/24,'points':pts})
    return {'schema':'r144-source-pose-support-v1','pose_file':str(path),'pose_sha256':sha(path),'video':raw['video'],'valid_frames':valid,'excluded_padding':list(range(valid,len(raw['frames']))),'crop_xywh':[16,8,1280,720],'selection_rule':raw['provenance']['selection_rule'],'person_ROI':None,'source_support_only':True,'definition':'same-source lag0 support with unchanged pair_error; eligibility needs coverage>=0.8 and valid_frames>=8; not a delayed candidate or ON decision','arm_features_sha256':sha(arm_path),'timing_metrics_sha256':sha(metric_path),'joint_coverage':joints,'nose_left_wrist_common_content':common,'shoulder_distance_px_descriptive':scales,'support':support,'representative_coordinates':examples,'GPU_started':False}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--pose',required=True);a.add_argument('--valid',type=int,required=True);a.add_argument('--arm',required=True);a.add_argument('--metrics',required=True);a.add_argument('--output',required=True);v=a.parse_args()
    result=assess(v.pose,v.valid,v.arm,v.metrics);Path(v.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':v.output,'sha256':sha(v.output),'valid':v.valid,'support_counts':[dict(mode=r['mode'],confidence=r['confidence'],window=r['window_length'],feature=r['feature'],qualified=r['qualifying_source_support_windows']) for r in result['support']]}))
