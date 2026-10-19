"""CPU-only proposal; not imported by any existing task or deployment."""
import importlib.util,math
from pathlib import Path
HELPER=Path('/Users/researcher/DevProjects/h3-timing-flexiact-h2a1-game4-repair-r116-host41-20261019/scripts/working_set_capacity.py')
spec=importlib.util.spec_from_file_location('reviewed_working_set',HELPER);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
GIB=2**30

def assess(snapshot,stage='entry'):
 assert stage in ('entry','running')
 assert snapshot['uid']==1004 and snapshot['host_available_bytes']>=32*GIB
 parent=next(r for r in snapshot['ancestors'] if r['path']=='/user.slice')
 assert (parent['high_bytes'],parent['max_bytes'])==(100*GIB,112*GIB)
 rows=[];fails=[]
 for r in snapshot['ancestors']:
  if r.get('high_bytes') is None and r.get('max_bytes') is None:continue
  cur=r['current_bytes'];assert type(cur)is int and cur>=0
  clean,credit=helper.file_credit(r['stat'],6*GIB);credit=min(credit,cur);adjusted=cur-credit
  h={k:r[k+'_bytes']-adjusted for k in ('high','max') if r.get(k+'_bytes')is not None}
  raw={k:r[k+'_bytes']-cur for k in h}
  if stage=='entry':
   fails.extend(r['path']+' adjusted '+k+' below 12GiB' for k,v in h.items() if v<12*GIB)
  elif h.get('max',float('inf'))<8*GIB:fails.append(r['path']+' adjusted max below 8GiB')
  # Preserve the proven hard-limit reserve even after granting clean-cache credit.
  if raw.get('max',float('inf'))<8*GIB:fails.append(r['path']+' raw max below 8GiB')
  for kind in ('some','full'):
   p=r['pressure'][kind]['avg10'];assert isinstance(p,(int,float)) and math.isfinite(p) and 0<=p<=100
   if stage=='entry' and p>1:fails.append(r['path']+' PSI above 1')
  for key in ('oom','oom_kill'):assert type(r['events'][key])is int and r['events'][key]>=0
  rows.append(dict(path=r['path'],raw_headroom=raw,adjusted_headroom=h,clean_unmapped=clean,credit=credit,retained_file_cache=6*GIB))
 assert rows
 return dict(passed=not fails,failures=fails,rows=rows,stage=stage,administrative_proposal_only=True)
