from pathlib import Path
import json,hashlib,shutil,sys,time,subprocess,importlib.util
R=Path(__file__).resolve().parents[1]; P=R.parent/'h3-display-pending-mf-20261019'; C=R.parent/'h3-ive-interview-guidance-metrics-r118-host41-20261019'
rd=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def cp(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
def binding(x,q):assert sha(Path(x['file']))==x['sha256'];cp(Path(x['file']),q)
assert not(R/'SEAL.json').exists()
manifest=rd(P/'SEAL.json')['files']
for rel,h in manifest.items():
 if rel.startswith(('scripts/','runtime/ive/','tests/')):
  assert sha(P/rel)==h;cp(P/rel,R/rel)
m=rd(C/'prepared/long_0047/MF_INPUTS.json');cache=rd(C/'audit/SOURCE_NATIVE_CACHE_VERIFIED.json');assert m['valid_frames']==97 and m['crop_xywh']==[16,8,1280,720]
c=R/'cases/long_0047';old=P/'cases/ivebench_long_0047_9f4de69a2c';o=rd(old/'INPUTS.json')
for n in ['source_full.mp4','source_score.mp4']:cp(old/n,c/n)
for key,n in [('report','REPORT.json'),('tracks','tracks.npz')]:binding(cache['tracks']['source'][key],c/'tracks/source'/n)
source_report=rd(c/'tracks/source/REPORT.json');assert source_report['effective_frame_count']==97 and sha(c/'source_full.mp4')==m['roles']['source']['raw_video']['sha256']
spec=importlib.util.spec_from_file_location('pixels',R/'runtime/ive/metric_runtime/ive_mf_adapter.py');pixels=importlib.util.module_from_spec(spec);spec.loader.exec_module(pixels)
frame_hashes=lambda p:pixels.frame_hashes(p,'/opt/homebrew/bin/ffmpeg')
def rgb_sha(p):return hashlib.sha256(subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(p),'-threads','1','-f','rawvideo','-pix_fmt','rgb24','-'])).hexdigest()
sm=frame_hashes(c/'source_score.mp4');assert sm==source_report['decoded_frame_md5'];assert rgb_sha(c/'source_score.mp4')==m['roles']['source']['decoded_rgb_sha256']
z=m['roles']['forced'];binding(z['raw_video'],c/'forced/full.mp4');subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-nostdin','-y','-threads','2','-i',str(c/'forced/full.mp4'),'-vf','crop=1280:720:16:8,trim=start_frame=0:end_frame=97,setpts=PTS-STARTPTS','-an','-fps_mode','passthrough','-c:v','libx264','-qp','0','-pix_fmt','yuv420p','-threads','2',str(c/'forced/score.mp4')],check=True)
tm=frame_hashes(c/'forced/score.mp4');raw_md5=pixels.frame_hashes(c/'forced/full.mp4','/opt/homebrew/bin/ffmpeg',vf='crop=1280:720:16:8,trim=start_frame=0:end_frame=97');assert tm==raw_md5 and len(tm)==97
save(R/'audit/PIXEL_DOMAIN_VERIFIED.json',{'passed':True,'target_lossless_yuv_equals_actual_raw_crop_per_frame':True,'source_cached_RGB_equal_to_consumer':True,'target_valid_frames':97,'target_raw_sha256':sha(c/'forced/full.mp4'),'target_score_sha256':sha(c/'forced/score.mp4'),'consumer_RGB_file_is_display_intake_only':True})
v=dict(schema='r118-guided-official-mf-v1',benchmark='IVEBench',canonical_id='long_0047',valid_frames=97,evaluation_frames=97,evaluation_fps=24,source_full_sha256=sha(c/'source_full.mp4'),source_score_sha256=sha(c/'source_score.mp4'),source_frame_md5=sm,source_cache={'report_sha256':sha(c/'tracks/source/REPORT.json'),'tracks_sha256':sha(c/'tracks/source/tracks.npz')},selection_sha256=source_report['selection_sha256'],targets=[dict(role='forced',full_file='forced/full.mp4',full_sha256=sha(c/'forced/full.mp4'),score_file='forced/score.mp4',score_sha256=sha(c/'forced/score.mp4'),score_frame_md5=tm,inventory_bindings=[dict(id='r118_long_0047_fixed',field='guided')])],actual_pair_gate_sha256=m['pair_gate']['sha256'],consumer_input_sha256=sha(C/'prepared/long_0047/MF_INPUTS.json'),crop_xywh=[16,8,1280,720],existing_native_score=cache['native_official_MF'])
save(c/'INPUTS.json',v);save(R/'configs/PLAN.json',{'groups':['long_0047'],'jobs':[{'case':'long_0047','role':'forced'}]});runtime=rd(P/'configs/RUNTIME.json');runtime.update(remote_root='/data4/researcher/h3_runs/ive_r118_mf_20261019',status='CPU_READY');save(R/'configs/RUNTIME.json',runtime)
for p,n in [(C/'prepared/long_0047/MF_INPUTS.json','CONSUMER_INPUTS.json'),(C/'audit/SOURCE_NATIVE_CACHE_VERIFIED.json','CACHE_REUSE.json'),(C/'incoming/long_0047/PAIR_RUNTIME_GATE.json','PAIR_RUNTIME_GATE.json'),(C/'incoming/long_0047/ROOT_EXIT_RECEIPT.json','PRODUCER_RELEASE.json')]:cp(p,R/'configs'/n)
files={str(p.relative_to(R)):sha(p)for sub in ['scripts','configs','runtime','cases','tests']for p in(R/sub).rglob('*')if p.is_file()and('__pycache__'not in p.parts or 'official_source'in p.parts)}
save(R/'SEAL.json',{'schema':'r118-mf-v1','files':files,'GPU_started':False,'created_unix':time.time()});save(R/'audit/PREPARE_RECEIPT.json',{'passed':True,'seal_sha256':sha(R/'SEAL.json'),'valid_frames':97,'source_track_reused':cache['tracks']['source']['tracks'],'native_score':cache['native_official_MF'],'scientific_modules_byte_identical_to':str(P),'GPU_started':False});print(sha(R/'SEAL.json'),len(files))
