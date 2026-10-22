from pathlib import Path
import json,hashlib,os,sys,subprocess,time
B=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1]
BASE=B/'h3-ive-reference-phase-mf-host41-20261020';C=B/'h3-oxygen-online-recovery-metrics-r138-20261020';OLD=B/'h3-ive-r113-seed-replication-mf-host41-20261020/cases/short_0252'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bound(p):return dict(file=str(p),sha256=sha(p))
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def link(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists():os.link(p,q)
 assert sha(p)==sha(q)
assert not(R/'SEAL.json').exists()
for p in (BASE/'scripts').glob('*.py'):link(p,R/'scripts'/p.name)
for name in ('final_release.py','collect.py','verify_inputs.py'):link(BASE/'audit'/name,R/'audit'/name)
(R/'runtime').symlink_to(BASE/'runtime',target_is_directory=True)
for name in ('ive_NUMERIC.json','EXISTING_SERVICES.json'):link(BASE/'configs'/name,R/'configs'/name)
runtime=read(BASE/'configs/RUNTIME.json');runtime.update(remote_root='/data4/researcher/h3_runs/ive_oxygen_online_recovery_mf_r138_20261020',peer_roots=[],status='ACTUAL_INPUT_READY');save(R/'configs/RUNTIME.json',runtime)
mp=C/'prepared/MF_INPUTS.json';m=read(mp);assert m['valid_frames']==98 and m['evaluation_indices']==list(range(98)) and m['new_tracking_roles']==['visible_only']
gate=C/'incoming/actual/ONLINE_RUNTIME_GATE.json';g=read(gate);release=C/'incoming/actual/ROOT_EXIT_RECEIPT.json';rr=read(release)
assert g['passed'] and g['cleanup_verified'] and rr['passed'];assert sha(gate)=='1f29d80ccba6ab366dbb98bdc97127d8b4180c34f9a41d26d95639ed8932d2b7'
assert sha(release)=='b6001af8a34490424a2f9720435f7c54499b0d05a769c5e978036fe3fcfe5c89'
case=R/'cases/short_0252';old=read(OLD/'INPUTS.json');assert m['full_videos']['source']['sha256']==old['source_full_sha256'];assert read(C/'audit/MF_SOURCE_CACHE_VERIFIED.json')['passed']
for rel in ['source_full.mp4','source_score.mp4','tracks/source/REPORT.json','tracks/source/tracks.npz']:link(OLD/rel,case/rel)
full=Path(m['full_videos']['visible_only']['file']);assert sha(full)==m['full_videos']['visible_only']['sha256'];link(full,case/'visible_only/full.mp4')
score=case/'visible_only/score.mp4';crop='crop=1280:720:16:8,trim=end_frame=98,setsar=1'
subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(full),'-an','-vf',crop,'-vsync','0','-c:v','libx264','-qp','0','-preset','fast','-pix_fmt','yuv420p','-threads','2',str(score)],check=True)
sys.path.insert(0,str(R/'runtime/ive/metric_runtime'));from ive_mf_adapter import frame_hashes,media_info,validate_time_view
pixels=frame_hashes(score,'/opt/homebrew/bin/ffmpeg');assert pixels==frame_hashes(full,'/opt/homebrew/bin/ffmpeg',crop);validate_time_view(media_info(score,'/opt/homebrew/bin/ffprobe'),98)
assert frame_hashes(case/'source_score.mp4','/opt/homebrew/bin/ffmpeg')==old['source_frame_md5']
manifest={k:old[k] for k in ['schema','benchmark','canonical_id','valid_frames','evaluation_frames','evaluation_fps','source_full_sha256','source_score_sha256','source_frame_md5','source_cache','selection_sha256','crop_xywh']}
manifest.update(schema='r138-resumed-online-actual-mf-v1',source_cache_domain_proof=bound(C/'audit/MF_SOURCE_CACHE_VERIFIED.json'),historical_reused_scores=read(C/'audit/MF_RESERVATION.json')['reused_scores'],targets=[dict(role='visible_only',full_file='visible_only/full.mp4',full_sha256=sha(full),score_file='visible_only/score.mp4',score_sha256=sha(score),score_frame_md5=pixels,evaluation_indices=list(range(98)),inventory_bindings=[dict(id='r138_short_0252_seed2026101703_visible_only',field='visible_only')],actual_consumer_input=bound(mp),actual_runtime_gate=bound(gate),actual_producer_release=bound(release))]);save(case/'INPUTS.json',manifest)
for p in [mp,gate,release,C/'incoming/actual/COLLECTION.json',C/'audit/MF_SOURCE_CACHE_VERIFIED.json',C/'audit/MF_RESERVATION.json']:link(p,R/'configs/evidence'/p.name)
save(R/'configs/PLAN.json',dict(groups=['short_0252'],jobs=[dict(case='short_0252',role='visible_only')],unique_targets=1,source_cache_count=1,status='ONE_ACTUAL_AUTO_TARGET_ONLY'))
# Reuse the exact remote files; upload only the new score view and small bindings.
remote_existing={'runtime':'/data4/researcher/h3_runs/ive_reference_phase_mf_20261020/runtime'}
for rel in ['source_full.mp4','source_score.mp4','tracks/source/REPORT.json','tracks/source/tracks.npz']:remote_existing['cases/short_0252/'+rel]='/data4/researcher/h3_runs/ive_r113_seed_replication_mf_20261020/cases/short_0252/'+rel
remote_existing['cases/short_0252/visible_only/full.mp4']='/data4/researcher/h3_runs/timing_oxygen_online_resume_r138_20261020/output/r138_short_0252_seed2026101703_visible_only_00001_.mp4'
save(R/'audit/REMOTE_REUSE_PLAN.json',remote_existing)
files={}
for top in ['scripts','configs','cases']:
 for p in (R/top).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:files[str(p.relative_to(R))]=sha(p)
for rel,h in read(BASE/'SEAL.json')['files'].items():
 if rel.startswith('runtime/'):assert sha(R/rel)==h;files[rel]=h
for name in ['audit/prepare.py','audit/final_release.py','audit/collect.py','audit/verify_inputs.py']:files[name]=sha(R/name)
save(R/'SEAL.json',dict(schema='r138-one-actual-output-official-mf-v1',files=files))
for p in (R/'scripts').glob('*.py'):assert sha(p)==sha(BASE/'scripts'/p.name)
upload=[rel for rel in files if not rel.startswith('runtime/') and rel not in remote_existing]+['SEAL.json','audit/REMOTE_REUSE_PLAN.json']
(R/'audit/DEPLOY_FILES.txt').write_text('\n'.join(upload)+'\n')
save(R/'audit/PREDEPLOY_CHECK.json',dict(passed=True,seal=bound(R/'SEAL.json'),files=len(files),execution_scripts_byte_equal=True,source_cache_reused=True,history_scores_reuse_only=True,new_trackers=1,upload_payload_bytes=sum((R/x).stat().st_size for x in upload),producer_release=bound(release),GPU_started=False))
print(json.dumps(read(R/'audit/PREDEPLOY_CHECK.json')))
