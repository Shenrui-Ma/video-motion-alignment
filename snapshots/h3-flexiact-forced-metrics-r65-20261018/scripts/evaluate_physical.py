"""Unchanged fixed physical views, using both freshly generated method poses."""
import argparse,os,sys,time
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import *
def relabel(value):
 if isinstance(value,dict):return {('forced' if k=='automatic' else k):relabel(v) for k,v in value.items()}
 if isinstance(value,list):return [relabel(v) for v in value]
 return value

def run(source):
 c=verify_runtime();incoming=ROOT/'incoming'/source;g=verify_gate(read(incoming/'PAIR_RUNTIME_GATE.json'),source);require(sha(ROOT/'source_pose/MANIFEST.json')==c['source_pose_manifest_sha256'],'source pose manifest changed')
 sm=read(ROOT/'source_pose/MANIFEST.json')['sources'][source];sourcepath=ROOT/'source_pose'/source/f'source_{source}_video.pose.json';require(sha(sourcepath)==sm['pose_sha256'] and sha(ROOT/'inputs'/f'source_{source}_video.mp4')==sm['video_sha256'],'source pose/prepared video mismatch');original=read(sourcepath)
 poses={};receipts={}
 for method in METHODS:
  folder=ROOT/'poses'/source/method;receipt=read(folder/'COMPLETE.json');path=folder/(method+'.pose.json');require(receipt['passed'] is True and sha(path)==receipt['pose']['sha256'] and receipt['video']['sha256']==g['runs'][method]['video']['sha256'] and receipt['producer_gate']['sha256']==sha(incoming/'PAIR_RUNTIME_GATE.json'),'actual target pose receipt changed');poses[method]=read(path);receipts[method]=bound(folder/'COMPLETE.json')
  require(poses[method]['provenance']==original['provenance'] and poses[method]['joint_order']==original['joint_order'],'DWPose runtime differs')
 sys.path.insert(0,str(ROOT/'runtime/physical'));evaluator=load('r65_frozen_physical_evaluator',ROOT/'runtime/physical/evaluate.py');started=time.monotonic();result=evaluator.evaluate(original,poses['native'],poses['forced'])
 report={'source':source,'official_pair_id':f'human/{source}/000','development_pairs':['fitness','one_leg'],'original_fixed5':['chest','crouch','fitness','one_leg','rotate'],'numeric_freeze_sha256':c['physical_freeze_sha256'],'source_pose':bound(sourcepath),'generated_pose_receipts':receipts,'producer_gate':bound(incoming/'PAIR_RUNTIME_GATE.json'),'numeric_function':'unchanged evaluate(reference,native,automatic), automatic argument holds fixed forced ON','method_label_map':{'native':'native','automatic':'forced'},'result':relabel(result),'elapsed_seconds':time.monotonic()-started,'selection_scope':'development subset selected using earlier Native timing and edit attainment; all predefined views retained'}
 output=ROOT/'scores/physical'/f'{source}.json';save(output,report);return output
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);a=p.parse_args()
 with cpu_lock():print(run(a.source))
