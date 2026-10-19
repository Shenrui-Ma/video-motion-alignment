"""Two frozen rules on archived actual observations. No tensor/pose/model imports."""
import ast,copy,fcntl,hashlib,json,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
PROTOCOL_SHA='398bd3699006940622763419e3f5a3074ac8d92fc6e09f65a9953d799b8e6d5d'

def require(value,message):
 if not value:raise ValueError(message)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for part in iter(lambda:f.read(1048576),b''):h.update(part)
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
 with Path(path).open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def exact_file(path,record):
 require(Path(path).stat().st_size==record['bytes'],'input size changed: '+str(path))
 require(sha(path)==record['sha256'],'input SHA changed: '+str(path))
def modules(case):
 for record in case['code'].values():exact_file(record['path'],record)
 pol=case['code']['extensions/H3AutomaticWindowRouter/automatic_window_policy.py']['path']
 tree=ast.parse(Path(pol).read_text());require(not any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(tree)),'policy unexpectedly imports a module')
 ns={};exec(compile(tree,pol,'exec'),ns)
 lay=case['code']['extensions/H3TemporalRouter/layout.py']['path'];tree=ast.parse(Path(lay).read_text());names={'frame_spans','event_latent_range'}
 nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name in names) or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FRAME_PER_TOKEN' for t in n.targets))]
 require(len(nodes)==3,'frozen layout extraction');layout={};exec(compile(ast.Module(body=nodes,type_ignores=[]),lay,'exec'),layout)
 return ns,layout

def alternative(module,index,rows):
 groups=module['components'](rows,.5);selected=[g['representative'] for g in groups]
 return {'index':index,'groups':groups,'selected':selected,'physical_intervals':[r['window'] for r in selected],'active':bool(selected),'reason':'current_delayed_proposal' if selected else 'no_qualifying_delayed_proposal'}
def mapped(decision,layout):
 bins=set();mapping=[]
 for a,b in decision['physical_intervals']:
  lo,hi=layout['event_latent_range'](a,b,42);bins.update(range(lo,hi));mapping.append({'physical_interval':[a,b],'latent_interval_half_open':[lo,hi]})
 return {'chosen_full':bool(bins),'latent_bins':sorted(bins),'mapping':mapping}
def compact(d,layout):
 return {k:d[k] for k in ('index','selected','physical_intervals','active','reason')}|mapped(d,layout)|{'component_count':len(d['groups']),'components':[{'span':g['span'],'members':len(g['members']),'representative':g['representative']} for g in d['groups']]}
def test_rules(module,layout):
 def row(feature='left_arm_direction',window=(40,55),gain=.7,status='measured'):
  return {'status':status,'baseline':'delayed_candidate','min_gain':gain,'window':list(window),'feature':feature,'comparison':{str(c):{'proposal_lag':13,'null_comparisons':[{'null_cost':1.,'proposal_cost':.3}]} for c in (.3,.5)}}
 policy=module['Policy'](.5);r=row()
 require(not policy.update(0,[r])['active'] and alternative(module,0,[r])['active'],'first step persistence test')
 require(policy.update(1,[r])['active'],'compatible two steps')
 require(not policy.update(2,[row('right_arm_direction')])['active'],'shared arm requirement')
 require(not policy.update(3,[])['active'] and not alternative(module,3,[])['active'],'unknown OFF')
 require(not policy.update(4,[r])['active'],'unknown breaks persistence')
 require(not alternative(module,5,[row(gain=.5)])['active'],'strict gain threshold')
 require(not alternative(module,6,[row(status='unknown')])['active'],'unknown row rejected')
 a=alternative(module,7,[r]);m=mapped(a,layout);require(m['latent_bins']==list(range(*layout['event_latent_range'](40,55,42))),'same support mapping')
 return {'passed':True,'checks':8,'no_new_metric_or_model':True}
