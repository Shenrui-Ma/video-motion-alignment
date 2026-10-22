"""Post-hoc boundary candidate replay on the fixed R133 trajectory; no inference."""
import hashlib,json,sys,time,types
from pathlib import Path
ROOT=Path('/data4/researcher/h3_runs/timing_oxygen_online_r133_20261020')
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
package=types.ModuleType('H3AutomaticWindowRouter')
package.__path__=[str(ROOT/'extensions/H3AutomaticWindowRouter')]
sys.modules['H3AutomaticWindowRouter']=package
import arm_features,scan_current_pose,content_visibility
from H3AutomaticWindowRouter.geometry import Geometry
from H3AutomaticWindowRouter.selector import Controller
from H3AutomaticWindowRouter.automatic_window_policy import candidate
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 start=time.monotonic();case=json.loads((ROOT/'configs/protocol.json').read_text())['cases'][0]
 geometry=Geometry.from_case(case);source=ROOT/'configs/source.pose.json'
 path=ROOT/'audit/counterfactual/r133_short_0252_seed2026101703_visible_only.json'
 audit=json.loads(path.read_text())['counterfactual'];assert len(audit['steps'])==9
 original=Controller(geometry,arm='visible_only');filtered=Controller(geometry,arm='visible_only')
 scan_current_pose.features=lambda raw,g,c:content_visibility.features(raw,g,c,case['evaluation_crop_xywh'],arm_features)
 rows=[]
 for index in range(9):
  measurement=audit['measurements'][index]
  old=original.select(index,measurement)
  assert all(audit['steps'][index]['decision'][k]==v for k,v in old.items())
  response_path=Path(measurement['response_file']);assert sha(response_path)==measurement['response_sha256']
  response=json.loads(response_path.read_text());pose=Path(response['pose']['file']);assert sha(pose)==response['pose']['sha256']
  scan=scan_current_pose.observe(source,pose,index,geometry)
  scan_path=OUT/f'step{index:03d}_BOUNDARY_SCAN.json';save(scan_path,scan)
  diagnostic=dict(measurement,observer=scan)
  new=filtered.select(index,diagnostic)
  fields=('active','chosen_full','physical_intervals','latent_bins','selected','reason')
  differences={k:{'actual':old[k],'posthoc_boundary':new[k]} for k in fields if old[k]!=new[k]}
  rows.append({'index':index,'source_pose_sha256':sha(source),'prediction_pose_sha256':sha(pose),'actual_response_sha256':sha(response_path),'boundary_scan':{'file':str(scan_path),'sha256':sha(scan_path)},'actual_decision':{k:old[k] for k in fields},'boundary_decision':{k:new[k] for k in fields},'differences':differences,'actual_qualifying_windows':sum(candidate(r) is not None for r in measurement['observer']['windows']),'boundary_qualifying_windows':sum(candidate(r) is not None for r in scan['windows'])})
  print(json.dumps({'index':index,'actual_on':old['active'],'candidate_on':new['active'],'changed_fields':list(differences)}),flush=True)
 result={'schema':'r133-fixed-trajectory-posthoc-content-boundary-replay-v1','scope':'Existing ordinary predictions only; counterfactual controller replay is not a rerun of the modified closed-loop trajectory. No current producer imports this candidate.','source_audit':{'file':str(path),'sha256':sha(path)},'module_sha256':sha(OUT/'content_visibility.py'),'frozen_arm_features_sha256':sha(ROOT/'scripts/arm_features.py'),'frozen_controller_sha256':sha(ROOT/'extensions/H3AutomaticWindowRouter/selector.py'),'thresholds':[.3,.5],'crop_xywh':case['evaluation_crop_xywh'],'original_policy_replay_exact':True,'logical_indices':list(range(9)),'actual_ON_indices':[r['index'] for r in rows if r['actual_decision']['active']],'boundary_ON_indices':[r['index'] for r in rows if r['boundary_decision']['active']],'changed_indices':[r['index'] for r in rows if r['differences']],'rows':rows,'CPU_seconds':time.monotonic()-start,'new_pose_extraction':False,'GPU_started':False}
 save(OUT/'RESULT.json',result);print(json.dumps({'result_sha256':sha(OUT/'RESULT.json'),'changed_indices':result['changed_indices'],'actual_ON':result['actual_ON_indices'],'candidate_ON':result['boundary_ON_indices'],'CPU_seconds':result['CPU_seconds']}))
if __name__=='__main__':main()
