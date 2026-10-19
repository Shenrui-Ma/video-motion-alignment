"""Bind this isolated service to the exact capacity controller generation."""
import hashlib,json,os,runpy,signal,sys,threading,time
from pathlib import Path
import process_identity
def identity(pid):
 return process_identity.hashed_record(process_identity.snapshot(pid),include_pid=True)
if __name__=='__main__':
 parent=json.loads(os.environ['H3_CAPACITY_PARENT']);own=os.getpid()
 if parent['uid']!=os.getuid() or identity(parent['pid'])!=parent or os.getpgid(own)!=own:raise RuntimeError('capacity controller identity/group differs')
 def watch():
  while identity(parent['pid'])==parent:time.sleep(.25)
  os.killpg(own,signal.SIGTERM)
 threading.Thread(target=watch,daemon=True).start()
 source=Path(sys.argv[1]);sys.argv=sys.argv[1:];sys.path.insert(0,str(source.parent));runpy.run_path(str(source),run_name='__main__')
