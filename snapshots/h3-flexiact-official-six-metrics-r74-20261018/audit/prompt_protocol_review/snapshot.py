"""Read-only snapshots: sealed plans and actual submitted/successful workflows."""
from pathlib import Path
import hashlib,json,shlex,subprocess,sys,time

ROOT=Path(__file__).resolve().parent
REMOTE_PROGRAM='''from pathlib import Path
import hashlib,json,sys,time
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for name in sys.argv[1:]:
 r=Path(name);c=json.loads((r/'configs/scientific_contract.json').read_text());cases=[]
 for item in c['cases']:
  run=item['run_id'];graph=r/'configs/graphs'/(run+'.json');g=json.loads(graph.read_text());actual={}
  for label,suffix in [('job','_job.json'),('history','_history.json')]:
   p=r/'logs'/(run+suffix)
   if p.is_file():actual[label]={'file':str(p),'sha256':sha(p),'data':json.loads(p.read_text())}
  cases.append({'case':item,'graph':g,'graph_sha256':sha(graph),'actual':actual})
 rows.append({'root':str(r),'contract_sha256':sha(r/'configs/scientific_contract.json'),'seal_sha256':sha(r/'deploy_manifest.json'),'cases':cases})
print(json.dumps({'time_unix':time.time(),'roots':rows}))
'''
GROUPS=[(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','H3_SERVER_B'],['/data3/researcher/h3_runs/timing_flexiact_prompt_pair_r72_20261018','/data3/researcher/h3_runs/timing_flexiact_official_six_r74_20261018'],'host41'),(['ssh','-J','H3_SERVER_B','-o','BatchMode=yes','-o','ConnectTimeout=15','H3_SERVER_A'],['/data5/researcher/h3_runs/timing_ivebench_expanded_r73_20261018'],'host9')]
def main():
 for ssh,roots,name in GROUPS:
  command=ssh+[shlex.join(['python3','-c',REMOTE_PROGRAM]+roots)]
  result=subprocess.run(command,check=True,capture_output=True,text=True,timeout=90)
  data=json.loads(result.stdout)
  (ROOT/(name+'_ACTUAL_SNAPSHOT.json')).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
  print(name,[(r['root'],len(r['cases']),sum('history' in x['actual'] for x in r['cases']),sum('job' in x['actual'] for x in r['cases'])) for r in data['roots']])
if __name__=='__main__':main()
