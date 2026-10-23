from pathlib import Path
import hashlib,json,subprocess,shlex,importlib.util
D=Path(__file__).resolve().parent
E=D.parents[4]
p=E/'innovation/adaptive_strength_20261023/batch/prepare_visual.py'
spec=importlib.util.spec_from_file_location('existing_visual_prepare',p);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
completion=E/'supervision/field_environment_reproduction_20261023/completion_1441.json'
c=json.loads(completion.read_text());expected=c['outputs']['video_sha256'];video=D/'temporal_gain_field.mp4'
if not video.exists():
 with video.with_suffix('.part').open('wb') as f:
  r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_HOST_CONFIGURE_LOCALLY',shlex.join(['cat',c['outputs']['video_path']])],stdout=f,stderr=subprocess.PIPE,timeout=60)
 if r.returncode:raise RuntimeError(r.stderr.decode())
 assert v.digest(video.with_suffix('.part'))==expected
 video.with_suffix('.part').rename(video)
assert v.digest(video)==expected
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate','-of','json',str(video)]))['streams'][0]
assert (probe['width'],probe['height'],int(probe['nb_frames']),probe['r_frame_rate'])==(1312,736,107,'24/1')
v.extract(video,D/'frames',105)
v.sheet(D/'frames',range(0,105,4),D/'overview.jpg','same-env field')
for start in range(0,105,36):
 v.sheet(D/'frames',range(start,min(105,start+36)),D/f'detail_{start:03d}.jpg','same-env field',crop=(0,65,430,380))
controls=[]
for m in ['native','global_weak']:
 d=E/'showcases/live_phase_calibration_20261023/visual/short_0358'/m
 a=d/'ANNOTATION.json';g=d/'TRAJECTORY_GATE.json';j=json.loads(a.read_text());gate=json.loads(g.read_text())
 assert gate['passed'] and gate['actual_video_sha256']==j['video_sha256']
 assert v.digest(d/(m+'.mp4'))==j['video_sha256']
 controls.append({'method':m,'annotation_path':str(a),'annotation_sha256':v.digest(a),'gate_sha256':v.digest(g),'video_sha256':j['video_sha256']})
frozen=E/'innovation/signed_phase_calibration_20261023/calibration/FROZEN_EVENTS.json'
source=E/'showcases/partial_rope_pilots_20261022/visual/short_0358/source.mp4'
assert v.digest(source)=='ed48b90939dd7387f5a4e56a371394e899b600baa230740544ec75ea9fd531fd'
(D/'PREPARATION.json').write_text(json.dumps({'video_path':str(video),'remote_video_path':c['outputs']['video_path'],'video_sha256':expected,'video_bytes':video.stat().st_size,'video_probe':probe,'valid_frames':105,'crop_xywh':[16,8,1280,720],'frames_resized':[768,432],'preparation_program':str(p),'preparation_program_sha256':v.digest(p),'completion_path':str(completion),'completion_sha256':v.digest(completion),'source_sha256':v.digest(source),'frozen_events_path':str(frozen),'frozen_events_sha256':v.digest(frozen),'controls':controls,'status':'prepared_not_yet_annotated'},indent=2)+'\n')
print(json.dumps({'video_sha256':expected,'valid_frames':105,'probe':probe,'evidence':[f.name for f in D.glob('*.jpg')]}))
