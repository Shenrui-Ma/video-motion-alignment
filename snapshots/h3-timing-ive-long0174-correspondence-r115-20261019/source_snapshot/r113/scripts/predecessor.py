"""Read-only exact release gate. Root supplies actual completed attempt names."""
import json,re
from pathlib import Path
from r113_contract import ROOT,read,sha,require

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
  elif spec['kind']=='screen':
   require(complete['all_sources_reviewed'] is True and complete['remaining_sources']==[],'predecessor screen incomplete')
   require([x['source_id'] for x in complete['terminal_sources']]==spec['required_sources'],'predecessor terminal sources differ')
  else:raise ValueError('unknown predecessor completion contract')
  rows.append({'key':spec['key'],'root':str(old),'actual_attempt':names[spec['key']],'owner':owner,'receipts':{key:{'file':str(path),'sha256':sha(path)} for key,path in paths.items()},'producer_seal_sha256':spec['producer_seal_sha256'],'passed':True})
 return {'passed':True,'predecessors':rows,'processes_observed':processes,'scope':'Read-only prerequisite. No signal, queue mutation or model loading.'}
