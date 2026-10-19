"""Single short MF tracker; raw headroom admission, PSI observed, no limit changes."""
import importlib.util,math
from pathlib import Path
GIB=2**30
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('mf_cgroup_snapshot',ROOT/'audit/cgroup_memory.py');cg=importlib.util.module_from_spec(s);s.loader.exec_module(cg)
def assess(v,raw_required_gib):
 assert raw_required_gib in (8,12)
 assert v['uid']==1004 and v['host_available_bytes']>=32*GIB,'host/UID capacity'
 parent=next(r for r in v['ancestors'] if r['path']=='/user.slice')
 assert (parent['high_bytes'],parent['max_bytes'])==(100*GIB,112*GIB),'parent limits changed'
 rows=[]
 for r in v['ancestors']:
  if r.get('high_bytes') is None and r.get('max_bytes') is None:continue
  assert type(r['current_bytes']) is int and r['current_bytes']>=0,'invalid memory.current'
  if raw_required_gib==12 and r.get('high_bytes') is not None:assert r['high_bytes']-r['current_bytes']>=12*GIB,'raw high headroom'
  if r.get('max_bytes') is not None:assert r['max_bytes']-r['current_bytes']>=raw_required_gib*GIB,'raw max headroom'
  for kind in ['some','full']:
   x=r['pressure'][kind]['avg10'];assert isinstance(x,(int,float)) and math.isfinite(x) and x>=0,'invalid memory pressure'
  for key in ['oom','oom_kill']:
   assert type(r['events'].get(key)) is int and r['events'][key]>=0,'invalid OOM counter'
  rows.append({'path':r['path'],'raw_high_headroom':r['high_bytes']-r['current_bytes'] if r.get('high_bytes') is not None else None,'raw_max_headroom':r['max_bytes']-r['current_bytes'] if r.get('max_bytes') is not None else None})
 assert rows,'no finite ancestor'
 return {'passed':True,'raw_required_gib':raw_required_gib,'raw_high_initial_gib':12,'PSI_observation_only':True,'cache_credit_bytes':0,'rows':rows,'snapshot':v}
def check(raw_required_gib):return assess(cg.snapshot(),raw_required_gib)
