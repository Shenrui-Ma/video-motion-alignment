from pathlib import Path
import os,sys,json,hashlib,subprocess,time,shutil
R=Path(__file__).resolve().parents[1];B=R.parent;OLD=B/'h3-ive-r119-mf-host9-20261020'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def link(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists():os.link(p,q)
 assert sha(p)==sha(q)
assert not (R/'SEAL.json').exists()
for p in (OLD/'scripts').glob('*.py'):link(p,R/'scripts'/p.name)
(R/'runtime').symlink_to(OLD/'runtime',target_is_directory=True)
sys.path.insert(0,str(R/'runtime/ive/metric_runtime'))
from ive_mf_adapter import frame_hashes,media_info,validate_time_view,verify_vendor
rt=read(OLD/'configs/RUNTIME.json');rt.update(gpu_uuid='GPU-REDACTED',remote_root='/home/researcher/h3_runs/ive_prompt_checks_mf_host9_20261020',peer_roots=['/home/researcher/h3_runs/timing_ive_generic_retention_r122_20261020']);save(R/'configs/RUNTIME.json',rt)
release=B/'h3-ive-official-prompt-metrics-r120-20261019/audit/actual_release/EXACT_RELEASE.json'
x=read(release);assert x['passed'] and x['all_five_exact_generations_absent'] and x['CUDA_allocation_absent'];link(release,R/'configs/R120_EXACT_RELEASE.json')
save(R/'configs/PRODUCER_RELEASE.json',dict(passed=True,process_absent=True,CUDA_allocation_absent=True,owner=x['records']['service'],source_release={'file':'configs/R120_EXACT_RELEASE.json','sha256':sha(release)},normalization='field-only adaptation of exact five-process release'))
jobs=[];records=[]
for key,project,ident,n in [('long_0059','h3-ive-official-prompt-metrics-r120-20261019','r120_long_0059_official_prompt',144),('short_0358','h3-ive-prompt-envelope-metrics-r123-20261020','r123_short_0358_prompt_envelope',105)]:
 c=R/'cases'/key;con=B/project;mp=con/'prepared'/key/'native/MF_INPUTS.json';m=read(mp);gate=con/'incoming'/key/'NATIVE_RUNTIME_GATE.json';g=read(gate)
 assert m['valid_frames']==n and m['fps']==24 and m['crop_xywh']==[16,8,1280,720] and m['evaluation_indices']==list(range(n));assert g['passed'] and all(g['checks'].values()) and g['runs']['native']['video']['sha256']==m['raw_videos']['native']['sha256']
 for role in ['source','native']:
  s=m['raw_videos'][role];assert sha(s['file'])==s['sha256'];link(Path(s['file']),c/('source_full.mp4' if role=='source' else 'native/full.mp4'))
 crop=f'crop=1280:720:16:8,trim=end_frame={n},setsar=1'
 cache=None;selection=sha(mp)
 if key=='short_0358':
  cached=B/'h3-ive-r121-mf-host41-20261020/cases/short_0358';link(cached/'source_score.mp4',c/'source_score.mp4')
  for f in ['REPORT.json','tracks.npz']:link(cached/'tracks/source'/f,c/'tracks/source'/f)
  report=read(c/'tracks/source/REPORT.json');assert report['passed'] and report['effective_frame_count']==n and report['score_frame_indices']==list(range(n));assert report['source_prepared_sha256']==sha(c/'source_full.mp4') and report['source_score_sha256']==sha(c/'source_score.mp4') and report['tracks_sha256']==sha(c/'tracks/source/tracks.npz');assert report['checkpoint_sha256']==rt['checkpoint_sha256'] and report['tracker']=={'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60};assert report['vendor']['manifest_sha256']==verify_vendor()['manifest_sha256']
  selection=report['selection_sha256'];cache={'report_sha256':sha(c/'tracks/source/REPORT.json'),'tracks_sha256':report['tracks_sha256']}
 for role in ['source','native']:
  full=c/('source_full.mp4' if role=='source' else 'native/full.mp4');out=c/('source_score.mp4' if role=='source' else 'native/score.mp4')
  if not out.exists():subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(full),'-an','-vf',crop,'-vsync','0','-c:v','libx264','-qp','0','-preset','fast','-pix_fmt','yuv420p','-threads','2',str(out)],check=True)
  hashes=frame_hashes(out,'/opt/homebrew/bin/ffmpeg');assert hashes==frame_hashes(full,'/opt/homebrew/bin/ffmpeg',crop);validate_time_view(media_info(out,'/opt/homebrew/bin/ffprobe'),n)
  if role=='source':sm=hashes
  else:tm=hashes
 if cache:assert sm==report['decoded_frame_md5']
 else:jobs.append({'case':key,'role':'source'})
 target=dict(role='native',full_file='native/full.mp4',full_sha256=sha(c/'native/full.mp4'),score_file='native/score.mp4',score_sha256=sha(c/'native/score.mp4'),score_frame_md5=tm,inventory_bindings=[{'id':ident,'field':'native'}])
 save(c/'INPUTS.json',dict(schema='existing-official-mf-input-manifest-v1',benchmark='IVEBench',canonical_id=key,valid_frames=n,evaluation_frames=n,evaluation_fps=24,crop_xywh=[16,8,1280,720],source_full_sha256=sha(c/'source_full.mp4'),source_score_sha256=sha(c/'source_score.mp4'),source_frame_md5=sm,source_cache=cache,selection_sha256=selection,targets=[target],consumer_input_sha256=sha(mp),actual_native_gate_sha256=sha(gate),guided_generated=False,task_valid=False))
 for src,name in [(mp,'CONSUMER_INPUTS.json'),(gate,'NATIVE_RUNTIME_GATE.json')]:link(src,R/'configs'/key/name)
 jobs.append({'case':key,'role':'native'});records.append(dict(case=key,frames=n,source_cache_reused=bool(cache),input_sha256=sha(mp),gate_sha256=sha(gate),target_sha256=target['full_sha256']))
