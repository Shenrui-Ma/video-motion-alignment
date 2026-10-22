"""Read-only exact release gate. Root supplies actual completed attempt names."""
import json,re
from pathlib import Path
from r123_contract import ROOT,read,sha,require

def attempts(values,keys):
 result={}
 for value in values:
  require(value.count('=')==1,'predecessor must be key=actual_attempt')
  key,attempt=value.split('=');require(key in keys and key not in result,'unknown or duplicate predecessor')
  require(re.fullmatch(r'[A-Za-z0-9_-]+',attempt) is not None,'unsafe predecessor attempt')
  result[key]=attempt
 require(set(result)==set(keys),'all actual predecessor attempt names are required')
 return result

def check(root=ROOT,attempt_names=(),current_identity=None,compute_processes=None):
 root=Path(root);config=read(root/'configs/predecessor.json');entries=config['required'];names=attempts(attempt_names,[x['key'] for x in entries])
 if current_identity is None or compute_processes is None:
  import service
  current_identity=service.current_identity if current_identity is None else current_identity
  compute_processes=service.compute_processes if compute_processes is None else compute_processes
 processes=compute_processes();rows=[]
 for spec in entries:
  old=Path(spec['remote_root']);attempt=old/'audit'/names[spec['key']]
  require(sha(old/'deploy_manifest.json')==spec['producer_seal_sha256'],'predecessor producer changed')
  runtime=read(old/'configs/runtime.json');require(sha(old/'configs/runtime.json')==spec['runtime_sha256'] and runtime['remote_root']==str(old),'predecessor runtime changed')
  if spec['kind']=='online_recovery':
   paths={n:attempt/(n+'.json') for n in ('STARTED','ROOT_EXIT_RECEIPT','COMPLETE_REVIEW_HOLD')};v={n:read(p) for n,p in paths.items()}
   owner=v['STARTED']['service'];ex=v['ROOT_EXIT_RECEIPT'];done=v['COMPLETE_REVIEW_HOLD'];clean=ex['service_cleanup'];children=ex['observer_children']
   require(owner==ex['service']==clean['service_record']==read(old/'processes/service.json'),'online predecessor owner differs')
   require(owner['identity']['uid']==runtime['uid'] and owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'],'online predecessor runtime differs')
   require(ex['passed'] is True and clean['process_absent'] is True and clean['own_compute_absent'] is True,'online predecessor release incomplete')
   require(children['all_exact_generations_absent'] is True and children['all_registered_CUDA_pids_absent'] is True,'online observer release incomplete')
   require(current_identity(owner['pid']) is None and not any(int(p['pid'])==owner['pid'] for p in processes),'online predecessor service remains')
   require(current_identity(v['STARTED']['root_controller']['pid']) is None,'online predecessor wrapper remains')
   gate_path=old/'analysis/postrun/ONLINE_RUNTIME_GATE.json';gate=read(gate_path)
   require(done['passed'] is True and done['run_id']==spec['required_run'] and sha(gate_path)==done['gate_sha256'],'online predecessor completion gate differs')
   require(gate['passed'] is True and gate['status']=='pass' and gate['cleanup_verified'] is True and gate['schema']=='r138-resumed-online-runtime-gate-v1','online predecessor runtime gate failed')
   require(gate['service_record']==owner and [c['run'] for c in gate['cases']]==[spec['required_run']],'online predecessor gate owner/run differs')
   rows.append({'key':spec['key'],'root':str(old),'actual_attempt':names[spec['key']],'owner':owner,'receipts':{k:{'file':str(p),'sha256':sha(p)} for k,p in paths.items()},'passed':True})
   continue
  paths={name:attempt/(name+'.json') for name in ('STARTED','ROOT_EXIT_RECEIPT','COMPLETE')};values={name:read(path) for name,path in paths.items()}
  owner=values['STARTED']['owner'];exit=values['ROOT_EXIT_RECEIPT'];complete=values['COMPLETE']
  require(read(old/'processes/service.json')==owner,'predecessor service generation changed')
  require(owner['identity']['uid']==runtime['uid'] and owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'],'predecessor owner runtime differs')
  require(str(old/'scripts/service_entry.py') in owner['identity']['cmdline'],'predecessor command binding differs')
  require(exit['passed'] is True and exit['owner']==owner and exit['process_absent'] is True and exit['CUDA_allocation_absent'] is True,'predecessor exact release receipt failed')
  require(current_identity(owner['pid']) is None,'predecessor process remains or PID reused')
  require(not any(int(p['pid'])==owner['pid'] for p in processes),'predecessor CUDA allocation remains')
  require(complete['passed'] is True and complete['GPU_released'] is True,'predecessor completion failed')
  if spec['kind']=='native':
   require(complete['jobs']==spec['required_runs'],'predecessor Native jobs differ')
   gate_path=old/spec['native_gate'];gate=read(gate_path)
   require(sha(gate_path)==complete['runtime_gate_sha256'] and gate['passed'] is True and all(gate['checks'].values()),'predecessor Native actual gate differs')
   job=read(old/'logs'/(spec['required_runs'][0]+'_job.json'))
   require(gate['run_id']==spec['required_runs'][0] and job['status']=='success' and job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'],'predecessor Native gate generation differs')
  elif spec['kind']=='single_control':
   require(complete['jobs']==spec['required_runs'] and complete['remaining']==[],'predecessor control jobs incomplete')
   for source in spec['required_sources']:
    entry=complete['gates'][source];gate_path=old/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json';gate=read(gate_path)
    require(Path(entry['file'])==gate_path and sha(gate_path)==entry['sha256'] and gate['passed'] is True and all(gate['checks'].values()),'predecessor paired gate differs')
    require(gate['service_owner']['pid']==owner['pid'] and gate['service_owner']['identity']==owner['identity'],'predecessor pair generation differs')
  elif spec['kind']=='two_new_arm_control':
   require(complete['jobs']==spec['required_runs'] and complete['remaining']==[], 'predecessor two-arm jobs incomplete')
   gate_path=old/spec['runtime_gate'];gate=read(gate_path)
   require(sha(gate_path)==complete['runtime_gate_sha256'] and gate.get('schema')==spec['gate_schema'] and gate['passed'] is True and all(gate['checks'].values()), 'predecessor two-arm gate differs')
   require(gate['service_owner']==owner and gate['producer_seal_sha256']==spec['producer_seal_sha256'] and gate['runtime_profile_sha256']==spec['runtime_sha256'], 'predecessor two-arm owner/runtime differs')
   require(gate['new_run_ids']==spec['required_runs'] and [gate['runs'][arm]['run_id'] for arm in spec['required_arms']]==spec['required_runs'], 'predecessor two-arm scope differs')
   for run in spec['required_runs']:
    job=read(old/'logs'/(run+'_job.json'))
    require(job['status']=='success' and job['name']==run and job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'], 'predecessor two-arm job generation differs')
  elif spec['kind']=='screen':
   require(complete['all_sources_reviewed'] is True and complete['remaining_sources']==[],'predecessor screen incomplete')
   require([x['source_id'] for x in complete['terminal_sources']]==spec['required_sources'],'predecessor terminal sources differ')
  elif spec['kind']=='two_seed_pairs':
   require(complete['jobs']==spec['required_runs'] and complete['remaining']==[], 'predecessor seed jobs incomplete')
   gate_path=old/spec['runtime_gate'];gate=read(gate_path)
   require(sha(gate_path)==complete['runtime_gate_sha256'] and gate['schema']==spec['gate_schema'] and gate['passed'] is True and all(gate['checks'].values()), 'predecessor seed gate differs')
   require(gate['service_owner']==owner and gate['producer_seal_sha256']==spec['producer_seal_sha256'] and gate['runtime_profile_sha256']==spec['runtime_sha256'], 'predecessor seed owner/runtime differs')
   require(gate['jobs']==spec['required_runs'] and gate['seeds']==spec['required_seeds'] and gate['source_id']==spec['required_source'], 'predecessor seed scope differs')
   require([x['seed'] for x in gate['pair_gate_receipts']]==spec['required_seeds'], 'predecessor pair list differs')
   for record in gate['pair_gate_receipts']:
    path=old/'analysis/postrun'/('seed'+str(record['seed']))/'PAIR_RUNTIME_GATE.json';pair=read(path)
    require(str(path)==record['file'] and sha(path)==record['sha256'] and pair['passed'] is True and all(pair['checks'].values()), 'predecessor per-seed gate differs')
    require(pair['service_owner']==owner and pair['seed']==record['seed'] and pair['source_id']==spec['required_source'], 'predecessor pair identity differs')
    require([pair['runs'][arm]['run_id'] for arm in ('native','fixed')]==[r for r in spec['required_runs'] if ('seed'+str(record['seed'])+'_') in r], 'predecessor per-seed runs differ')
   for run in spec['required_runs']:
    job=read(old/'logs'/(run+'_job.json'))
    require(job['status']=='success' and job['name']==run and job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'], 'predecessor seed job generation differs')
  else:raise ValueError('unknown predecessor completion contract')
  rows.append({'key':spec['key'],'root':str(old),'actual_attempt':names[spec['key']],'owner':owner,'receipts':{key:{'file':str(path),'sha256':sha(path)} for key,path in paths.items()},'producer_seal_sha256':spec['producer_seal_sha256'],'passed':True})
 mf=None
 if config.get('mf_final_release_path'):
  path=Path(config['mf_final_release_path']);value=read(path)
  flags=('passed','all_spawned_trackers_released','exact_processes_absent','exact_CUDA_allocations_absent')
  require(sha(path)==config['mf_final_release_sha256'],'registered MF final release changed')
  require(all(value.get(k) is True for k in flags), 'official MF final release incomplete')
  identities=value['wrapper_identities']+value['tracker_identities']
  require(identities, 'official MF identity list empty')
  for identity in identities:
   pid=int(identity['pid'])
   require(current_identity(pid) is None and not any(int(p['pid'])==pid for p in processes), 'official MF process or CUDA remains')
  mf={'file':str(path),'sha256':sha(path),'identities_verified_absent':len(identities),'passed':True}
 return {'passed':True,'predecessors':rows,'official_MF_release':mf,'processes_observed':processes,'scope':'Read-only prerequisite. No signal, queue mutation or model loading.'}
