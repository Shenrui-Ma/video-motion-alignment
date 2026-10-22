"""Bind all four released R113 outputs to the unchanged official IVE MF runtime."""
from pathlib import Path
import json, hashlib, shutil, sys, importlib.util, time
R=Path(__file__).resolve().parents[1]
D=R.parent
C=D/'h3-oxygen-seed-replication-metrics-r113-host41-20261019'
T=D/'h3-ive-r118-mf-host41-20261019'
CACHE=D/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019/r106_short_0252_solvers_capacity4'
SOURCE_REPORT=CACHE/'actual_host41/cases/r106_short_0252_solvers/tracks/source/REPORT.json'
SOURCE_SCORE=CACHE/'cases/r106_short_0252_solvers/inputs/source_score.mp4'
SEEDS=(2026101702,2026101703)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def cp(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
def bind(p):return {'file':str(p),'sha256':sha(p)}
def checked_copy(b,q):assert sha(Path(b['file']))==b['sha256'];cp(Path(b['file']),q)
def main():
 assert not(R/'SEAL.json').exists(),'preserve sealed package'
 sys.path.insert(0,str(C/'scripts'))
 import common as consumer
 actual=C/'incoming/actual';consumer.verify_collection(actual)
 release=read(actual/'ROOT_EXIT_RECEIPT.json');aggregate=read(actual/'AGGREGATE_GATE.json')
 assert release['passed'] and aggregate['passed']
 report=read(SOURCE_REPORT)
 assert report['passed'] and report['effective_frame_count']==98 and report['score_frame_indices']==list(range(98))
 assert report['source_prepared_sha256']==sha(actual/'source.mp4')
 assert report['source_score_sha256']==sha(SOURCE_SCORE)
 assert report['tracks_sha256']==sha(SOURCE_REPORT.parent/'tracks.npz')
 assert report['official_commit']=='2dcf8900ee65197f43854c76f61c66a32bb8dbfc'
 assert report['checkpoint_sha256']=='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
 assert report['tracker']==dict(grid_size=10,grid_query_frame=0,backward_tracking=False,offline=True,window_len=60)
 spec=importlib.util.spec_from_file_location('pixels',R/'runtime/ive/metric_runtime/ive_mf_adapter.py');pixels=importlib.util.module_from_spec(spec);spec.loader.exec_module(pixels)
 hashes=lambda p,vf=None:pixels.frame_hashes(p,'/opt/homebrew/bin/ffmpeg',**({'vf':vf}if vf else {}))
 c=R/'cases/short_0252'
 cp(actual/'source.mp4',c/'source_full.mp4');cp(SOURCE_SCORE,c/'source_score.mp4')
 for name in ['REPORT.json','tracks.npz']:cp(SOURCE_REPORT.parent/name,c/'tracks/source'/name)
 sm=hashes(c/'source_score.mp4');assert sm==report['decoded_frame_md5']
 assert sm==hashes(c/'source_full.mp4','crop=1280:720:16:8,trim=end_frame=98,setsar=1')
 targets=[];pixel_checks=[]
 for seed in SEEDS:
  mp=C/'prepared'/str(seed)/'MF_INPUTS.json';m=read(mp)
  assert (m['seed'],m['valid_frames'],m['total_frames'],m['fps'],m['crop_xywh'])==(seed,98,107,24,[16,8,1280,720])
  assert m['physical_frame_indices']==list(range(98)) and m['aggregate_gate']['sha256']==sha(actual/'AGGREGATE_GATE.json')
  assert m['roles']['source']['full_video']['sha256']==sha(c/'source_full.mp4') and m['roles']['source']['frame_md5']==sm
  for arm in ['native','fixed']:
   z=m['roles'][arm];role=f'seed{seed}_{arm}';dest=c/role
   checked_copy(z['full_video'],dest/'full.mp4');checked_copy(z['score_video'],dest/'score.mp4')
   tm=hashes(dest/'score.mp4');assert tm==z['frame_md5'] and len(tm)==98
   assert tm==hashes(dest/'full.mp4','crop=1280:720:16:8,trim=end_frame=98,setsar=1')
   info=pixels.media_info(dest/'score.mp4','/opt/homebrew/bin/ffprobe');assert info['count']==98 and all(abs(t-i/24)<1e-6 for i,t in enumerate(info['pts_s']))
   targets.append(dict(role=role,seed=seed,original_arm=arm,full_file=f'{role}/full.mp4',full_sha256=sha(dest/'full.mp4'),score_file=f'{role}/score.mp4',score_sha256=sha(dest/'score.mp4'),score_frame_md5=tm,evaluation_indices=list(range(98)),inventory_bindings=[dict(id=f'r113_short_0252_seed{seed}_fixed',field='native'if arm=='native'else'guided')]))
   pixel_checks.append(dict(role=role,lossless_yuv_equal_to_actual_raw_crop=True,frames=98))
  cp(mp,R/'configs'/f'CONSUMER_INPUTS_{seed}.json')
  cp(actual/f'seed{seed}_PAIR_GATE.json',R/'configs'/f'PAIR_GATE_{seed}.json')
 inputs=dict(schema='r113-four-output-official-mf-v1',benchmark='IVEBench',canonical_id='short_0252',valid_frames=98,evaluation_frames=98,evaluation_fps=24,source_full_sha256=sha(c/'source_full.mp4'),source_score_sha256=sha(c/'source_score.mp4'),source_frame_md5=sm,source_cache={'report_sha256':sha(c/'tracks/source/REPORT.json'),'tracks_sha256':sha(c/'tracks/source/tracks.npz')},selection_sha256=report['selection_sha256'],targets=targets,crop_xywh=[16,8,1280,720],aggregate_gate_sha256=sha(actual/'AGGREGATE_GATE.json'))
 save(c/'INPUTS.json',inputs)
 save(R/'configs/PLAN.json',dict(groups=['short_0252'],jobs=[dict(case='short_0252',role=t['role'])for t in targets],unique_targets=4,source_cache_count=1))
 save(R/'configs/ive_NUMERIC.json',dict(source=str(T/'runtime/ive'),files={str(p.relative_to(T/'runtime/ive')):sha(p)for p in(T/'runtime/ive').rglob('*')if p.is_file()and('__pycache__'not in p.parts or 'official_source'in p.parts)}))
 runtime=read(T/'configs/RUNTIME.json');runtime['remote_root']='/data4/researcher/h3_runs/ive_r113_seed_replication_mf_20261020';save(R/'configs/RUNTIME.json',runtime)
 for name in ['ROOT_EXIT_RECEIPT.json','AGGREGATE_GATE.json','COLLECTION.json']:cp(actual/name,R/'configs'/name)
 save(R/'configs/CACHE_REUSE.json',dict(passed=True,source_report=bind(SOURCE_REPORT),source_tracks=bind(SOURCE_REPORT.parent/'tracks.npz'),source_score=bind(SOURCE_SCORE),exact_domain_frames=98,source_frame_md5=sm,scientific_tracker=report['tracker'],checkpoint_sha256=report['checkpoint_sha256']))
 save(R/'audit/PIXEL_DOMAIN_VERIFIED.json',dict(passed=True,source_cached_decoded_frames_equal=True,targets=pixel_checks))
 files={str(p.relative_to(R)):sha(p)for sub in ['scripts','configs','runtime','cases','tests']for p in(R/sub).rglob('*')if p.is_file()and('__pycache__'not in p.parts or 'official_source'in p.parts)}
 save(R/'SEAL.json',dict(schema='r113-mf-v1',files=files,GPU_started=False,created_unix=time.time()))
 save(R/'audit/PREPARE_RECEIPT.json',dict(passed=True,seal=bind(R/'SEAL.json'),new_trackers=4,source_tracker_reused=True,scientific_template=bind(T/'SEAL.json'),GPU_started=False))
 print(sha(R/'SEAL.json'),len(files))
if __name__=='__main__':main()
