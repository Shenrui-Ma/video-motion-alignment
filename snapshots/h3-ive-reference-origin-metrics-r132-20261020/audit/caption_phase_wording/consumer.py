"""Read actual R132 output, reuse established rendering; no GPU entry."""
import argparse,shutil,sys,base64,html
from common import *
from remote import read_paths,fetch
from render_native import media_info,check_time,choose_font
import render_pair,full_frame_review

def collect(attempt):
 c=validate_static();require(attempt.replace('_','').replace('-','').isalnum(),'invalid attempt');root=Path(c['producer_remote']);case=c['case'];run=case['run_id'];dest=ROOT/'incoming'
 if dest.exists():return verify_collection()
 paths={'STARTED.json':root/f'audit/{attempt}/STARTED.json','COMPLETE.json':root/f'audit/{attempt}/COMPLETE.json','ROOT_EXIT_RECEIPT.json':root/f'audit/{attempt}/ROOT_EXIT_RECEIPT.json','REFERENCE_ORIGIN_RUNTIME_GATE.json':root/'analysis/postrun/long_0039/REFERENCE_ORIGIN_RUNTIME_GATE.json'}
 data=read_paths([str(p)for p in paths.values()]);values={k:data[str(p)]['value']for k,p in paths.items()};gate=values['REFERENCE_ORIGIN_RUNTIME_GATE.json'];r=verify_gate(gate,values['STARTED.json'],values['COMPLETE.json'],values['ROOT_EXIT_RECEIPT.json']);require(values['COMPLETE.json']['runtime_gate_sha256']==data[str(paths['REFERENCE_ORIGIN_RUNTIME_GATE.json'])]['sha256'],'complete gate SHA differs')
 fixed={'graph.json':(f'configs/graphs/{run}.json',sha(ROOT/'configs/graphs'/f'{run}.json')),'history.json':(f'logs/{run}_history.json',r['history_sha256']),'job.json':(f'logs/{run}_job.json',r['job_sha256']),'router.json':(f'audit/router/{run}.json',r['router_file_sha256']),'conditioning.json':(f'audit/{run}_conditioning.json',r['binding_artifacts'][f'audit/{run}_conditioning.json']),'noise.json':(f'audit/{run}_noise.json',r['binding_artifacts'][f'audit/{run}_noise.json'])}
 staging=ROOT/'audit/intake_staging'/str(time.time_ns());staging.mkdir(parents=True);digests={}
 for name,path in paths.items():fetch(str(path),staging/name);require(sha(staging/name)==data[str(path)]['sha256'],'receipt changed during transfer');digests[name]=sha(staging/name)
 for name,(rel,h)in fixed.items():fetch(str(root/rel),staging/name);require(sha(staging/name)==h,'artifact digest differs '+name);digests[name]=h
 for index,(rel,h)in enumerate(r['binding_artifacts'].items()):
  if not rel.endswith('.json') or any(rel==v[0]for v in fixed.values()):continue
  name=f'binding_{index:02d}.json';fetch(str(root/rel),staging/name);require(sha(staging/name)==h,'bound JSON differs');digests[name]=h
 fetch(r['video']['file'],staging/'reference_origin.mp4');require(sha(staging/'reference_origin.mp4')==r['video']['sha256'],'reference_origin video changed');digests['reference_origin.mp4']=r['video']['sha256']
 check_time(media_info(staging/'reference_origin.mp4','/opt/homebrew/bin/ffprobe'),107,1312,736)
 save(staging/'COLLECTION.json',{'schema':'r132-reference_origin-actual-intake-v1','attempt':attempt,'files':digests,'producer_seal_sha256':c['producer_seal_sha256'],'source_id':'long_0039','parent_media':c['parent_media'],'valid_frames':106,'total_frames':107,'fps':24,'crop_xywh':[16,8,1280,720],'GPU_started':False,'created_unix':time.time()});staging.rename(dest);return verify_collection()

def render():
 verify_collection();c=config();font=choose_font();ffmpeg='/opt/homebrew/bin/ffmpeg';ffprobe='/opt/homebrew/bin/ffprobe';source=Path(c['parent_media']['source']['file']);reference_origin=ROOT/'incoming/reference_origin.mp4';outputs=[]
 for prior,label in [('native','2.普通编辑'),('fixed','2.固定时序引导')]:
  dest=ROOT/'showcase'/('source_'+prior+'_reference_origin');inputs=[source,Path(c['parent_media'][prior]['file']),reference_origin]
  if not (dest/'PRESENTATION.json').exists():
   stage=ROOT/'audit/render_staging'/str(time.time_ns());stage.mkdir(parents=True);render_pair.LABELS=('1.参考视频',label,'3.参考分支原点引导');media=render_pair.render_files(inputs,stage,107,106,font,ffmpeg,ffprobe,rows=(6,12))
   save(stage/'PRESENTATION.json',{'schema':'r132-three-column-presentation-v1','columns':['source',prior,'reference_origin'],'collection':bound(ROOT/'incoming/COLLECTION.json'),'inputs':[bound(p)for p in inputs],'timeline':{'fps':24,'valid_frames':106,'total_frames':107,'crop_xywh':[16,8,1280,720]},'original_task':c['case']['original_task'],'method':'Reference-video branch query-origin rotation; fixed steps 6–14; original joint RoPE preserved; 450 routed blocks','quality_review':'PENDING',**media});dest.parent.mkdir(exist_ok=True);stage.rename(dest)
  m=read(dest/'PRESENTATION.json');require(m['collection']==bound(ROOT/'incoming/COLLECTION.json'),'presentation intake differs')
  for x in m['videos']+m['contact_sheets']:require(sha(dest/x['file'])==x['sha256'],'presentation changed')
  outputs.append(bound(dest/'PRESENTATION.json'))
 pages=ROOT/'audit/full106_review';ledger=pages/'FRAME_LEDGER.json'
 if not ledger.exists():
  inputs=[source,Path(c['parent_media']['native']['file']),reference_origin];rows=full_frame_review.render_files(inputs,pages,107,106,font,ffmpeg,ffprobe)
  save(ledger,{'columns':['source','native','reference_origin'],'all_frames_prepared':True,'all_frames_inspected':False,'valid_frames':106,'fps':24,'input_media':[bound(p)for p in inputs],'collection':bound(ROOT/'incoming/COLLECTION.json'),'pages':rows,'existing_fixed_review':c['parent_full_frame_review'],'events':bound(ROOT/'design/R122_SOURCE_EVENTS_REFINED_BEFORE_OUTPUT.json'),'evaluation_plan':bound(ROOT/'design/R129_EVALUATION_PLAN.json')})
 save(ROOT/'prepared/MF_INPUTS.json',{'benchmark':'IVEBench','source_id':'long_0039','full_videos':{**c['parent_media'],'reference_origin':bound(reference_origin)},'valid_frames':106,'total_frames':107,'evaluation_indices':list(range(106)),'evaluation_fps':24,'crop_xywh':[16,8,1280,720],'collection':bound(ROOT/'incoming/COLLECTION.json'),'source_cache_policy':'Reuse verified R122 source/native/fixed tracks only when exact pixels, physical frame domain, official tracker checkpoint and settings match. Track only new reference_origin output.','GPU_started':False})
 return {'presentations':outputs,'full_frame_ledger':bound(ledger),'MF_inputs':bound(ROOT/'prepared/MF_INPUTS.json')}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);a=p.parse_args();collect(a.attempt);print(json.dumps(render(),ensure_ascii=False))
