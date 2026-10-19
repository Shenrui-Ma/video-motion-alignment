"""Short MF admission; does not alter tracking, reclaim memory, or change limits."""
import importlib.util
from pathlib import Path
GIB=2**30
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('mf_cgroup_snapshot',ROOT/'audit/cgroup_memory.py')
cg=importlib.util.module_from_spec(s);s.loader.exec_module(cg)
def assess(v,raw_required_gib):
 assert raw_required_gib in (8,12)
 assert v['uid']==1004 and v['host_available_bytes']>=32*GIB,'host/UID capacity'
 parent=next(r for r in v['ancestors'] if r['path']=='/user.slice')
 assert (parent['high_bytes'],parent['max_bytes'])==(100*GIB,112*GIB),'parent limits changed'
 rows=[]
 for r in v['ancestors']:
  if r.get('high_bytes') is None and r.get('max_bytes') is None:continue
  stat=r['stat']
  for k in ['file','shmem','active_file','inactive_file','file_mapped','file_dirty','file_writeback']:
   assert type(stat.get(k)) is int and stat[k]>=0,'invalid stat '+k
  disk=min(max(0,stat['file']-stat['shmem']),stat['active_file']+stat['inactive_file'])
  clean=max(0,disk-stat['file_mapped']-stat['file_dirty']-stat['file_writeback'])
  credit=min(r['current_bytes'],max(0,clean-6*GIB))
  adjusted=r['current_bytes']-credit
  if r.get('high_bytes') is not None:assert r['high_bytes']-adjusted>=12*GIB,'adjusted high headroom'
  if r.get('max_bytes') is not None:assert r['max_bytes']-r['current_bytes']>=raw_required_gib*GIB,'raw max headroom'
  for kind in ['some','full']:
   x=r['pressure'][kind]['avg10'];assert isinstance(x,(int,float)) and 0<=x<=5,'startup memory pressure'
  rows.append({'path':r['path'],'clean_unmapped':clean,'credited':credit,'adjusted_current':adjusted})
 assert rows,'no finite ancestor'
 return {'passed':True,'raw_required_gib':raw_required_gib,'adjusted_high_required_gib':12,'retained_cache_gib':6,'rows':rows,'snapshot':v}
def check(raw_required_gib):return assess(cg.snapshot(),raw_required_gib)
