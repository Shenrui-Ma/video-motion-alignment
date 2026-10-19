from pathlib import Path
import shutil,json,hashlib
R=Path(__file__).resolve().parents[1];P=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-evaluation-r66-20261018');G=Path('/Users/researcher/DevProjects/h3-timing-flexiact-official-six-r74-20261018');F=Path('/Users/researcher/DevProjects/h3-flexiact-forced-metrics-r65-20261018');I=Path('/Users/researcher/DevProjects/h3-timing-ivebench-prompt-pair-r71-20261018/analysis/physical_time_review')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
for d in ['scripts','configs','runtime/source_videos','runtime/physical','runtime/source_pose','tests','controls','incoming','prepared','source_pose','poses','showcase','scores','reports','audit/watcher']:(R/d).mkdir(parents=True,exist_ok=True)
# All official metric numerical files and weights copied without substitution.
shutil.copytree(P/'runtime/official_metric',R/'runtime/official_metric',ignore=shutil.ignore_patterns('__pycache__','*.pyc'),dirs_exist_ok=True);shutil.copytree(P/'runtime/release',R/'runtime/release',ignore=shutil.ignore_patterns('__pycache__','*.pyc'),dirs_exist_ok=True)
for p in (F/'runtime/physical').iterdir():
 if p.is_file():cp(p,R/'runtime/physical'/p.name)
cp(F/'runtime/source_pose/remote_one.py',R/'runtime/source_pose/remote_one.py');cp(I/'vendor/pose_probe.py',R/'runtime/source_pose/pose_probe.py');cp(I/'audit/independent_targets/adapter.py',R/'runtime/physical/independent_adapter.py')
for n in ['collect_pair.py','prepare_pair.py','track_shared.py','tracking_plan.py','score_one.py','make_triptych.py','make_showcase.py','summarize.py','common.py']:
 text=(P/'scripts'/n).read_text().replace('r66','r74').replace('R66','R74');(R/'scripts'/n).write_text(text)
p=R/'scripts/common.py';t=p.read_text();start=t.index('PAIR_KEYS=');end=t.index('\ndef read',start)
keys=tuple(p['pair_key'] for p in json.loads((G/'design/PAIR_DEFINITIONS.json').read_text())['pairs']);t=t[:start]+f"PAIR_KEYS={keys!r}\nSOURCES=PAIR_KEYS;MOTIONS=('chest','crouch','rotate');METHODS=('native','forced');INDICES=list(range(0,147,3));METRIC=ROOT/'runtime/official_metric'"+t[end:];t=t.replace("g.get('prompt_version')=='R49_original'","g.get('prompt_version')=='P1'");p.write_text(t)
# Remove legacy source cache import path: this package requires fresh source tracking.
p=R/'scripts/score_one.py';t=p.read_text().replace('from source_cache import validate_reuse\n','');t=t.replace(" if role=='reference' and (folder/'R74_SOURCE_REUSE.json').exists():validate_reuse(folder,action,config)\n else:\n",' if True:\n');p.write_text(t)
# Administrative rendering supports existing FFmpeg4; image/audio/time filters unchanged.
p=R/'scripts/make_triptych.py';p.write_text(p.read_text().replace("'-fps_mode','vfr'","'-vsync','vfr'"))
for f in ['scientific_contract.json','deploy_manifest.json']:cp(G/'configs'/f if f=='scientific_contract.json' else G/f,R/'configs'/('producer_scientific_contract.json' if f=='scientific_contract.json' else 'producer_deploy_manifest.json'))
cp(G/'design/PAIR_DEFINITIONS.json',R/'configs/PAIR_DEFINITIONS.json');cp(G/'design/FIXED_8_CANDIDATES.json',R/'configs/FIXED_8_CANDIDATES.json')
defs=json.loads((G/'design/PAIR_DEFINITIONS.json').read_text())['pairs'];pairs=[];sources=[]
for p in defs:
 a=p['motion_source_id'];pairs.append({'pair_key':p['pair_key'],'motion_source_id':a,'original_pair_id':p['original_pair_id'],'group':p['group'],'reference_id':f'human/{a}/000','source_sha256':p['source']['original_sha256'],'prepared_source_sha256':p['source']['video_sha256'],'portrait_sha256':p['portrait_sha256'],'prompt_sha256':p['prompt_sha256']})
 if a not in [x['id'].split('/')[1] for x in sources]:
  for suffix in ['video.mp4','provenance.json']:cp(G/'inputs'/f'source_{a}_{suffix}',R/'runtime/source_videos'/f'source_{a}_{suffix}')
  cp(G/'inputs'/p['source']['original'],R/'runtime/official_metric/inputs'/f'{a}.mp4')
  sources.append({'id':f'human/{a}/000','role':'reference','file':f'inputs/{a}.mp4','sha256':p['source']['original_sha256'],'frames':49,'pts_seconds':[i/8 for i in range(49)],'original_frame_indices':list(range(49)),'original_fps':8,'official_source_url':p['source_asset']['pinned_url'],'id_scope':'motion-source tracker cache; actual official target-pair recorded separately'})
