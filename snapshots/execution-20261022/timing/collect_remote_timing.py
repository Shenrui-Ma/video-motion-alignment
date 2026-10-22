"""Read-only small-log collection; no model files or video transfers."""
import concurrent.futures
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).parent
BASE = Path('/Users/researcher/DevProjects')
TARGETS = {'short_0252','short_0358','long_0039','long_0059','short_0085','short_0274'}
requests = {}
for directory in ['h3-guidance-schedule-eval-r149-20261020','h3-guidance-schedule-eval-r150-20261021']:
    for case in json.loads((BASE/directory/'EVALUATION_MANIFEST.json').read_text())['cases']:
        if case['source_id'] not in TARGETS:
            continue
        gate = json.loads(Path(case['historical_pair_gate']['file']).read_text())
        runtime = gate['runtime_profile']
        requests.setdefault(runtime['host'], {}).setdefault(runtime['remote_root'], []).extend(v['run_id'] for v in gate['runs'].values())

REMOTE = '''
import hashlib,json,pathlib
requests=REQUESTS
out=[]
for root,ids in requests.items():
 p=pathlib.Path(root);log=p/'logs/comfyui.log'
 record={'remote_root':root,'exists':p.exists(),'job_records':[],'sampling_manifests':{}}
 if log.exists() and log.stat().st_size<3000000:
  raw=log.read_bytes();record.update(log_path=str(log),log_bytes=len(raw),log_sha256=hashlib.sha256(raw).hexdigest(),log_text=raw.decode(errors='replace'))
 else:record['log_error']='missing or exceeds 3 MB collection limit'
 for f in (p/'logs').glob('*_job.json'):
  try:
   d=json.loads(f.read_text());selected={k:v for k,v in d.items() if k in ['name','run_id','submitted_unix','finished_unix','completed_unix','status','prompt_id','graph_sha256','wall_seconds','elapsed_seconds','history_file']}
   selected['file']=str(f);selected['sha256']=hashlib.sha256(f.read_bytes()).hexdigest();record['job_records'].append(selected)
  except Exception as exc:record['job_records'].append({'file':str(f),'error':str(exc)})
 for ident in ids:
  f=p/'audit/x0'/ident/'manifest.json'
  if f.exists():
   d=json.loads(f.read_text());record['sampling_manifests'][ident]={'file':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'keys':list(d),'summary':{k:v for k,v in d.items() if k not in ['snapshots','records','captures','steps']},'first_items':{k:v[:2] for k,v in d.items() if isinstance(v,list)}}
 out.append(record)
print(json.dumps(out,ensure_ascii=False))
'''

def fetch(host, items):
    code = REMOTE.replace('REQUESTS', repr(items))
    result = subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3',host,'python3','-'],input=code,text=True,capture_output=True,timeout=180)
    dest = ROOT / ('remote_' + host + '.json')
    if result.returncode:
        record={'host':host,'error':result.stderr[-2000:],'returncode':result.returncode}
    else:
        record={'host':host,'roots':json.loads(result.stdout),'stderr':result.stderr[-1000:]}
    dest.write_text(json.dumps(record,ensure_ascii=False,indent=2))
    return host, result.returncode, dest.stat().st_size

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for result in pool.map(lambda x: fetch(*x), requests.items()):
        print(result)