def chosen_set(d):return {(tuple(r['window']),r['feature']) for r in d['selected']}
def observation_digest(obs):
 # Existing producer-observer replay certificates use all numeric values except runtime timing.
 return hashlib.sha256(json.dumps({k:v for k,v in obs.items() if k!='scan_seconds'},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def run_case(case):
 started=time.perf_counter();cap=Path(case['archive']);module,layout=modules(case);tests=test_rules(module,layout)
 for name,key in [('FILE_INVENTORY.json','archive_inventory_sha256'),('DERIVED_FILES.json','derived_inventory_sha256'),('deploy_manifest.json','archived_producer_manifest_sha256'),('DECISION_LEDGER.json','decision_ledger_sha256'),('CPU_COMPLETE.json','completion_sha256')]:require(sha(cap/name)==case[key],'archive certificate changed: '+name)
 der=read(cap/'DERIVED_FILES.json');ledger=read(cap/'DECISION_LEDGER.json');require(len(ledger['rows'])==20,'ledger20 rows')
 policy=module['Policy'](.5);rows=[];first_difference=None
 for record,original in zip(case['observations'],ledger['rows']):
  n=record['index'];require(original['denoising_index']==n,'ledger index sequence')
  exact_file(record['path'],record['record']);exact_file(record['request'],record['request_record']);exact_file(record['response'],record['response_record'])
  obs=read(record['path']);req=read(record['request']);resp=read(record['response']);actual=original['decision']
  require(req['run_id']==case['run_id'] and req['branch']=='native' and req['physical_index']==n and resp['physical_index']==n,'current Native request binding')
  require(resp['status']=='complete' and resp['request_id']==req['request_id'],'completed same request')
  require(resp['observer']['sha256']==record['record']['sha256'] and resp['request_sha256']==record['request_record']['sha256'],'response observer/request SHA')
  require(actual['request_sha256']==record['request_record']['sha256'] and actual['response_sha256']==record['response_record']['sha256'],'actual decision request/response binding')
  require(req['nfe_index']==actual['native_nfe_index'] and req['nfe_index']==original['nfe_indices'][0] and req['sigma']==original['sigma'],'Native NFE/sigma binding')
  require(req['raw_stream_signatures']==original['native_raw_stream_signatures'],'actual Native endpoint pair')
  require(obs['schema']=='r27-whole-timeline-observation-v1' and obs['physical_index']==n and obs['thresholds']==[.3,.5],'observation schema/index/confidence')
  require(obs['status'] in ('measured','unknown_visibility'),'technical error not scientific UNKNOWN')
  require(obs['status']!='unknown_visibility' or not obs['windows'],'UNKNOWN rows must be empty')
  certname=f'observer_replay/{n:03d}.json';require(sha(cap/certname)==der[certname],'numeric replay certificate changed');cert=read(cap/certname)
  require(cert['passed'] is True and cert['index']==n and cert['all_numeric_values_equal'] is True,'numeric replay completion')
  require(cert['source_pose_sha256']==obs['source_pose_sha256'] and cert['pose_sha256']==obs['edited_pose_sha256']==resp['pose']['sha256'],'source/current pose binding')
  require(cert['scan_sha256']==cert['producer_observer_sha256'],'existing numeric replay mismatch')
  d=policy.update(n,obs['windows']);m=mapped(d,layout)
  if obs['status']=='unknown_visibility':d['reason']='unknown_visibility'
  for key,value in d.items():require(actual[key]==value,f'original policy mismatch {case["label"]}/{n}/{key}')
  for key,value in m.items():require(actual[key]==value,f'original support mismatch {case["label"]}/{n}/{key}')
  require(actual['measurement_status']==obs['status'] and actual['measurement_reasons']==obs['reasons'],'measurement status mismatch')
  require(original['chosen']==('full' if d['active'] else 'native'),'actual chosen branch mismatch')
  alt=alternative(module,n,obs['windows'])
  if obs['status']=='unknown_visibility':alt['reason']='unknown_visibility'
  require(alt['groups']==d['groups'],'ablation changed candidate grouping')
  require(chosen_set(d)<=chosen_set(alt),'no-persistence unexpectedly removes a current representative')
  before,after=compact(d,layout),compact(alt,layout);different=before['selected']!=after['selected']
  if different and first_difference is None:first_difference=n
  added=chosen_set(alt)-chosen_set(d)
  rows.append({'denoising_index':n,'actual_native_nfe_index':req['nfe_index'],'sigma':req['sigma'],'observation_status':obs['status'],'observation_rows':len(obs['windows']),'baseline_counts':{status:sum(r['baseline']==status for r in obs['windows']) for status in sorted({r['baseline'] for r in obs['windows']})},'original_reproduced_exact':True,'original':before,'without_persistence':after,'ON_changed':before['active']!=after['active'],'support_changed':different,'added_selected':[{'window':list(w),'feature':f} for w,f in sorted(added)],'added_bins':sorted(set(after['latent_bins'])-set(before['latent_bins'])),'removed_bins':sorted(set(before['latent_bins'])-set(after['latent_bins'])),'alternative_observation_is_causally_shared_prefix':first_difference is None or n<=first_difference,'observer_sha256':record['record']['sha256'],'request_sha256':record['request_record']['sha256'],'response_sha256':record['response_record']['sha256'],'numeric_replay_certificate_sha256':der[certname]})
  del obs,req,resp,original,actual
 original_active=[r['denoising_index'] for r in rows if r['original']['active']];alternative_active=[r['denoising_index'] for r in rows if r['without_persistence']['active']]
 require(original_active==ledger['active_indices'],'actual active indices mismatch')
 require(ledger['NFE']==20+len(original_active) and ledger['Euler_updates']==20,'actual NFE/Euler mismatch')
 result={'label':case['label'],'run_id':case['run_id'],'actual_archive':case['archive'],'passed':True,'synthetic_checks':tests,'exact_original_reproduced_steps':20,'actual_active_indices':original_active,'actual_Full_count':len(original_active),'actual_NFE':ledger['NFE'],'no_persistence_fixed_tape_active_indices':alternative_active,'no_persistence_fixed_tape_Full_count':len(alternative_active),'no_persistence_fixed_tape_implied_NFE_not_executed':20+len(alternative_active),'added_ON_indices':sorted(set(alternative_active)-set(original_active)),'removed_ON_indices':sorted(set(original_active)-set(alternative_active)),'support_changed_indices':[r['denoising_index'] for r in rows if r['support_changed']],'first_decision_divergence':first_difference,'normal_new_ON':bool(alternative_active) if case['label']=='R27_normal' else None,'rows':rows,'seconds':time.perf_counter()-started}
 return result

def main():
 require(sha(HERE/'PROTOCOL.json')==PROTOCOL_SHA,'protocol changed');protocol=read(HERE/'PROTOCOL.json')
 require(not (HERE/'RESULTS.json').exists(),'results are append-only; do not rerun successful evaluation')
 with Path(protocol['resources']['Mac_nonblocking_lock']).open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('CPU_BUSY_NO_EVALUATION');return 75
  start=time.perf_counter();results=[run_case(case) for case in protocol['cases']]
  versions={rel:{c['label']:c['code'][rel]['sha256'] for c in protocol['cases']} for rel in protocol['cases'][0]['code']}
  result={'schema':'persistence-ablation-replay-results-v1','protocol_sha256':PROTOCOL_SHA,'script_sha256':sha(__file__),'all_original_reproduction_passed':True,'versions':versions,'all_listed_versions_identical':all(len(set(d.values()))==1 for d in versions.values()),'cases':results,'wall_seconds':time.perf_counter()-start,'resource':'stdlib JSON only, one CPU process, Mac nonblocking lock; no GPU/model/pose/remote action','scope':protocol['interpretation']}
  save(HERE/'RESULTS.json',result)
  print(json.dumps({'passed':True,'wall_seconds':result['wall_seconds'],'cases':[{k:c[k] for k in ('label','actual_active_indices','no_persistence_fixed_tape_active_indices','added_ON_indices','support_changed_indices','normal_new_ON')} for c in results]}))
 return 0
if __name__=='__main__':
 try:sys.exit(main())
 except Exception:
  save(HERE/f'FAILURE_{time.time_ns()}.json',{'traceback':traceback.format_exc(),'protocol_sha256':PROTOCOL_SHA,'script_sha256':sha(__file__),'no_model_call':True});raise
