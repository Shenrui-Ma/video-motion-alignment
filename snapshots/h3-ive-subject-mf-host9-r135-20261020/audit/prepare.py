from pathlib import Path
import json,os,sys,hashlib,subprocess,time,ast
R=Path(__file__).resolve().parents[1];B=R.parent;OLD=B/'h3-ive-caption-scrubs-mf-host9-20261020';C=B/'h3-ive-subject-replacement-metrics-r135-20261020';P=B/'h3-timing-ive-subject-replacement-r135-20261020';REMOTE='/home/researcher/h3_runs/ive_subject_mf_r135_20261020'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rd(p):return json.loads(Path(p).read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def link(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists():os.link(p,q)
 assert sha(p)==sha(q)
assert not (R/'SEAL.json').exists()
for p in (OLD/'scripts').glob('*.py'):link(p,R/'scripts'/p.name)
(R/'runtime').symlink_to(OLD/'runtime',target_is_directory=True)
rt=rd(OLD/'configs/RUNTIME.json');rt.update(remote_root=REMOTE,gpu_uuid='GPU-REDACTED',peer_roots=['/home/researcher/h3_runs/timing_ive_otter_color_r136_20261020']);save(R/'configs/RUNTIME.json',rt)
sys.path.insert(0,str(R/'runtime/ive/metric_runtime'))
from ive_mf_adapter import frame_hashes,media_info,validate_time_view
key='short_0084';n=76;c=R/'cases'/key;mp=C/'prepared'/key/'native/MF_INPUTS.json';m=rd(mp);gp=C/'incoming'/key/'NATIVE_RUNTIME_GATE.json';g=rd(gp)
assert m['valid_frames']==n and m['total_frames']==90 and m['evaluation_indices']==list(range(n)) and m['fps']==24 and m['crop_xywh']==[16,8,1280,720]
assert g['passed'] and all(g['checks'].values()) and g['runs']['native']['video']['sha256']==m['raw_videos']['native']['sha256']
assert m['input_to_original_frame']==list(range(75))+[74]
checks={};crop=f'crop=1280:720:16:8,trim=end_frame={n},setsar=1'
for role in ['source','native']:
 src=m['raw_videos'][role];assert sha(src['file'])==src['sha256'];full=c/('source_full.mp4' if role=='source' else 'native/full.mp4');out=c/('source_score.mp4' if role=='source' else 'native/score.mp4');link(src['file'],full)
 subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(full),'-an','-vf',crop,'-vsync','0','-c:v','libx264','-qp','0','-preset','fast','-pix_fmt','yuv420p','-threads','2',str(out)],check=True)
 checks[role]=frame_hashes(out,'/opt/homebrew/bin/ffmpeg');assert checks[role]==frame_hashes(full,'/opt/homebrew/bin/ffmpeg',crop);validate_time_view(media_info(out,'/opt/homebrew/bin/ffprobe'),n)
t=dict(role='native',full_file='native/full.mp4',full_sha256=sha(c/'native/full.mp4'),score_file='native/score.mp4',score_sha256=sha(c/'native/score.mp4'),score_frame_md5=checks['native'],inventory_bindings=[{'id':'r135_short_0084_generic_retention','field':'native'}])
save(c/'INPUTS.json',dict(schema='existing-official-mf-input-manifest-v1',benchmark='IVEBench',canonical_id=key,valid_frames=n,evaluation_frames=n,evaluation_fps=24,crop_xywh=[16,8,1280,720],source_full_sha256=sha(c/'source_full.mp4'),source_score_sha256=sha(c/'source_score.mp4'),source_frame_md5=checks['source'],source_cache=None,selection_sha256=sha(mp),targets=[t],consumer_input_sha256=sha(mp),actual_native_gate_sha256=sha(gp),guided_generated=False,task_valid=True,visual_timing='synchronous; actual guided skip'))
plan={'groups':[key],'jobs':[{'case':key,'role':r} for r in ['source','native']]};save(R/'configs/PLAN.json',plan)
pa=P/'audit/root_subject_replacement_attempt1';release=pa/'ROOT_EXIT_RECEIPT.json';assert sha(release)=='7a2a51aa23afe9b9cdd56ede7c4acc30bd7da24c9129e1b26e03fed29febc22c';rel=rd(release);assert rel['passed'] and rel['process_absent'] and rel['CUDA_allocation_absent']
for p,name in [(mp,'CONSUMER_INPUTS.json'),(gp,'NATIVE_RUNTIME_GATE.json'),(release,'ROOT_EXIT_RECEIPT.json'),(pa/'COMPLETE.json','COMPLETE.json'),(C/'audit/full_frame_review'/key/'native/REVIEW.json','VISUAL_REVIEW.json')]:link(p,R/'configs'/key/name)
link(release,R/'configs/PRODUCER_RELEASE.json')
s=(OLD/'audit/final_release.py').read_text().replace("assert len(states) == 3 and len(results) == 2","plan = read(ROOT/'configs/PLAN.json')\n    expected_scores = sum(x['role'] != 'source' for x in plan['jobs'])\n    assert len(states) == len(plan['jobs']) and len(results) == expected_scores").replace("'completed_generated_scores':2","'completed_generated_scores':expected_scores")
(R/'audit/final_release.py').write_text(s)
s=(OLD/'audit/collect.py').read_text().replace('/home/researcher/h3_runs/ive_caption_scrubs_mf_host9_20261020',REMOTE).replace('requested_targets=2',"requested_targets=sum(x['role']!='source' for x in read(R/'configs/PLAN.json')['jobs'])")
(R/'audit/collect.py').write_text(s);link(OLD/'audit/verify_current_cpu.py',R/'audit/verify_current_cpu.py')
for p in list((R/'scripts').glob('*.py'))+list((R/'audit').glob('*.py')):ast.parse(p.read_text())
files={str(p.relative_to(R)):sha(p) for folder in ['scripts','configs','cases'] for p in (R/folder).rglob('*') if p.is_file()}
for rel,h in rd(OLD/'SEAL.json')['files'].items():
 if rel.startswith('runtime/') and '__pycache__' not in rel:assert sha(R/rel)==h;files[rel]=h
for name in ['final_release.py','collect.py','verify_current_cpu.py','prepare.py']:files['audit/'+name]=sha(R/'audit'/name)
save(R/'SEAL.json',dict(schema='existing-host9-mf-new-manifest-v1',base_seal_sha256=sha(OLD/'SEAL.json'),scientific_and_lifecycle_scripts_byte_identical=True,files=files,created_unix=time.time()))
save(R/'audit/MINIMAL_HANDOFF.json',dict(passed=True,seal_sha256=sha(R/'SEAL.json'),files=len(files),jobs=plan['jobs'],scores=1,task_status='PASS_CORE_EDIT/synchronous/SKIP',new_framework=False,changes=['sample manifest and scoreview only','GPU2 and actual R136 peer root','read-only final-release/collector counts derive from PLAN'],scientific_scripts_unchanged=True,runtime_reused=str(OLD/'runtime'),prerequisite_release={'file':REMOTE+'/configs/PRODUCER_RELEASE.json','sha256':sha(release)},gpu=rt['gpu_uuid'],entry=['scripts/run_batch.py','--attempt','actual_r135_subject_attempt1','--gpu',rt['gpu_uuid'],'--review','ROOT_REVIEW.json'],GPU_started=False))
print(json.dumps(rd(R/'audit/MINIMAL_HANDOFF.json')))
