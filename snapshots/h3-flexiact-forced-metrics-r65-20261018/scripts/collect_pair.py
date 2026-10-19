"""Copy only a completed, CPU-verified producer pair into a portable intake bundle."""
import argparse,shutil
from common import *
def collect(producer,source):
 producer=Path(producer).resolve();receipt=producer/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json';g=verify_gate(read(receipt),source);dest=ROOT/'incoming'/source
 require(not dest.exists(),'intake already exists; preserve old attempt');dest.mkdir(parents=True)
 shutil.copy2(receipt,dest/'PAIR_RUNTIME_GATE.json')
 for method in METHODS:
  run=g['runs'][method]['run_id'];video=Path(g['runs'][method]['video']['file']);require(video.resolve().is_relative_to(producer/'output') and sha(video)==g['runs'][method]['video']['sha256'],'actual output changed/outside producer')
  shutil.copy2(video,dest/(method+'.mp4'))
  for kind,source_path in [('job',producer/'logs'/f'{run}_job.json'),('history',producer/'logs'/f'{run}_history.json'),('router',producer/'audit/router'/f'{run}.json'),('graph',producer/'configs/graphs'/f'{run}.json')]:
   if kind!='graph':require(sha(source_path)==g['runs'][method][{'job':'job_sha256','history':'history_sha256','router':'router_file_sha256'}[kind]],'producer evidence changed')
   shutil.copy2(source_path,dest/f'{method}_{kind}.json')
 save(dest/'COLLECTION.json',{'schema':'r65-portable-pair-intake-v1','source':source,'producer_root':str(producer),'runtime_receipt':bound(receipt),'files':{p.name:sha(p) for p in dest.iterdir() if p.is_file()}})
 return dest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--producer-root',type=Path,required=True);p.add_argument('--source',choices=SOURCES,required=True);a=p.parse_args();print(collect(a.producer_root,a.source))
