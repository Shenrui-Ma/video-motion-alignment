"""Narrow v1 pose recovery; immutable data and exact19-field provenance gate."""
import time
from contract import *
OLD_SCRIPT='b0eb01e8a0d24049cff8880dc3f356a177ada760cc919a31cfbd11ee7f82fa89'
NEW_SCRIPT='04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f'

def check_pose_provenance(source,generated,source_video_sha):
 e=read(HERE/'RECOVERY_EVIDENCE.json');bridge=read(HERE/'SOURCE_POSE_PROVENANCE_EXCEPTION.json')
 require(source==e['source_provenance'] and generated==e['generated_provenance'],'unregistered pose provenance fields')
 require(source['script_sha256']==OLD_SCRIPT and generated['script_sha256']==NEW_SCRIPT,'unregistered pose script pair')
 require(len(source)==len(generated)==20 and {k:v for k,v in source.items() if k!='script_sha256'}=={k:v for k,v in generated.items() if k!='script_sha256'},'19 remaining pose fields differ')
 require(bridge.get('passed') is True and bridge['frames']==141 and source_video_sha==bridge['source_sha256'] and bridge['old_default_RGB_sha256']==bridge['new_explicit_ffmpeg_single_thread_RGB_sha256'],'source opening-mode141RGB bridge mismatch')
 return {'source_script':OLD_SCRIPT,'generated_script':NEW_SCRIPT,'other19_fields_exact':True,'opening_mode_bridge_sha256':sha(HERE/'SOURCE_POSE_PROVENANCE_EXCEPTION.json')}

def check_legacy(p):
 r=p['recovery'];old=Path(r['legacy_remote']);require(sha(old/'FREEZE.json')==r['legacy_freeze_sha256'] and sha(old/'BINDING.json')==r['legacy_binding_sha256'],'legacy seal/binding changed')
 for rel,d in read(old/'FREEZE.json')['files'].items():require(sha(safe(old,rel))==d,'legacy frozen payload changed '+rel)
 require(sha(HERE/'RECOVERY_EVIDENCE.json')==r['evidence_sha256'] and sha(HERE/'SOURCE_POSE_PROVENANCE_EXCEPTION.json')==r['opening_mode_bridge_sha256'],'registered recovery evidence changed')
 e=read(HERE/'RECOVERY_EVIDENCE.json');arc=Path(r['archive_root']);run=p['cases'][0]['run_id']
 require(str(arc)==e['archive_root'] and run==e['run_id'],'recovery archive identity')
 for path,key in ((old/'archive_receipts'/f'{run}.json','archive_receipt_sha256'),(arc/'RUN_GATE.json','archive_gate_sha256'),(arc/'FILE_INVENTORY.json','archive_inventory_sha256')):require(sha(path)==e[key],'legacy archive anchor changed')
 return e

def check_cached(folder,video,source,e):
 folder=Path(folder);files={str(f.relative_to(folder)) for f in folder.rglob('*') if f.is_file()};require(files==set(e['files']),'failed pose exact inventory differs')
 for rel,v in e['files'].items():
  f=safe(folder,rel);require(f.stat().st_size==v['bytes'] and sha(f)==v['sha256'],'cached pose dependency changed '+rel)
 pose=safe(folder,e['pose_relative']);require(sha(pose)==e['pose_sha256'] and sha(video)==e['video_sha256'] and sha(source)==e['source_pose_sha256'],'cached pose/video/source binding')
 raw=read(pose);v=raw['video'];require(v['sha256']==e['video_sha256'] and [v['width'],v['height'],v['container_frame_count'],v['fps']]==[1312,736,141,24],'cached video geometry')
 require(raw['extraction']=={'start':0,'end':None,'stride':1} and raw['statistics']==e['statistics'] and raw['statistics']['processed_frames']==141,'cached extraction configuration')
 require(len(raw['frames'])==141 and [f['frame'] for f in raw['frames']]==list(range(141)) and all(abs(f['time_s']-i/24)<1e-8 for i,f in enumerate(raw['frames'])),'cached physical frame mapping')
 return pose,raw

def recover_pose(root,arc,p,owner):
 started=time.monotonic();e=check_legacy(p);verify_producer_sources(root,p['producer_manifest_sha256'],all_files=True);from outcome import current,checked_external
 run,video,sourcevideo,source,deps=current(root,arc,p);checked_external(p);folder=phase_folder(arc,'pose');pose,raw=check_cached(folder,video,source,e);from scan_current_pose import valid_pose;require(valid_pose(pose)==raw,'cached pose semantic schema changed');provenance=check_pose_provenance(read(source)['provenance'],raw['provenance'],sha(sourcevideo))
 verify_source_archive(root,arc,owner,run);checked_external(p);check_cached(folder,video,source,e)
 metadata={'pose_relative':e['pose_relative'],'pose_sha256':e['pose_sha256'],'video_sha256':e['video_sha256'],'verified_dependencies':deps,'elapsed_seconds':time.monotonic()-started,'pose_extraction_reused_seconds':raw['statistics']['elapsed_s'],'model_invocations':0,'no_numerical_pose_changed':True,'recovery_evidence_sha256':sha(HERE/'RECOVERY_EVIDENCE.json'),'provenance_exception':provenance}
 receipt=seal_phase(arc,'pose',metadata);save(HERE/'phase_receipts'/f'{run}_pose.json',{'result_sha256':sha(folder/'COMPLETE.json'),'inventory_sha256':sha(arc/'FILE_INVENTORY.json')});return {'phase':'recover_pose','passed':True,'pose_sha256':e['pose_sha256'],'model_invocations':0,'metadata':metadata}