put(R/'runtime/official_metric/SOURCE_INPUTS.json',{'schema':'r74-three-official-source-inputs-v1','inputs':sources,'selection_sha256':sha(G/'design/FIXED_8_CANDIDATES.json')})
freeze=json.loads((P/'runtime/official_metric/RUNTIME_FREEZE.json').read_text());freeze['files']['SOURCE_INPUTS.json']={'sha256':sha(R/'runtime/official_metric/SOURCE_INPUTS.json'),'bytes':(R/'runtime/official_metric/SOURCE_INPUTS.json').stat().st_size};freeze.update(phase='R74 CPU preparation, fresh .41 tracks pending',revision=5,previous_freeze_sha256=sha(P/'runtime/official_metric/RUNTIME_FREEZE.json'),change='Only source-input metadata selects three original official clips; all numerical code, weights and frame-release files unchanged.');put(R/'runtime/official_metric/RUNTIME_FREEZE.json',freeze)
c=json.loads((P/'configs/contract.json').read_text());c.update(schema='r74-official-six-mf-consumer-v1',pairs=pairs,motion_sources=['chest','crouch','rotate'],source_tracking_policy='fresh41_all3_sources_and12targets; no historical track import',root_host41='/data3/researcher/h3_runs/flexiact_official_six_metrics_r74_20261018',root_host9=None,producer_root_host41='/data3/researcher/h3_runs/timing_flexiact_official_six_r74_20261018',producer_root_local=str(G),producer_contract_sha256=sha(R/'configs/producer_scientific_contract.json'),producer_seal_sha256=sha(G/'deploy_manifest.json'),official_runtime_freeze_sha256=sha(R/'runtime/official_metric/RUNTIME_FREEZE.json'),evaluation={'official_csv_pairs':6,'distinct_motion_sources':3,'new_motion_sources':0,'missing':None,'physical_common_support_retained':True,'physical_independent_targets_additional':True,'edit_success_and_motion_identity':'PENDING_HUMAN_REVIEW'})
c.pop('reuse_r65',None);put(R/'configs/contract.json',c)
physical=json.loads((F/'configs/contract.json').read_text())['pose_protocol'];external={k.split('/comfyui_controlnet_aux/',1)[1]:v for k,v in physical['frozen_external'].items() if '/comfyui_controlnet_aux/' in k}
put(R/'configs/physical_protocol.json',{'aux_root':'/data3/researcher/ComfyUI/custom_nodes/comfyui_controlnet_aux','external_relative_sha256':external,'geometry':physical['geometry'],'extraction':physical['extraction'],'threads':4,'timeout_seconds':300,'source_tracking':'fresh CPU .41 same current source/target provenance','physical_numeric_freeze_sha256':sha(R/'runtime/physical/FREEZE.json'),'physical_original_evaluator_sha256':sha(R/'runtime/physical/evaluate.py'),'pose_probe_sha256':sha(R/'runtime/source_pose/pose_probe.py'),'validator_sha256':sha(R/'runtime/source_pose/remote_one.py'),'independent_adapter_sha256':sha(R/'runtime/physical/independent_adapter.py'),'fixed_windows':'original frozen evaluator all views; no output-selected windows','shared_cpu_lock':'/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock'})
# Proof of actual inherited numerics, no claims based on renamed administrative modules.
files={}
for folder,parent in [('runtime/official_metric',P),('runtime/release',P),('runtime/physical',F)]:
 for p in (R/folder).rglob('*'):
  before=parent/p.relative_to(R)
  if p.is_file() and p.suffix=='.py' and before.is_file():
   assert sha(p)==sha(before),(p,before);files[str(p.relative_to(R))]={'sha256':sha(p),'parent':str(before)}
for dest,src in [('runtime/source_pose/pose_probe.py',I/'vendor/pose_probe.py'),('runtime/source_pose/remote_one.py',F/'runtime/source_pose/remote_one.py'),('runtime/physical/independent_adapter.py',I/'audit/independent_targets/adapter.py')]:files[dest]={'sha256':sha(R/dest),'parent':str(src)}
put(R/'configs/NUMERICAL_INHERITANCE.json',files)
print('prepared',len(pairs),'pairs',len(sources),'sources',len(files),'numeric Python files')
