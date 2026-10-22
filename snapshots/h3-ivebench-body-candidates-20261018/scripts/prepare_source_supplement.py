"""Freeze a source-only shortlist; retain official MP4 bytes and six fixed views."""
from pathlib import Path
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import time
import urllib.request
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]/'supplement_style_or_props'
ROOT.mkdir(exist_ok=False)
for name in ('scripts','metadata','sources','source_review','audit'):(ROOT/name).mkdir()
BASE=Path('/Users/researcher/DevProjects')
META=BASE/'h3-ivebench-next-candidates-20261018/metadata'
PRIOR=BASE/'h3-ivebench-pilot-20261017/inputs_selection/candidate_sources'
REV='1e6cb655c0a537f6093edcf18e2607fb03e76734'
IDS=['short_0090','short_0055','short_0321']
REASONS={'short_0090':'Style edit; climber with moving limbs, check visibility and action changes.','short_0055':'Style edit; fork/cake and cup interactions, inspect hand actions.','short_0321':'Prop addition; seated talking man with gestures, inspect actual hand transitions.'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

for name in ('ivebenchdb_prompt_short.json','ivebenchdb_prompt_long.json','ivebenchdb_name_mapping.csv'):
 shutil.copy2(META/name,ROOT/'metadata'/name)
tasks=json.loads((META/'ivebenchdb_prompt_short.json').read_text())+json.loads((META/'ivebenchdb_prompt_long.json').read_text())
assert len(tasks)==600
prior_runs={}
for producer in BASE.glob('h3-timing-ivebench*'):
 for graph in (producer/'configs/graphs').glob('*.json'):
  for sid in re.findall(r'(?:short|long)_\d{4}',graph.name):prior_runs.setdefault(sid,[]).append(str(graph))
assert not (set(IDS)&set(prior_runs))
plan={'schema':'ivebench-body-source-prefilter-v1','frozen_before_new_source_inspection':True,'dataset_revision':REV,
 'official_repository_commit':'2dcf8900ee65197f43854c76f61c66a32bb8dbfc','metadata_count':600,
 'generated_outputs_used':0,'status':'SOURCE_REVIEW_ONLY_NO_INFERENCE_QUEUE',
 'criteria':'Supplement after eight source-only inspections found only two clear moving-hand candidates and several head-only shots. Official global style or prop edit that should preserve the human action; prefer visible changing limbs or hands. Keep this supplementary task stratum separate from identity/clothing editing. Retain original edit prompt. Judge actual source motion/framing before any generation. Record excluded and low-motion candidates; do not force eight suitable cases.',
 'excluded_previously_generated_or_queued':prior_runs,
 'six_view_rule':'round(i*(N-1)/5), i=0..5 on original decoded video frames, no chosen event times',
 'candidates':[{'source_id':sid,'metadata_reason':REASONS[sid],'previous_source_only_review':(PRIOR/(sid+'.mp4')).exists(), 'official_task':next(t for t in tasks if t['src_video_name']==sid+'.mp4')} for sid in IDS],
 'metadata_sha256':{name:sha(ROOT/'metadata'/name) for name in ('ivebenchdb_prompt_short.json','ivebenchdb_prompt_long.json','ivebenchdb_name_mapping.csv')}}
write(ROOT/'PREFILTER_FREEZE.json',plan)
write(ROOT/'PREFILTER_FREEZE_SHA.json',{'sha256':sha(ROOT/'PREFILTER_FREEZE.json')})
paths=['ivebenchdb_mp4_short/'+sid+'.mp4' for sid in IDS]
request=urllib.request.Request('https://huggingface.co/api/datasets/Coraxor/IVEBench/paths-info/'+REV,data=json.dumps({'paths':paths,'expand':True}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=60) as f:info=json.load(f)
write(ROOT/'metadata/OFFICIAL_FILES_INFO.json',info)
assert {x['path'] for x in info}==set(paths)
assert sum(x['size'] for x in info)<500_000_000
receipts=[];probes=[]
for sid in IDS:
 record=next(x for x in info if x['path']=='ivebenchdb_mp4_short/'+sid+'.mp4')
 url='https://huggingface.co/datasets/Coraxor/IVEBench/resolve/'+REV+'/'+record['path']
 destination=ROOT/'sources'/(sid+'.mp4');start=time.monotonic()
 if (PRIOR/(sid+'.mp4')).exists():shutil.copy2(PRIOR/(sid+'.mp4'),destination);origin='exact archived official source'
 else:
  with urllib.request.urlopen(url,timeout=120) as source,destination.with_suffix('.part').open('wb') as output:shutil.copyfileobj(source,output)
  destination.with_suffix('.part').rename(destination);origin='official frozen revision download'
 assert sha(destination)==record['lfs']['oid'] and destination.stat().st_size==record['size']
 receipts.append({'source_id':sid,'file':str(destination),'url':url,'bytes':destination.stat().st_size,'sha256':sha(destination),'origin':origin,'wall_seconds':time.monotonic()-start})
 write(ROOT/'audit/DOWNLOAD_RECEIPTS.json',receipts)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(destination)]))
 pts=[float(f['best_effort_timestamp_time']) for f in probe['frames']];assert pts and all(b>a for a,b in zip(pts,pts[1:]))
 stream=probe['streams'][0];frames=[round(i*(len(pts)-1)/5) for i in range(6)]
 row={'source_id':sid,'width':stream['width'],'height':stream['height'],'avg_frame_rate':stream['avg_frame_rate'],'frame_count':len(pts),'pts_s':pts,'duration_last_pts_s':pts[-1],'review_frames':frames}
 probes.append(row);write(ROOT/'SOURCE_TIMEBASE.json',probes)
 canvas=Image.new('RGB',(1920,780),'black');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
 for index,frame in enumerate(frames):
  raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(destination),'-vf',f'select=eq(n\\,{frame}),scale=640:360:force_original_aspect_ratio=decrease:flags=lanczos,pad=640:360:(ow-iw)/2:(oh-ih)/2:black','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'])
  x=(index%3)*640;y=(index//3)*390;canvas.paste(Image.open(io.BytesIO(raw)).convert('RGB'),(x,y));draw.text((x+10,y+364),f'{sid}  f{frame}  {pts[frame]:.3f}s',font=font,fill='white')
 canvas.save(ROOT/'source_review'/(sid+'.jpg'),quality=93)
 print(sid,len(pts),pts[-1],destination.stat().st_size,flush=True)
print('SOURCE_ONLY_COMPLETE',flush=True)
