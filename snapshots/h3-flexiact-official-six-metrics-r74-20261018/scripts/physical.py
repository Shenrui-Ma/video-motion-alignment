"""CPU pose and fixed physical views; independent targets supplement paired support."""
import argparse,os,subprocess,sys,time
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import *
def relabel(value):
 if isinstance(value,dict):return {('forced' if k=='automatic' else k):relabel(v) for k,v in value.items()}
 if isinstance(value,list):return [relabel(v) for v in value]
 return value

def protocol():
 verify_runtime();p=read(ROOT/'configs/physical_protocol.json')
 for relative,digest in p['external_relative_sha256'].items():require(sha(Path(p['aux_root'])/relative)==digest,'DWPose external artifact changed: '+relative)
 require(sha(ROOT/'runtime/source_pose/pose_probe.py')==p['pose_probe_sha256'],'pose script changed')
 frozen(ROOT/'runtime/physical','FREEZE.json',p['physical_numeric_freeze_sha256'])
 require(sha(ROOT/'runtime/source_pose/remote_one.py')==p['validator_sha256'] and sha(ROOT/'runtime/physical/independent_adapter.py')==p['independent_adapter_sha256'],'frozen evaluator administrative adapter changed')
 return p

def source_video(action):
 require(action in MOTIONS,'unknown source');path=ROOT/'runtime/source_videos'/f'source_{action}_video.mp4';expected=next(p['prepared_source_sha256'] for p in read(ROOT/'configs/contract.json')['pairs'] if p['motion_source_id']==action);require(sha(path)==expected,'source video changed');return path

def extract(action,pair=None,method=None):
 p=protocol();validator=load('r74_original_pose_validator',ROOT/'runtime/source_pose/remote_one.py')
 if pair is None:video=source_video(action);dest=ROOT/'source_pose'/action
 else:
  require(method in METHODS and pair_info(pair)['motion_source_id']==action,'pose pair binding differs');gate=verify_gate(read(ROOT/'incoming'/pair/'PAIR_RUNTIME_GATE.json'),pair);video=ROOT/'incoming'/pair/f'{method}.mp4';require(sha(video)==gate['runs'][method]['video']['sha256'],'actual target video changed');dest=ROOT/'poses'/pair/method
 require(not dest.exists(),'pose attempt exists; preserve actual partial/success result');dest.mkdir(parents=True)
 cmd=[sys.executable,str(ROOT/'runtime/source_pose/pose_probe.py'),'--video',str(video),'--output-dir',str(dest),'--aux-root',p['aux_root'],'--threads','4','--stride','1']
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1');start=time.monotonic()
 with (dest/'pose.log').open('x') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=p['timeout_seconds'])
 require(result.returncode==0,'CPU pose extraction failed; preserve log');path=dest/(video.stem+'.pose.json');raw=validator.validate_pose(read(path),sha(video),p)
 record={'passed':True,'motion_source_id':action,'pair_key':pair,'method':method,'video':bound(video),'pose':bound(path),'pose_provenance':raw['provenance'],'command':cmd,'elapsed_seconds':time.monotonic()-start,'physical_protocol':bound(ROOT/'configs/physical_protocol.json'),'retained_frames':158,'scored_frame_indices':INDICES,'GPU_started':False}
 if pair:record['producer_gate']=bound(ROOT/'incoming'/pair/'PAIR_RUNTIME_GATE.json')
 save(dest/'COMPLETE.json',record);return record

def checked_pose(folder,video,protocol,pair=None,method=None):
 receipt=read(folder/'COMPLETE.json');path=folder/(video.stem+'.pose.json');require(receipt['passed'] is True and receipt['video']['sha256']==sha(video) and receipt['pose']['sha256']==sha(path),'pose actual binding differs')
 require(receipt['pair_key']==pair and receipt['method']==method,'pose source/target identity differs')
 if pair:require(receipt['producer_gate']['sha256']==sha(ROOT/'incoming'/pair/'PAIR_RUNTIME_GATE.json'),'pose producer receipt changed')
 validator=load('r74_original_pose_validator',ROOT/'runtime/source_pose/remote_one.py');return validator.validate_pose(read(path),sha(video),protocol),bound(folder/'COMPLETE.json')

def evaluate(pair):
 p=protocol();action=pair_info(pair)['motion_source_id'];gate=ROOT/'incoming'/pair/'PAIR_RUNTIME_GATE.json';verify_gate(read(gate),pair)
 source,source_receipt=checked_pose(ROOT/'source_pose'/action,source_video(action),p);targets={};receipts={}
 for method in METHODS:
  targets[method],receipts[method]=checked_pose(ROOT/'poses'/pair/method,ROOT/'incoming'/pair/f'{method}.mp4',p,pair,method)
  require(targets[method]['provenance']==source['provenance'] and targets[method]['joint_order']==source['joint_order'],'source/target pose runtime differs')
 sys.path.insert(0,str(ROOT/'runtime/physical'));evaluator=load('r74_unchanged_evaluator',ROOT/'runtime/physical/evaluate.py');adapter=load('r74_independent_targets',ROOT/'runtime/physical/independent_adapter.py');start=time.monotonic()
 paired=relabel(evaluator.evaluate(source,targets['native'],targets['forced']));independent=adapter.independent_targets(evaluator.evaluate,source,targets)
 bindings={'pair_key':pair,'motion_source_id':action,'source_pose_receipt':source_receipt,'generated_pose_receipts':receipts,'producer_gate':bound(gate),'numeric_evaluator':bound(ROOT/'runtime/physical/evaluate.py'),'independent_adapter':bound(ROOT/'runtime/physical/independent_adapter.py'),'elapsed_seconds':time.monotonic()-start,'all_fixed_windows_and_UNKNOWN_retained':True}
 out=ROOT/'scores/physical'/pair;out.mkdir(parents=True,exist_ok=False)
 save(out/'PAIRED.json',{'schema':'r74-physical-common-support-v1',**bindings,'result':paired,'scope':'Original paired common-support report. A failed target may make the original paired report UNKNOWN.'})
 save(out/'INDEPENDENT.json',{'schema':'r74-physical-independent-targets-v1',**bindings,'results':independent,'scope':'One target evaluated independently per call with unchanged source/functions/thresholds; retain only one slot. Does not redefine common-support paired error.'})
 save(out/'COMPLETE.json',{'passed':True,'pair_key':pair,'paired':bound(out/'PAIRED.json'),'independent':bound(out/'INDEPENDENT.json'),'GPU_started':False});return out
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--action',choices=['check','source','native','forced','evaluate'],required=True);parser.add_argument('--key',required=True);a=parser.parse_args()
 try:
  with cpu_lock():
   if a.action=='check':print(protocol())
   elif a.action=='source':print(extract(a.key))
   elif a.action=='evaluate':print(evaluate(a.key))
   else:print(extract(pair_info(a.key)['motion_source_id'],a.key,a.action))
 except BlockingIOError:raise SystemExit(75)
