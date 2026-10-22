import json,re,hashlib,datetime,subprocess
from pathlib import Path
BASE=Path('/Users/researcher/DevProjects');OUT=BASE/'h3-research-progress-notes-20261020/overnight_audit'
start=datetime.datetime.fromisoformat('2026-10-19T17:00:56.042+00:00').timestamp();wake=datetime.datetime.fromisoformat('2026-10-20T03:08:58.061+00:00').timestamp()
roots=[p for p in BASE.glob('h3-*') if p.is_dir() and any(int(x)>=100 for x in re.findall(r'(?:^|-)r(\d+)(?:-|$)',p.name)) and '-mf-' not in p.name]
files=[]
for p in roots:
 files.extend(Path(x) for x in subprocess.run(['rg','--files',str(p),'-g','*history*.json','-g','!runtime','-g','!node_modules'],capture_output=True,text=True).stdout.splitlines())
rows={};fail=[]
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def histories(d):
 if isinstance(d,dict) and 'prompt' in d and 'status' in d:yield d
 elif isinstance(d,dict):
  for v in d.values():
   if isinstance(v,dict) and 'prompt' in v and 'status' in v:yield v
for f in files:
 if f.stat().st_size>2000000:continue
 try:d=json.loads(f.read_text())
 except Exception:continue
 for h in histories(d):
  status=h.get('status',{});events=status.get('messages',[])
  successes=[v['timestamp']/1000 for typ,v in events if typ=='execution_success' and 'timestamp' in v]
  errors=[v['timestamp']/1000 for typ,v in events if typ in ('execution_error','execution_interrupted') and 'timestamp' in v]
  t=max(successes or errors or [0]);
  if t<start-3600:continue
  prompt=h.get('prompt',[]);pid=prompt[1] if isinstance(prompt,list) and len(prompt)>1 else None
  graph=prompt[2] if isinstance(prompt,list) and len(prompt)>2 else {}
  prefixes=[]
  for n in graph.values():
   inputs=n.get('inputs',{});prefix=inputs.get('filename_prefix')
   if isinstance(prefix,str) and re.search(r'r\d+_',prefix):prefixes.append(prefix)
  jobfile=f.with_name(f.name.replace('_history.json','_job.json')) if f.name.endswith('_history.json') else f.with_name('job.json')
  job={}
  if jobfile.exists():
   try:job=json.loads(jobfile.read_text())
   except Exception:pass
  run=job.get('name') or (prefixes[0] if prefixes else None)
  if not run:continue
  source=(job.get('case_binding') or {}).get('source_id') or next(iter(re.findall(r'(?:short|long)_\d{4}',run)),None)
  if source is None:source=run.split('_seed')[0].split('_',1)[-1]
  entry={'run_id':run,'source_id':source,'prompt_id':pid,'completed_unix':t,'completed_utc':datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat(),'completed_cst':datetime.datetime.fromtimestamp(t,datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'period':'sleep' if start<=t<wake else ('after_wake' if t>=wake else 'before_sleep'),'success':bool(successes) and status.get('completed') is True,'outputs':h.get('outputs'),'history_file':str(f),'history_sha256':sha(f),'job_file':str(jobfile) if jobfile.exists() else None,'method':run.rsplit('_',1)[-1]}
  key=(pid,run)
  if entry['success']:
   if key not in rows or '/incoming_pairs/' in str(f):rows[key]=entry
  elif key not in [(x['prompt_id'],x['run_id']) for x in fail]:fail.append(entry)
result={'cutoff_sleep_utc':'2026-10-19T17:00:56.042Z','cutoff_wake_utc':'2026-10-20T03:08:58.061Z','history_files_scanned':len(files),'roots_scanned':len(roots),'successful':sorted(rows.values(),key=lambda x:x['completed_unix']),'failed':fail}
(OUT/'HISTORY_SCAN.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for r in result['successful']:print(r['period'],r['completed_cst'][11:23],r['run_id'],Path(r['history_file']).parts[4])
print('FAIL',[(x['completed_cst'],x['run_id']) for x in fail])
print('TOTAL',len(rows))