save(R/'configs/PLAN.json',dict(groups=['long_0059','short_0358'],jobs=jobs))
# Administrative summary handles a fresh source plus two generated targets; scientific scripts remain byte-identical.
s=(OLD/'audit/final_release.py').read_text();s=s.replace("        result_file = ROOT/'results'/job['case']/(job['role']+'.json')\n        value = read(result_file)['motion_fidelity']\n        assert isinstance(value, (int, float)) and math.isfinite(value)\n        states.append(bound(state_file));results.append(bound(result_file));released.append(receipt);identities.append(owner)","        if job['role'] != 'source':\n            result_file = ROOT/'results'/job['case']/(job['role']+'.json')\n            value = read(result_file)['motion_fidelity']\n            assert isinstance(value, (int, float)) and math.isfinite(value)\n            results.append(bound(result_file))\n        states.append(bound(state_file));released.append(receipt);identities.append(owner)").replace('assert len(states) == len(results) == 1','assert len(states) == 3 and len(results) == 2').replace("'completed_generated_scores':1","'completed_generated_scores':2")
(R/'audit/final_release.py').write_text(s)
s=(OLD/'audit/collect.py').read_text().replace('/home/researcher/h3_runs/ive_r119_mf_host9_20261020',rt['remote_root']).replace('requested_targets=1','requested_targets=2');(R/'audit/collect.py').write_text(s)
files={}
for sub in ['scripts','configs','cases']:
 for p in (R/sub).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:files[str(p.relative_to(R))]=sha(p)
for rel,h in read(OLD/'SEAL.json')['files'].items():
 if rel.startswith('runtime/'):assert sha(R/rel)==h;files[rel]=h
files['audit/final_release.py']=sha(R/'audit/final_release.py')
save(R/'SEAL.json',dict(schema='reused-r119-official-mf-runtime-new-inputs-v1',files=files,base_seal_sha256=sha(OLD/'SEAL.json'),numerical_and_lifecycle_scripts_byte_identical=True,created_unix=time.time()))
save(R/'audit/PREPARE_RECEIPT.json',dict(passed=True,records=records,jobs=jobs,seal_sha256=sha(R/'SEAL.json'),files=len(files),runtime_reused=str(OLD/'runtime'),GPU_started=False))
print(json.dumps(read(R/'audit/PREPARE_RECEIPT.json')))
