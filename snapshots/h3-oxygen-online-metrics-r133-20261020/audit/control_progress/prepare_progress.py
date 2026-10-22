"""Read existing actual controller records; no new measurement or interpolation."""
import argparse, hashlib, json, math
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(path,partial):
 data=json.loads(path.read_text());cf=data.get('counterfactual',data)
 raw=cf['steps'];steps={int(s.get('physical_index',s.get('index'))):s for s in raw}
 assert len(steps)==len(raw) and set(steps)==set(range(len(steps)))
 if not partial:assert len(steps)==20,'Final progress requires20 actual completed updates'
 measurements={int(m['physical_index']):m for m in cf.get('measurements',[])}
 on=[i for i,s in steps.items() if s['decision']['active']]
 assert on,'No actual ON; no first-selected window can be declared'
 first=on[0];selected=steps[first]['decision']['selected'];assert len(selected)==1,'Explicit multi-window handling required'
 window=selected[0]['window'];feature=selected[0]['feature'];assert len(window)==2
 out=[]
 for i in range(20):
  s=steps.get(i);item={'step_1based':i+1,'physical_index_0based':i,'observed':s is not None,'actual_ON':None,'ON_frame_windows':[],'fixed_window_reliable_lags':{k:None for k in ['0.3','0.5']},'measurement_status':'not_observed'}
  if s is not None:
   d=s['decision'];item.update(actual_ON=d['active'],ON_frame_windows=d['physical_intervals'],decision_reason=d['reason'])
   rows=s.get('rows')
   if rows is None:rows=measurements[i]['observer']['windows']
   matching=[r for r in rows if r['window']==window and r['feature']==feature];assert len(matching)==1
   row=matching[0];item['measurement_status']=row.get('status');item['confidence_evidence']={}
   for key in ['0.3','0.5']:
    m=row['measurements'][key];lag=m.get('reliable_lag_frames');assert lag is None or (isinstance(lag,(int,float)) and math.isfinite(lag))
    item['fixed_window_reliable_lags'][key]=lag
    item['confidence_evidence'][key]={'status':m.get('status'),'flags':m.get('flags',[]),'reliable_lag_frames':lag}
  out.append(item)
 return {'schema':'r133-actual-control-progress-v1','input':{'file':str(path),'sha256':sha(path)},'partial':partial,'observed_completed_updates':len(steps),'planned_updates':20,'first_ON_index_0based':first,'fixed_window_frames_inclusive':window,'fixed_feature':feature,'confidence_thresholds':[0.3,0.5],'lag_band_frames':[-2,2],'observation_phase':'ordinary x0 observation before this Euler update; ON guidance applied afterwards','selection_rule':'window and anatomical feature fixed by first actual ON, not reselected at later steps','unknown_rule':'null stays a gap; no best-lag substitution or interpolation','display_axes':{'x':'denoising step1..20','upper_y':'actual ON physical frame window,24fps','lower_y':'reliable lag in physical frames'},'scope':'explanation of actual control trace; no final-video efficacy conclusion','rows':out}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--partial',action='store_true');a=p.parse_args();r=build(a.input,a.partial);a.output.parent.mkdir(parents=True,exist_ok=True);assert not a.output.exists();a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'file':str(a.output),'sha256':sha(a.output),'observed':r['observed_completed_updates'],'partial':a.partial}))
