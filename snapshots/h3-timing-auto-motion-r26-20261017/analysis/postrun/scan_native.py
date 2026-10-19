"""R26 outer binding around the existing all-window pose diagnostic."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
NUMERIC=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016/scripts/timing_metrics.py')
NUMERIC_SHA='eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'
FEATURES=('arm_direction','left_arm_direction','right_arm_direction')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def compact(d):
    return {k:v for k,v in d.items() if k != 'curve'} | {'curve':[
        {k:v for k,v in row.items() if k not in ('source_frames','per_frame_error')}
        for row in d['curve']]}
def windows(last):
 for length in (16,32):
  for start in sorted(set(range(0,last-length+2,4))|{last-length+1}):yield [start,start+length-1]
def classify(ls):
 status='unknown'
 if all(x is not None for x in ls) and abs(ls[0]-ls[1])<=2:
  if min(ls)>2:status='delayed_candidate'
  elif max(ls)<-2:status='advanced_candidate'
  elif all(abs(x)<=2 for x in ls):status='aligned'
 return status

def evaluate(source_path,target_path,output,run):
 if digest(NUMERIC)!=NUMERIC_SHA:raise ValueError('frozen numeric module changed')
 spec=importlib.util.spec_from_file_location('frozen_metrics',NUMERIC);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 inputs={str(p):digest(p) for p in (source_path,target_path)};source={};target={};errors={};started=time.time()
 for c in (.3,.5):
  try:source[c]=mod.load_pose(source_path,c);target[c]=mod.load_pose(target_path,c)
  except ValueError as e:
   if 'Insufficient reliable torso anchors for scale normalization' not in str(e):raise
   errors[str(c)]=str(e);source[c]=target[c]=None
 raw=json.loads(Path(source_path).read_text());last=raw['frames'][-1]['frame']
 if last!=140 or [v['frame'] for v in raw['frames']]!=list(range(141)):raise ValueError('source must contain exact141 physical frames')
 rows=[];identity=[]
 for w in windows(last):
  for feature in FEATURES:
   ds=[]
   for c in (.3,.5):
    if source[c] is None:ds.append({'reliable_lag_frames':None,'curve':[],'status':'unknown_scale','reason':errors[str(c)]});continue
    d=mod.local_diagnostic(source[c],target[c],w,24,feature)
    if len(d['curve'])!=49:raise ValueError('missing full49 lag curve')
    ds.append(d)
   ls=[d['reliable_lag_frames'] for d in ds];rows.append({'window':w,'feature':feature,'status':classify(ls),'measurements':dict(zip(('0.3','0.5'),map(compact,ds)))})
   if source[.3] is None:identity.append({'window':w,'feature':feature,'lag':None,'reason':errors['0.3']});continue
   di=mod.local_diagnostic(source[.3],source[.3],w,24,feature);li=di['reliable_lag_frames']
   if li not in (None,0):raise RuntimeError('Identity self-check nonzero reliable lag')
   identity.append({'window':w,'feature':feature,'lag':li})
 summary={s:sum(x['status']==s for x in rows) for s in ('delayed_candidate','advanced_candidate','aligned','unknown')}
 covered={s:sorted({i for x in rows if x['status']==s for i in range(x['window'][0],x['window'][1]+1)}) for s in ('delayed_candidate','advanced_candidate')}
 for p,h in inputs.items():
  if digest(p)!=h:raise ValueError('pose input changed during scan')
 payload=mod.clean({'run_id':run,'source':str(source_path),'target':str(target_path),'inputs':inputs,'numeric_sha256':NUMERIC_SHA,'script_sha256':digest(__file__),'summary':summary,'candidate_covered_frames':covered,'identity_checks':identity,'windows':rows,'scale_unknown':errors,'elapsed_seconds':time.time()-started,'cpu_only':True,'limitations':['186 correlated part/windows, not independent videos.','Candidates require separate visual interpretation.','Selected-source tracking inherits full-source context.','No intermediate pose or online feedback is evaluated here.']})
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 with (output/'RESULTS.json').open('x') as f:json.dump(payload,f,allow_nan=False)
 (output/'SUMMARY.json').write_text(json.dumps({'run_id':run,'summary':summary,'candidate_covered_frames':covered,'scale_unknown':errors,'results_sha256':digest(output/'RESULTS.json')},indent=2)+'\n');print(json.dumps(summary),flush=True)
 return payload
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--target',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--run',required=True);a=p.parse_args();evaluate(a.source,a.target,a.output,a.run)
