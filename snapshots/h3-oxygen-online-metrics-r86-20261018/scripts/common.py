"""R86 media-only readout of root-verified online execution."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN='r86_short_0252_seed2026101701_visible_only'
SOURCE='short_0252'
def require(ok,message):
 if not ok:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def bound(path):return {'file':str(Path(path).resolve()),'sha256':sha(path)}
def save(path,value,replace=False):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 if not replace:require(not p.exists(),'receipt exists: '+str(p))
 tmp=p.with_name(p.name+'.tmp.'+str(os.getpid()));tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def config():return read(ROOT/'configs/contract.json')
def validate_static():
 for name,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/name)==digest,'consumer file changed: '+name)
 return config()
def safe_remote(path,subdir=None):
 p=Path(path);root=Path(config()['producer_remote']);base=root/subdir if subdir else root
 require(p.is_absolute() and '..' not in p.parts and p.is_relative_to(base),'remote path outside bound task');return p

def verify_gate(g,owner):
 cfg=config()
 require(g.get('schema')=='r86-online-runtime-gate-v1' and g.get('passed') is True and g.get('status')=='pass','actual complete online gate required')
 require(g.get('producer_manifest_sha256')==cfg['producer_seal_sha256'] and g.get('protocol_sha256')==cfg['protocol_sha256'],'gate science/manifest differs')
 require(g.get('service_record')==owner and g.get('cleanup_verified') is True,'gate service/release differs')
 require(g.get('partial_batch') is False and g.get('planned_denominator')==1 and g.get('planned_sources')==1 and g.get('new_arms')==1 and g.get('Native_reused_from_R73') is True,'single online/reused Native scope differs')
 require(g.get('runtime_integrity_only') is True and g.get('new_method_claim') is False,'integrity/effectiveness scope differs')
 cases=g.get('cases');require(isinstance(cases,list) and len(cases)==1,'single online case required');case=cases[0]
 require(case.get('run')==RUN and case.get('arm')=='visible_only' and g.get('verified_runs')==[RUN],'online run differs')
 mask=case['mask'];require(mask==sorted(set(mask)) and all(type(x) is int and 1<=x<=19 for x in mask),'invalid online ON mask')
 require(case['first_on']==(mask[0] if mask else None) and case['NFE']==20+len(mask) and case['updates']==20 and case['observations']==20,'actual online counts differ')
 require(case['all_OFF_final_exact'] is (not bool(mask)),'allOFF endpoint claim differs')
 clean=case['independent_parent_inputs'];require(clean['actual_clean_inputs_equal'] is True and clean['initial_video_audio_noise_equal'] is True,'historical input equality missing')
 require(len(clean['clean_tensor_pairs'])==6 and all(x['tensor_equal'] is True for x in clean['clean_tensor_pairs']),'six actual clean tensor pairs missing')
 prefix=case['independent_native_prefix'];end=mask[0]+1 if mask else 20
 require([x['physical_index'] for x in prefix]==list(range(end)) and all(x['actual_video_audio_tensor_equal'] is True for x in prefix),'actual causal Native prefix differs')
 decision=case['decision_records'];require(decision['status']=='DECISIONS_AND_TRANSACTION_RECORDS_PASS' and decision['active_indices']==mask and decision['first_intervention']==case['first_on'],'decision gate mismatch')
 props=g['video']['properties'];require((props['width'],props['height'],str(props['nb_read_frames']),props['avg_frame_rate'])==(1312,736,'107','24/1') and g['valid_frames']==98,'actual output geometry differs');safe_remote(g['video']['file'],'output')
 require(g['spatial_selection']=='source-specified xcenter .40-.75' and g['automatic_scope']=='online temporal window/start/stop','actor/automatic scope differs')
 require([r['index'] for r in g['raw_filtered_pose_binding']]==list(range(20)),'raw adult selection records incomplete')
 require(g['efficiency']['NFE']==case['NFE'] and [r['index'] for r in g['efficiency']['per_step']]==list(range(20)),'actual efficiency record incomplete')
 return case

def read_decisions(audit,case):
 """Summarize verified records; never recompute policy or import offline replay."""
 require(audit.get('status')=='complete','unfinished online audit');c=audit['counterfactual'];mask=case['mask']
 require(c['policy']=='visible_only' and c['full_physical_indices']==mask and c['actual_model_nfe']==case['NFE'],'audit/gate mask mismatch')
 require(c['actual_euler_updates']==c['callback_count']==20 and len(c['steps'])==len(c['measurements'])==20,'complete20 actual steps required')
 require(audit['completed_forward_calls']==case['NFE'] and audit['completed_calls']==50*case['NFE'] and audit['routed_calls']==50*len(mask),'actual routing counts differ')
 require([m['physical_index'] for m in c['measurements']]==list(range(20)),'observations incomplete/duplicated')
 require(len(c['branches'])==case['NFE'],'branch count differs');rows=[]
 for i,step in enumerate(c['steps']):
  d=step['decision'];m=c['measurements'][i];on=i in mask
  require(step['physical_index']==d['index']==i and d['arm']=='visible_only' and d['chosen_full'] is on and step['callback_observed_once'] is True,'step/decision index mismatch')
  require(step['selected_branch']==('full' if on else 'native') and d['observation_complete'] is True,'chosen branch or complete observation missing')
  require(d['control_state']==('visible' if on else 'native') and d['route_alpha']==(1.0 if on else 0.0),'online routing strength differs')
  require(d['spatial_support']=='all_spatial_queries','spatial attention support differs')
  windows=d['physical_intervals'];require(bool(windows)==on and bool(d['latent_bins'])==on,'active support differs')
  require(not(on and d['all_unknown'] is True),'UNKNOWN cannot trigger visible-only route')
  for w in windows:require(len(w)==2 and all(type(x) is int for x in w) and 0<=w[0]<=w[1]<98,'physical action window outside valid prefix')
  require(m['status']=='complete' and m['observer']['physical_index']==i,'actual observer status/index differs')
  rows.append({'denoising_index':i,'ON':on,'physical_intervals':windows,'seconds_inclusive':[[a/24,b/24] for a,b in windows],'selected':d['selected'],'candidate_groups':d['candidate_groups'],'latent_bins':d['latent_bins'],'bin_coverage':d['bin_coverage'],'reason':d['reason'],'all_unknown':d['all_unknown'],'reliable_rows':d['reliable_rows'],'total_rows':d['total_rows'],'measurement_status':d['measurement_status'],'request_sha256':m['request_sha256'],'response_sha256':m['response_sha256']})
 intervals=[]
 for i in mask:
  if intervals and intervals[-1][1]+1==i:intervals[-1][1]=i
  else:intervals.append([i,i])
 return {'source':'actual R86 audit/counterfactual; not R81 offline replay','actual_ON_indices':mask,'actual_ON_denoising_intervals_inclusive':intervals,'first_ON':case['first_on'],'actual_OFF_indices':[i for i in range(20) if i not in mask],'rows':rows,'NFE':case['NFE'],'Euler_updates':20,'effectiveness':'UNREVIEWED','manual_spatial_actor_bounds':[.4,.75],'attention_spatial_support':'all_spatial_queries'}

def verify_intake():
 parent=ROOT/'incoming';receipt=read(parent/'COLLECTION.json');require(receipt['execution_binding_sha256']==sha(ROOT/'audit/EXECUTION_BINDING.json'),'execution binding changed')
 for rel,digest in receipt['files'].items():require(sha(parent/rel)==digest,'intake file changed: '+rel)
 owner=read(ROOT/'audit/EXECUTION_BINDING.json')['owner'];g=read(parent/'ONLINE_RUNTIME_GATE.json');case=verify_gate(g,owner);require(sha(parent/'online.mp4')==g['video']['sha256'],'online video changed')
 return g,case
