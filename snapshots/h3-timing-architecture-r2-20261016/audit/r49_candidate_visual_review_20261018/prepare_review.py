from pathlib import Path
import subprocess,json,hashlib
from PIL import Image,ImageDraw,ImageFont
import numpy as np
out=Path(__file__).parent
archive=Path('/Users/researcher/DevProjects/h3-timing-flexiact-native-r49-20261017/analysis/postrun/captured/batch')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',16)
checks={}; details={}
inv=json.loads((archive/'FILE_INVENTORY.json').read_text());gate=json.loads((archive/'RUN_GATE.json').read_text()); runtime=json.loads((archive/'RUNTIME_GATE.json').read_text())
assert sha(archive/'FILE_INVENTORY.json')==gate['file_inventory_sha256']
assert sha(archive/'RUNTIME_GATE.json')==gate['runtime_gate_sha256']
for source in ['rotate','crouch']:
 run=f'r49_source_{source}_seed2026101701_native'
 summary=json.loads((archive/'final'/run/'SUMMARY.json').read_text())
 relative=list(summary['phase_dependency_hashes'])+[f'audit/{run}_noise.json',f'audit/{run}_conditioning.json',f'output/{run}_00001_.mp4']
 record=[]
 for rel in relative:
  p=archive/rel
  expected=inv.get(rel,{}).get('sha256',summary['phase_dependency_hashes'].get(rel,{}).get('sha256'))
  if rel.startswith('output/'):expected=summary['video_sha256']
  if p.is_file():
   actual=sha(p);assert expected is None or expected==actual,(rel,expected,actual)
   record.append({'path':str(p),'sha256':actual,'expected':expected,'matched':expected==actual})
  else: record.append({'path':str(p),'present':False,'expected':expected,'scope':'remote large tensor excluded from local archive'})
 videos={'source':archive/'inputs'/f'source_{source}_video.mp4','native':archive/'output'/f'{run}_00001_.mp4'}
 images={}; probes={}
 for name,p in videos.items():
  probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,nb_frames:frame=best_effort_timestamp_time','-of','json',str(p)]))
  times=[float(x['best_effort_timestamp_time']) for x in probe['frames']];assert len(times)==158
  pts_error=max(abs(t-i/24) for i,t in enumerate(times));assert pts_error<1e-5,pts_error
  probes[name]={'path':str(p),'sha256':sha(p),'frames':158,'fps':'24/1','max_pts_error':pts_error,'valid_prefix':147}
  raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(p),'-vf','select=not(mod(n\\,3))*lt(n\\,147),scale=384:256:flags=lanczos','-vsync','0','-frames:v','49','-f','rawvideo','-pix_fmt','rgb24','-'])
  frames=np.frombuffer(raw,np.uint8).reshape(-1,256,384,3);assert len(frames)==49
  images[name]=frames
 pages=[]
 for start in range(0,49,7):
  canvas=Image.new('RGB',(768,7*282),(0,0,0));draw=ImageDraw.Draw(canvas)
  for row,i in enumerate(range(start,min(start+7,49))):
   for col,name in enumerate(['source','native']):
    canvas.paste(Image.fromarray(images[name][i]),(col*384,row*282))
    draw.text((col*384+8,row*282+259),f'{name.upper()}  f{i*3:03d}  {i/8:.3f}s',(240,240,240),font=font)
  p=out/f'{source}_all49_page{start//7+1:02d}.jpg';canvas.save(p,quality=94)
  pages.append({'path':str(p),'frames24':[i*3 for i in range(start,min(start+7,49))],'sha256':sha(p)})
 noise=json.loads((archive/f'audit/{run}_noise.json').read_text())
 cond=json.loads((archive/f'audit/{run}_conditioning.json').read_text())
 details[source]={'identity':summary['identity'],'inputs_verified':record,'videos':probes,'noise':noise,'condition_input_video':cond['input_video'],'runtime_checks':{k:v for k,v in runtime['checks'].items() if run in k},'pages':pages,'source_time_resolution_seconds':.125,'review_grid':'all49 original source instants n/8; target same physical frames3n/24; generated intermediate frames not individually annotated'}
checks={'host':'H3_SERVER_A .9','gpu_uuid':gate['owner']['gpu_uuid'],'service_pid':gate['owner']['pid'],'service_start_ticks':gate['owner']['identity']['start_ticks'],'run_gate_sha256':sha(archive/'RUN_GATE.json'),'runtime_gate_sha256':sha(archive/'RUNTIME_GATE.json'),'scope':'existing complete local archive hash checks; no remote/GPU or tensor regeneration','cases':details}
(out/'INTEGRITY_AND_FRAMES.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False)+'\n')
print({k:{'target':v['identity'],'pages':len(v['pages']),'files':len(v['inputs_verified'])} for k,v in details.items()})
