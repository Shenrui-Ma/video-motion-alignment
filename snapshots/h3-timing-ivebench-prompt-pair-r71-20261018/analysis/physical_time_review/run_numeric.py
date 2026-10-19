"""Apply frozen observers to completed videos without changing their thresholds."""
import argparse,gzip,hashlib,importlib.util,json,os,sys,types
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(ok,msg):
 if not ok:raise ValueError(msg)
def write_gz(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);check(not p.exists(),'preserve result')
 with gzip.open(p,'xt') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False)
def main(version):
 p=read(ROOT/'PROTOCOL.json')
 for b in p['bindings']:check(sha(ROOT/b['relative'])==b['sha256'],'frozen module changed')
 source=ROOT/'poses/source.pose.json';check(sha(source)==p['source_pose']['sha256'],'source pose changed')
 targets={}
 for arm in ['p0','p1']:
  path=ROOT/'poses'/arm/(arm+'.pose.json');receipt=read(path.parent/'COMPLETE.json');check(receipt['status']=='complete' and receipt['pose_sha256']==sha(path) and receipt['protocol_sha256']==sha(ROOT/'PROTOCOL.json'),'actual target receipt differs');targets[arm]=path
 if version=='physical':
  sys.path.insert(0,str(ROOT/'vendor/physical'));import evaluate90
  result=evaluate90.evaluate(read(source),read(targets['p0']),read(targets['p1']),'short_0210')
  write_gz(ROOT/'results/physical_original.json.gz',{'scope':p['scope'],'method_key_mapping':{'native':'p0','auto':'p1'},'protocol_sha256':sha(ROOT/'PROTOCOL.json'),'result':result})
 else:
  vendor=ROOT/'vendor'/version;sys.path.insert(0,str(vendor/'scripts'))
  package=types.ModuleType('H3AutomaticWindowRouter');package.__path__=[str(vendor/'extensions/H3AutomaticWindowRouter')];sys.modules['H3AutomaticWindowRouter']=package
  import scan_current_pose as scanner
  geometry=scanner.Geometry(width=1312,height=736,frames=90,fps=24,valid_frames=87)
  for arm,path in targets.items():
   result=scanner.observe(source,path,0,geometry)
   write_gz(ROOT/'results'/(version+'_'+arm+'.json.gz'),{'scope':p['scope'],'physical_index_0_is_offline_schema_placeholder':True,'arm':arm,'protocol_sha256':sha(ROOT/'PROTOCOL.json'),'observer':result})
 print(json.dumps({'version':version,'complete':True}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--version',choices=['original','visible','physical'],required=True);main(p.parse_args().version)
