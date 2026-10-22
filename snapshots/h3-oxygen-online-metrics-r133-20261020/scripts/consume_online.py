"""Single read-only intake; no inference, tracker, watcher, or tensor transfer."""
import argparse,subprocess
from common import *
from remote import read_paths,fetch
from render_native import media_info,check_time,choose_font
import render_pair,full_frame_review

def collect(attempt):
 c=validate_static();require(attempt==c['expected_attempt'],'unregistered actual attempt');root=Path(c['producer_remote']);dest=ROOT/'incoming/actual'
 if dest.exists():return verify_collection()
 paths={'STARTED.json':root/f'audit/{attempt}/STARTED.json','COMPLETE_REVIEW_HOLD.json':root/f'audit/{attempt}/COMPLETE_REVIEW_HOLD.json','ROOT_EXIT_RECEIPT.json':root/f'audit/{attempt}/ROOT_EXIT_RECEIPT.json','ONLINE_RUNTIME_GATE.json':root/'analysis/postrun/ONLINE_RUNTIME_GATE.json','counterfactual.json':root/f'audit/counterfactual/{RUN}.json','graph.json':root/f'configs/graphs/{RUN}.json','history.json':root/f'logs/{RUN}_history.json','job.json':root/f'logs/{RUN}_job.json','x0_manifest.json':root/f'audit/x0/{RUN}/manifest.json'}
 data=read_paths([str(p) for p in paths.values()]);v={k:data[str(p)]['value'] for k,p in paths.items()};g=v['ONLINE_RUNTIME_GATE.json'];counts=verify_gate(g,v['STARTED.json'],v['COMPLETE_REVIEW_HOLD.json'],v['ROOT_EXIT_RECEIPT.json'],v['counterfactual.json'])
 require(v['COMPLETE_REVIEW_HOLD.json']['gate_sha256']==data[str(paths['ONLINE_RUNTIME_GATE.json'])]['sha256'],'completion gate SHA differs')
 stage=ROOT/'audit/formal_intake_staging'/str(time.time_ns());stage.mkdir(parents=True);digests={};remote_map={}
 def get(path,name,digest=None):
  path=safe_path(path);require(path.suffix=='.json','tensor or unregistered metadata transfer denied');target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);fetch(str(path),target)
  if digest:require(sha(target)==digest,'changed actual evidence '+name)
  digests[name]=sha(target);remote_map[str(path)]=name;return read(target)
 for name,path in paths.items():get(path,name,data[str(path)]['sha256'])
 for m in v['counterfactual.json']['counterfactual']['measurements']:
  i=m['physical_index'];folder=f'observations/{i:02d}';req=get(m['request_file'],folder+'/request.json',m['request_sha256']);res=get(m['response_file'],folder+'/response.json',m['response_sha256'])
  require(req['physical_index']==i and req['run_id']==RUN,'observer request identity differs')
  for kind in ('decode','pose','observer'):get(res[kind]['file'],folder+'/'+kind+'.json',res[kind]['sha256'])
  filtered=Path(res['pose']['file']);raw=filtered.parent/'native.pose.json';selection=get(filtered.parent/'adult_selection.json',folder+'/adult_selection.json');get(raw,folder+'/raw.pose.json',selection['raw_pose_sha256']);require(selection['filtered_pose_sha256']==res['pose']['sha256'],'raw/filtered pose selection differs')
  get(filtered.parent.parent/'pose_complete.json',folder+'/pose_complete.json')
  expected=next(x for x in g['raw_filtered_pose_binding'] if x['index']==i);require(expected['raw_sha256']==selection['raw_pose_sha256'] and expected['filtered_sha256']==selection['filtered_pose_sha256'] and expected['rejected_frames']==selection['rejected_frames'],'gate person-selection binding differs')
 fetch(g['video']['file'],stage/'visible_only.mp4');require(sha(stage/'visible_only.mp4')==g['video']['sha256'],'actual output changed during transfer');digests['visible_only.mp4']=g['video']['sha256'];check_time(media_info(stage/'visible_only.mp4','/opt/homebrew/bin/ffprobe'),107,1312,736)
 save(stage/'COLLECTION.json',{'schema':'r133-visible-only-actual-intake-v1','attempt':attempt,'files':digests,'remote_json_to_local':remote_map,'producer_seal_sha256':c['producer_seal_sha256'],'actual_counts':counts,'roles':['source','native','fixed','visible_only'],'historical_inputs':bound(ROOT/'configs/HISTORICAL_INPUTS.json'),'valid_frames':98,'total_frames':107,'fps':24,'crop_xywh':[16,8,1280,720],'tensor_payloads_transferred':False,'GPU_started':False});dest.parent.mkdir(exist_ok=True);stage.rename(dest);return verify_collection()

