"""Host9 read-only host RAM/cgroup-v1 admission; no CUDA or model imports."""
from pathlib import Path
import json,time
GIB=1024**3
ROOT=Path(__file__).resolve().parents[1]
def snapshot():
 mem={k:v.strip() for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
 available=int(mem['MemAvailable'].split()[0])*1024; rows=[]
 for line in Path('/proc/self/cgroup').read_text().splitlines():
  _,controllers,rel=line.split(':',2)
  if 'memory' in controllers.split(','):
   path=Path('/sys/fs/cgroup/memory')/rel.lstrip('/')
   for folder in (path,*path.parents):
    if not folder.is_relative_to('/sys/fs/cgroup/memory'):break
    limit=folder/'memory.limit_in_bytes';usage=folder/'memory.usage_in_bytes'
    if limit.exists() and usage.exists():
     n,u=int(limit.read_text()),int(usage.read_text());rows.append({'path':str(folder),'limit_bytes':n,'usage_bytes':u,'free_bytes':max(0,n-u)})
 return {'host_available_bytes':available,'ancestors':rows,'observed_unix':time.time()}
def check(root=ROOT):
 v=snapshot();required=20*GIB
 if v['host_available_bytes']<required or any(x['free_bytes']<required for x in v['ancestors']):raise RuntimeError('host9 RAM/cgroup headroom below20GiB')
 return dict(v,admitted=True,required_free_bytes=required)
def observe(root=ROOT):return snapshot()
