"""Fresh generated158 DWPose on the previously verified .9 CPU environment."""
import argparse,os,subprocess,sys,time
from common import *
def run(source,method):
 c=verify_runtime();require(str(ROOT).startswith('/data5/'),'DWPose run uses the frozen .9 CPU environment')
 protocol=c['pose_protocol'];incoming=ROOT/'incoming'/source;g=verify_gate(read(incoming/'PAIR_RUNTIME_GATE.json'),source);video=incoming/(method+'.mp4');require(sha(video)==g['runs'][method]['video']['sha256'],'generated video changed')
 for path,digest in protocol['frozen_external'].items():require(sha(path)==digest,'frozen pose implementation/model differs: '+path)
 dest=ROOT/'poses'/source/method;require(not dest.exists(),'pose attempt exists');dest.mkdir(parents=True)
 script=next(p for p in protocol['frozen_external'] if p.endswith('/pose_probe.py'));command=[sys.executable,script,'--video',str(video),'--output-dir',str(dest),'--threads','4','--stride','1'];started=time.monotonic()
 with (dest/'pose.log').open('x') as log:
  result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1'),timeout=240)
 require(result.returncode==0,'pose extraction failed; preserve log')
 pose=dest/(video.stem+'.pose.json');validator=load('frozen_r49_pose_validator',ROOT/'runtime/source_pose/remote_one.py');raw=validator.validate_pose(read(pose),sha(video),protocol)
 source_manifest=read(ROOT/'source_pose/MANIFEST.json');sourcefile=ROOT/'source_pose'/source/f'source_{source}_video.pose.json';require(sha(sourcefile)==source_manifest['sources'][source]['pose_sha256'],'cached source pose changed');original=read(sourcefile)
 require(raw['provenance']==original['provenance'] and raw['joint_order']==original['joint_order'],'pose source/generated implementation or runtime differs')
 save(dest/'COMPLETE.json',{'passed':True,'source':source,'method':method,'video':bound(video),'pose':bound(pose),'producer_gate':bound(incoming/'PAIR_RUNTIME_GATE.json'),'pose_provenance':raw['provenance'],'command':command,'elapsed_seconds':time.monotonic()-started,'retained_frames':158,'scored_frame_indices':INDICES});return dest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--method',choices=METHODS,required=True);a=p.parse_args()
 with cpu_lock():print(run(a.source,a.method))
