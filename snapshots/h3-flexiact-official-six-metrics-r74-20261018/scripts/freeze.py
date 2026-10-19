"""Freeze independent consumer before CPU watcher/tracker launch."""
from pathlib import Path
import hashlib,json,time
ROOT=Path(__file__).resolve().parents[1]
def main():
 if (ROOT/'controls').exists() and any((ROOT/'controls').iterdir()):raise ValueError('tracking controls already exist')
 if (ROOT/'audit/watcher/STARTED.json').exists():raise ValueError('watcher already started')
 files={}
 for folder in ['scripts','configs','runtime','tests']:
  for p in (ROOT/folder).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':files[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 p=ROOT/'ROOT_SOURCE_CHECKPOINTS.json';files[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
 (ROOT/'CONSUMER_FREEZE.json').write_text(json.dumps({'schema':'r74-consumer-freeze-v1','files':files,'created_unix':time.time(),'source_track_policy':'fresh41 all3+12targets'},indent=2)+'\n');print(len(files))
if __name__=='__main__':main()
