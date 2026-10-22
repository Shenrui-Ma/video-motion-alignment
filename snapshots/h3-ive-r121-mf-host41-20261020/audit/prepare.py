"""CPU binding for the released R121 official-prompt outputs; no GPU entry."""
from pathlib import Path
import hashlib,importlib.util,json,shutil,subprocess,sys,time
R=Path(__file__).resolve().parents[1];B=R.parent
C=B/'h3-ive-official-positive-recheck-metrics-r121-20261020'
T=B/'h3-ive-r113-seed-replication-mf-host41-20261020'
CACHE={
 'short_0252':(T/'cases/short_0252/tracks/source',T/'cases/short_0252/source_score.mp4'),
 'short_0358':(B/'h3-quantitative-evaluation-recovery-20261019/tracks/source',B/'h3-quantitative-evaluation-recovery-20261019/inputs/source_score.mp4')}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(p),'sha256':sha(p)}
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert read(p)==v,str(p)
 else:p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def cp(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if q.exists():assert sha(p)==sha(q)
 else:shutil.copy2(p,q)
def main():
 assert not(R/'SEAL.json').exists(),'sealed package preserved'
 sys.path.insert(0,str(R/'scripts'));from r121_binding import reviewed_roles,validate_domain
 # Consumer validates actual production graphs and gate/media binding.
 sys.path.insert(0,str(C/'scripts'));import common as con
 from paired import verify_pair_intake
 from remote import read_paths
 con.validate_static();config=con.config();actual=read(C/'audit/EXECUTION_BINDING.json');remote=Path(config['producer_remote'])/'audit'/actual['attempt']
 paths=[str(remote/n)for n in ['COMPLETE.json','ROOT_EXIT_RECEIPT.json']];remote_values=read_paths(paths)
 completion=remote_values[paths[0]]['value'];release=remote_values[paths[1]]['value'];roles=reviewed_roles(completion)
 assert release['passed'] and release['process_absent'] and release['CUDA_allocation_absent'] and release['owner']==actual['owner']
 for name,path in zip(['PRODUCER_COMPLETE.json','PRODUCER_RELEASE.json'],paths):save(R/'configs'/name,remote_values[path]['value'])
 save(R/'configs/PRODUCER_BINDING.json',{'producer_seal':config['producer_seal_sha256'],'execution_binding':bound(C/'audit/EXECUTION_BINDING.json'),'remote_receipts':remote_values})
 spec=importlib.util.spec_from_file_location('pixel_domain',R/'runtime/ive/metric_runtime/ive_mf_adapter.py');pixels=importlib.util.module_from_spec(spec);spec.loader.exec_module(pixels)
 ffmpeg='/opt/homebrew/bin/ffmpeg';ffprobe='/opt/homebrew/bin/ffprobe';hashes=lambda p,vf=None:pixels.frame_hashes(p,ffmpeg,**({'vf':vf}if vf else{}));vendor=pixels.verify_vendor()
 jobs=[];checks=[];caches=[]
 for source,arms in roles.items():
  paired=len(arms)==2;mode='paired'if paired else'native';folder='incoming_pairs'if paired else'incoming'
  gate=verify_pair_intake(source)if paired else con.verify_intake(source)
  assert gate['service_owner']=={'pid':actual['owner']['pid'],'identity':actual['owner']['identity']}
  mp=C/'prepared'/source/mode/'MF_INPUTS.json';m=read(mp);n=validate_domain(source,m,arms)
  gatefile=C/folder/source/('PAIR_RUNTIME_GATE.json'if paired else'NATIVE_RUNTIME_GATE.json');assert sha(gatefile)==m['gate']['sha256']
  c=R/'cases'/source;crop=f'crop=1280:720:16:8,trim=end_frame={n},setsar=1'
  source_full=Path(m['raw_videos']['source']['file']);assert sha(source_full)==m['raw_videos']['source']['sha256'];cp(source_full,c/'source_full.mp4')
  cache,score=CACHE[source];report=read(cache/'REPORT.json')
  cp(score,c/'source_score.mp4')
  for name in ['REPORT.json','tracks.npz']:cp(cache/name,c/'tracks/source'/name)
  assert report['passed'] and report['effective_frame_count']==n and report['score_frame_indices']==list(range(n))
  assert report['source_prepared_sha256']==sha(c/'source_full.mp4') and report['source_score_sha256']==sha(c/'source_score.mp4')
  assert report['tracks_sha256']==sha(c/'tracks/source/tracks.npz')
  assert report['official_commit']==pixels.COMMIT and report['checkpoint_sha256']==pixels.WEIGHT_SHA
  assert report['tracker']==dict(grid_size=10,grid_query_frame=0,backward_tracking=False,offline=True,window_len=60) and report['vendor']['manifest_sha256']==vendor['manifest_sha256']
  sm=hashes(c/'source_score.mp4');assert sm==report['decoded_frame_md5']==hashes(c/'source_full.mp4',crop)
  pixels.validate_time_view(pixels.media_info(c/'source_score.mp4',ffprobe),n)
  targets=[]
  for arm in arms:
   v=m['raw_videos'][arm];assert sha(v['file'])==v['sha256']==gate['runs'][arm]['video']['sha256'];dest=c/arm;cp(Path(v['file']),dest/'full.mp4')
   score=dest/'score.mp4'
   if not score.exists():subprocess.run([ffmpeg,'-v','error','-threads','2','-i',str(dest/'full.mp4'),'-an','-vf',crop,'-vsync','0','-c:v','libx264','-qp','0','-preset','fast','-pix_fmt','yuv420p','-threads','2',str(score)],check=True)
   tm=hashes(score);assert tm==hashes(dest/'full.mp4',crop);pixels.validate_time_view(pixels.media_info(score,ffprobe),n)
   targets.append(dict(role=arm,full_file=f'{arm}/full.mp4',full_sha256=sha(dest/'full.mp4'),score_file=f'{arm}/score.mp4',score_sha256=sha(score),score_frame_md5=tm,evaluation_indices=list(range(n)),inventory_bindings=[dict(id=f'r121_{source}_official_prompt',field='native'if arm=='native'else'guided')]))
   jobs.append({'case':source,'role':arm});checks.append({'case':source,'role':arm,'frames':n,'lossless_yuv_equal':True})
  save(c/'INPUTS.json',dict(schema='r121-official-mf-v1',benchmark='IVEBench',canonical_id=source,valid_frames=n,evaluation_frames=n,evaluation_fps=24,crop_xywh=[16,8,1280,720],source_full_sha256=sha(c/'source_full.mp4'),source_score_sha256=sha(c/'source_score.mp4'),source_frame_md5=sm,source_cache={'report_sha256':sha(c/'tracks/source/REPORT.json'),'tracks_sha256':report['tracks_sha256']},selection_sha256=report['selection_sha256'],targets=targets,consumer_input_sha256=sha(mp),actual_gate_sha256=sha(gatefile)))
  for name,path in [('INPUTS',mp),('GATE',gatefile),('COLLECTION',C/folder/source/'COLLECTION.json')]:cp(path,R/'configs'/f'{source}_{name}.json')
  caches.append(dict(source_id=source,report=bound(cache/'REPORT.json'),tracks=bound(cache/'tracks.npz'),pixel_time_equal=True,frames=n,tracker=report['tracker']))
 save(R/'configs/PLAN.json',dict(groups=list(roles),jobs=jobs,unique_targets=len(jobs),source_cache_count=2))
 save(R/'configs/CACHE_REUSE.json',dict(passed=True,sources=caches))
 files={str(p.relative_to(T/'runtime/ive')):sha(p)for p in(T/'runtime/ive').rglob('*')if p.is_file()and('__pycache__'not in p.parts or'official_source'in p.parts)}
 assert all(sha(R/'runtime/ive'/rel)==h for rel,h in files.items());save(R/'configs/ive_NUMERIC.json',dict(source=str(T/'runtime/ive'),files=files))
 save(R/'audit/PIXEL_DOMAIN_VERIFIED.json',dict(passed=True,targets=checks,source_caches=2))
 files={str(p.relative_to(R)):sha(p)for sub in ['scripts','configs','runtime','cases','tests']for p in(R/sub).rglob('*')if p.is_file()and('__pycache__'not in p.parts or'official_source'in p.parts)}
 save(R/'SEAL.json',dict(schema='r121-mf-v1',files=files,GPU_started=False,created_unix=time.time()))
 save(R/'audit/PREPARE_RECEIPT.json',dict(passed=True,seal=bound(R/'SEAL.json'),new_trackers=len(jobs),source_caches=2,scientific_template=bound(T/'SEAL.json'),GPU_started=False))
 print(sha(R/'SEAL.json'),len(files))
if __name__=='__main__':main()
