"""One-shot CPU intake after the original R101 consumer actually completes."""
import shutil,sys
from common import *
CONSUMER=Path('/Users/researcher/DevProjects/h3-flexiact-character-guidance-metrics-r101-20261019')
def main():
 verify_runtime();validate_cache()
 if not (CONSUMER/'incoming/COLLECTION.json').is_file() or not (CONSUMER/'prepared/MF_INPUTS.json').is_file():
  print(json.dumps({'status':'PENDING_ACTUAL_R101_PAIRED_CONSUMER','GPU_started':False}));return
 old=load('frozen_r101_consumer',ROOT/'runtime/r101_consumer_common.py');old.ROOT=CONSUMER
 require(sha(CONSUMER/'CONSUMER_FREEZE.json')==sha(ROOT/'configs/r101_consumer_freeze.json'),'consumer snapshot changed')
 gate=old.verify_intake();mf=read(CONSUMER/'prepared/MF_INPUTS.json');validate_gate(gate,mf['media'])
 require(mf['physical_frame_indices']==INDICES and mf['physical_pts_seconds']==[i/8 for i in range(49)] and mf['valid_frames']==147,'MF timestamp contract differs')
 for item in mf['media'].values():require(sha(item['file'])==item['sha256'],'actual MF media changed')
 dest=ROOT/'incoming';require(not list(dest.iterdir()),'existing intake retained')
 for name in ['PAIR_RUNTIME_GATE.json','COLLECTION.json','history.json','job.json','graph.json','forced.mp4']:
  shutil.copy2(CONSUMER/'incoming'/name,dest/name)
 shutil.copy2(CONSUMER/'prepared/MF_INPUTS.json',dest/'R101_MF_INPUTS.json');shutil.copy2(CONSUMER/'audit/EXECUTION_BINDING.json',dest/'EXECUTION_BINDING.json')
 save(dest/'INTAKE.json',{'passed':True,'consumer_freeze_sha256':sha(CONSUMER/'CONSUMER_FREEZE.json'),'files':{p.name:sha(p) for p in dest.iterdir() if p.is_file()},'source_full_sha256':mf['media']['source']['sha256'],'native_full_sha256':mf['media']['native']['sha256'],'guided_full_sha256':mf['media']['forced']['sha256'],'GPU_started':False})
 print(json.dumps({'status':'ACTUAL_R101_INTAKE_READY','gate':bound(dest/'PAIR_RUNTIME_GATE.json'),'GPU_started':False}))
if __name__=='__main__':main()