def render_four(inputs,dest,font,ffmpeg,ffprobe):
 from PIL import Image,ImageDraw,ImageFont
 dest.mkdir(parents=True);cap=Image.new('RGB',(5120,88),'black');draw=ImageDraw.Draw(cap);f=ImageFont.truetype(str(font),32)
 for col,label in enumerate(('1.参考视频','2.普通编辑','3.固定时序引导','4.自动时序引导')):draw.text((col*1280+(1280-draw.textlength(label,font=f))/2,30),label,font=f,fill='white')
 cap.save(dest/'caption.png');out=dest/'comparison_full98.mp4';cmd=[ffmpeg,'-v','error','-nostdin','-n']
 for p in inputs:check_time(media_info(p,ffprobe),107,1312,736);cmd+=['-threads','2','-i',str(p)]
 cmd+=['-framerate','24','-loop','1','-i',str(dest/'caption.png')];fs=[f'[{i}:v]crop=1280:720:16:8,trim=end_frame=98,setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(4)]+['[v0][v1][v2][v3]hstack=inputs=4:shortest=1[images]','[images][4:v]vstack=inputs=2:shortest=1[out]'];cmd+=['-filter_complex',';'.join(fs),'-map','[out]','-frames:v','98','-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(out)];subprocess.run(cmd,check=True,timeout=420);check_time(media_info(out,ffprobe),98,5120,808)
 return {'videos':[{'file':out.name,'sha256':sha(out),'frame_interval_inclusive':[0,97],'command':cmd}]}

def render():
 verify_collection();h=read(ROOT/'configs/HISTORICAL_INPUTS.json');roles={k:Path(v['full_video']['file']) for k,v in h['historical_roles'].items()};roles['visible_only']=ROOT/'incoming/actual/visible_only.mp4';ffmpeg='/opt/homebrew/bin/ffmpeg';ffprobe='/opt/homebrew/bin/ffprobe';font=choose_font();groups=[('source','native','visible_only'),('source','fixed','visible_only'),('source','native','fixed','visible_only')];present=[]
 for group in groups:
  dest=ROOT/'showcase'/'_'.join(group);inputs=[roles[k] for k in group]
  if not (dest/'PRESENTATION.json').exists():
   stage=ROOT/'audit/formal_render_staging'/str(time.time_ns());stage.mkdir(parents=True)
   if len(group)==3:
    render_pair.LABELS=('1.参考视频','2.普通编辑' if group[1]=='native' else '2.固定时序引导','3.自动时序引导');media=render_pair.render_files(inputs,stage,107,98,font,ffmpeg,ffprobe,rows=(6,12))
   else:media=render_four(inputs,stage/'four',font,ffmpeg,ffprobe);stage=stage/'four'
   save(stage/'PRESENTATION.json',{'schema':'r133-online-presentation-v1','columns':list(group),'collection':bound(ROOT/'incoming/actual/COLLECTION.json'),'inputs':[bound(x) for x in inputs],'timeline':{'fps':24,'valid_frames':98,'total_frames':107,'crop_xywh':[16,8,1280,720]},'quality_review':'PENDING','method':'R86 visible-only online temporal window/start-stop; source-defined adult xcenter ROI0.40–0.75; actual20 decisions recorded','evaluation_plan':bound(ROOT/'configs/EVALUATION_PLAN.json'),**media});dest.parent.mkdir(exist_ok=True);stage.rename(dest)
  present.append(bound(dest/'PRESENTATION.json'))
 pages=ROOT/'audit/full98_review';ledger=pages/'FRAME_LEDGER.json';inputs=[roles[k] for k in ('source','native','fixed','visible_only')]
 if not ledger.exists():
  rows=full_frame_review.render_files(inputs,pages,107,98,font,ffmpeg,ffprobe);save(ledger,{'columns':['source','native','fixed','visible_only'],'valid_frames':98,'fps':24,'pages':rows,'all_frames_prepared':True,'all_frames_inspected':False,'inputs':[bound(x) for x in inputs],'collection':bound(ROOT/'incoming/actual/COLLECTION.json'),'evaluation_plan':bound(ROOT/'configs/EVALUATION_PLAN.json')})
 save(ROOT/'prepared/MF_INPUTS.json',{'benchmark':'IVEBench','source_id':'short_0252','actual_role':'visible_only','full_videos':{k:bound(v) for k,v in roles.items()},'valid_frames':98,'total_frames':107,'evaluation_indices':list(range(98)),'evaluation_fps':24,'crop_xywh':[16,8,1280,720],'collection':bound(ROOT/'incoming/actual/COLLECTION.json'),'historical_cache_binding':bound(ROOT/'configs/HISTORICAL_INPUTS.json'),'new_tracking_roles':['visible_only'],'GPU_started':False})
 return {'presentations':present,'full_frame_ledger':bound(ledger),'MF_inputs':bound(ROOT/'prepared/MF_INPUTS.json')}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',default='root_oxygen_online_attempt1');a=p.parse_args();collect(a.attempt);print(json.dumps(render(),ensure_ascii=False))
