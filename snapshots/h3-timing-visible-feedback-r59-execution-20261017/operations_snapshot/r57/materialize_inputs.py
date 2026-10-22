"""Copy existing R54 bytes on the remote host; no download, transformation or GPU."""
import argparse,json,shutil
from pathlib import Path
from r57_contract import ROOT,REMOTE,read,sha

def materialize(root=ROOT):
 root=Path(root)
 if root.resolve()!=REMOTE.resolve():raise ValueError('remote materialization only; Mac uses external SHA-bound inputs')
 results={}
 for name,row in read(root/'configs/input_bindings.json').items():
  source=Path(row['remote_source']);target=root/'inputs'/name
  if source.is_symlink() or source.stat().st_size!=row['bytes'] or sha(source)!=row['sha256']:raise ValueError('parent input changed: '+name)
  target.parent.mkdir(exist_ok=True)
  if target.is_symlink():raise ValueError('input symlink rejected')
  if not target.exists():
   with source.open('rb') as inp,target.open('xb') as out:shutil.copyfileobj(inp,out)
  if sha(target)!=row['sha256']:raise ValueError('materialized bytes differ: '+name)
  results[name]={'sha256':row['sha256'],'bytes':row['bytes']}
 return {'passed':True,'inputs':results,'transformations':0}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(materialize(a.root),indent=2))
