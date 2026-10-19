"""Collect only verified Native MP4/JSON; no tensor downloads or tracking."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from r80_contract import SOURCES,read,sha,require

def collect(source):
 gate=ROOT/'analysis/postrun'/source/'NATIVE_RUNTIME_GATE.json';report=read(gate)
 require(report['passed'] is True and all(report['checks'].values()),'actual Native gate pending')
 run=report['runs']['native'];video=Path(run['video']['file'])
 require(video.is_absolute() and video.resolve().is_relative_to((ROOT/'output').resolve()) and sha(video)==run['video']['sha256'],'actual output binding failed')
 dest=ROOT/'audit/consumer/incoming'/source;dest.mkdir(parents=True,exist_ok=True)
 for before,after in [(video,dest/'native.mp4'),(gate,dest/'NATIVE_RUNTIME_GATE.json'),(ROOT/'logs'/(run['run_id']+'_history.json'),dest/'history.json'),(ROOT/'logs'/(run['run_id']+'_job.json'),dest/'job.json')]:
  if after.exists():require(sha(before)==sha(after),'incoming changed')
  else:shutil.copyfile(before,after)
 value={'source_id':source,'gate_sha256':sha(gate),'video_sha256':sha(dest/'native.mp4'),'valid_frames':run['valid_frames'],'evaluation_crop_xywh':run['evaluation_crop_xywh'],'scope':'New .9 P1 Native; historical .41 P0 display is not a prompt-only comparison.'}
 (dest/'COLLECTION.json').write_text(json.dumps(value,indent=2)+'\n');return value
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES);a=p.parse_args()
 print(json.dumps([collect(source) for source in ([a.source] if a.source else SOURCES)],indent=2))
