"""Bind one completed pair to the existing scoring input domain; no GPU code."""
from pathlib import Path
import argparse,json,hashlib,os,sys,subprocess
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'runtime/ive/metric_runtime'))
from ive_mf_adapter import frame_hashes,media_info,validate_time_view

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def bound(p):return {'file':str(p),'sha256':sha(p)}
def link(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists():os.link(p,q)
 assert sha(p)==sha(q)
a=argparse.ArgumentParser();a.add_argument('--consumer',type=Path,required=True);a.add_argument('--source',required=True);a.add_argument('--native-role',required=True);a.add_argument('--guided-role',required=True);a.add_argument('--inventory-id',required=True);args=a.parse_args();assert not(R/'SEAL.json').exists()
c=R/'cases'/args.source;m=read(c/'INPUTS.json');mp=args.consumer/'prepared'/args.source/'paired/MF_INPUTS.json';v=read(mp);gate=args.consumer/'incoming_pairs'/args.source/'PAIR_RUNTIME_GATE.json';g=read(gate)
assert g['passed'] and all(g['checks'].values()) and v['valid_frames']==m['valid_frames'] and v['fps']==24 and v['crop_xywh']==m['crop_xywh'] and v['evaluation_indices']==list(range(m['valid_frames']))
assert v['raw_videos']['source']['sha256']==m['source_full_sha256'];native=next(t for t in m['targets'] if t['role']==args.native_role);assert v['raw_videos']['native']['sha256']==native['full_sha256']==g['runs']['native']['video']['sha256']
target=v['raw_videos']['forced'];full=Path(target['file']);assert sha(full)==target['sha256']==g['runs']['forced']['video']['sha256'];role=args.guided_role;assert role not in [x['role'] for x in m['targets']]
folder=c/role;link(full,folder/'full.mp4');score=folder/'score.mp4';n=m['valid_frames'];crop=f'crop=1280:720:16:8,trim=end_frame={n},setsar=1'
subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(full),'-an','-vf',crop,'-vsync','0','-c:v','libx264','-qp','0','-preset','fast','-pix_fmt','yuv420p','-threads','2',str(score)],check=True)
hashes=frame_hashes(score,'/opt/homebrew/bin/ffmpeg');assert hashes==frame_hashes(full,'/opt/homebrew/bin/ffmpeg',crop);validate_time_view(media_info(score,'/opt/homebrew/bin/ffprobe'),n)
m['targets'].append({'role':role,'full_file':role+'/full.mp4','full_sha256':target['sha256'],'score_file':role+'/score.mp4','score_sha256':sha(score),'score_frame_md5':hashes,'inventory_bindings':[{'id':args.inventory_id,'field':'guided'}],'actual_consumer_input':bound(mp),'actual_pair_gate':bound(gate),'evaluation_indices':list(range(n))})
save(c/'INPUTS.json',m);plan=read(R/'configs/PLAN.json');plan['jobs'].append({'case':args.source,'role':role});plan['unique_targets']+=1;save(R/'configs/PLAN.json',plan)
for p,name in [(mp,'MF_INPUTS.json'),(gate,'PAIR_RUNTIME_GATE.json'),(args.consumer/'incoming_pairs'/args.source/'COLLECTION.json','COLLECTION.json')]:link(p,R/'configs'/args.source/'actual_pair'/name)
save(R/'audit'/f'{args.source}_{role}_PIXELS_VERIFIED.json',{'passed':True,'pair_gate':bound(gate),'mf_input':bound(mp),'full_generated_video':bound(full),'score':bound(score),'valid_frames':n,'fps':24,'crop_xywh':m['crop_xywh'],'decoded_frame_pixels_equal':True,'same_actual_native':True,'GPU_started':False})
print(json.dumps({'passed':True,'case':args.source,'role':role,'score_sha256':sha(score),'targets':plan['unique_targets']}))
