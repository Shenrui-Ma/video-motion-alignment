"""Prepare pixels for completed outputs; uses the existing official input adapter."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).resolve().parent; B=Path('/Users/researcher/DevProjects'); base=B/'h3-ive-prompt-envelope-metrics-r123-20261020'
sys.path.insert(0,str(B/'h3-ive-r119-mf-host9-20261020/runtime/ive/metric_runtime'))
from ive_mf_adapter import frame_hashes,media_info,validate_time_view,verify_vendor
os.environ['CUDA_VISIBLE_DEVICES']=''
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def bound(p): return {'file':str(p),'sha256':sha(p)}
def link(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists(): os.link(p,q)
 assert sha(p)==sha(q)
queue=read(base/'audit/NEXT_MF_BATCH_QUEUE.json'); records=[]
for item in queue['known_completed_native_inputs']:
 mp=Path(item['manifest']['file']); assert sha(mp)==item['manifest']['sha256']; m=read(mp)
 n=item['valid_frames']; assert m['valid_frames']==n and m['fps']==24 and m['crop_xywh']==[16,8,1280,720] and m['evaluation_indices']==list(range(n))
 folder=R/item['key']; folder.mkdir(exist_ok=True); crop=f'crop=1280:720:16:8,trim=end_frame={n},setsar=1'; roles={}
 for role in ('source','native'):
  b=m['raw_videos'][role]; full=Path(b['file']); assert sha(full)==b['sha256']; score=folder/(role+'_score.mp4')
  cached=B/'h3-ive-prompt-checks-mf-host9-20261020/cases/short_0358'
  if role=='source' and n==105:
   report=read(cached/'tracks/source/REPORT.json'); assert report['source_prepared_sha256']==b['sha256'] and report['effective_frame_count']==n and report['score_frame_indices']==list(range(n)); assert report['vendor']['manifest_sha256']==verify_vendor()['manifest_sha256']; link(cached/'source_score.mp4',score)
  if not score.exists(): subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(full),'-an','-vf',crop,'-vsync','0','-c:v','libx264','-qp','0','-preset','fast','-pix_fmt','yuv420p','-threads','2',str(score)],check=True)
  hashes=frame_hashes(score,'/opt/homebrew/bin/ffmpeg'); assert hashes==frame_hashes(full,'/opt/homebrew/bin/ffmpeg',crop); validate_time_view(media_info(score,'/opt/homebrew/bin/ffprobe'),n)
  roles[role]={'full':b,'score':bound(score),'decoded_frame_md5':hashes}
 records.append({'key':item['key'],'inventory_id':item['inventory_id'],'consumer_input':bound(mp),'valid_frames':n,'fps':24,'crop_xywh':m['crop_xywh'],'roles':roles})
out={'passed':True,'records':records,'created_unix':time.time(),'GPU_started':False,'scope':'Lossless valid-domain media preparation only; all scores remain pending.'}; (R/'READY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'passed':True,'records':len(records),'receipt':bound(R/'READY.json')}))
