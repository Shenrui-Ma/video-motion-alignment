"""Append verified real experiments without changing existing jobs or processes."""
import hashlib,json,os,tempfile
from pathlib import Path

def append(root):
 root=Path(root); package=root/'extension2'
 ready=json.loads((package/'input_ready.json').read_text())
 assert ready['ready'] and ready['count']==10
 addition=json.loads((package/'jobs_append.json').read_text())['jobs']
 for job in addition:
  graph=root/job['graph']
  assert hashlib.sha256(graph.read_bytes()).hexdigest()==job['metadata']['graph_sha256'],job['id']
  assert Path(job['metadata']['source_video']).is_file(),job['id']
 manifest=root/'jobs.json'; current=json.loads(manifest.read_text()); old=list(current['jobs'])
 byid={j['id']:j for j in old}
 for j in addition:
  if j['id'] in byid:assert byid[j['id']]==j,'Conflicting existing job '+j['id']
  else:current['jobs'].append(j);byid[j['id']]=j
 assert current['jobs'][:len(old)]==old
 backup=package/'jobs_before_append.json'
 if not backup.exists():backup.write_bytes(manifest.read_bytes())
 fd,tmp=tempfile.mkstemp(prefix='.jobs-',suffix='.json',dir=root)
 with os.fdopen(fd,'w') as f:
  json.dump(current,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,manifest)
 print(json.dumps({'previous':len(old),'current':len(current['jobs']),'added':len(current['jobs'])-len(old)}))
if __name__=='__main__':
 import sys
 append(sys.argv[1])
