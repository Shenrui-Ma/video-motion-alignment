"""Reuse the 23 failed-final files; append explicit limited completion only."""
import argparse,time
from common import *

def prepare_summary(p,legacy,arc):
 run=p['run'];case=legacy.case_for(run);e=read(HERE/'INPUT_EVIDENCE.json');r=read(HERE/'RESULTS.json')
 ledger=read(arc/'DECISION_LEDGER.json');gate=read(arc/'RUNTIME_GATE.json');c=gate['cases'][0]
 require(gate==e['runtime_gate'] and gate['status']=='pass' and len(gate['cases'])==1 and c['run']==run and c['all_OFF_final_exact'] is True and c['NFE']==20 and c['mask']==[],'final AV equality gate differs')
 require(ledger['active_indices']==[] and ledger['NFE']==20 and ledger['Euler_updates']==20 and len(ledger['rows'])==20 and all(x['chosen']=='native' for x in ledger['rows']),'not actual all-OFF20')
 pixels=read(arc/'final/media/PIXELS_AND_MEDIA.json');require(pixels==e['existing_pixels'],'saved pixel evidence differs')
 require(len(pixels['RGB_frame_sha256']['AUTO'])==141 and pixels['RGB_frame_sha256']['AUTO']!=pixels['RGB_frame_sha256']['normal_native'] and r['RGB_equality'] is False,'expected failed RGB gate differs')
 require(read(arc/'final/media/PLAYBACK_GATE.json')==e['playback_gate'],'saved playback differs')
 require(r['passed_input_integrity'] is True and r['input_evidence_sha256']==p['input_evidence_sha256'],'pixel diagnostic input proof')
 for name,row in e['videos'].items():require(sha(row['path'])==row['sha256'],'actual compared video changed '+name)
 pose=arc/'final/pose'/f'{run}_00001_.pose.json';raw=read(pose);source=arc/'configs/source.pose.json';video=Path(e['videos']['AUTO']['path']);require(sha(pose)==e['current_pose_sha256'] and raw['video']['sha256']==sha(video) and sha(source)==p['source_pose_sha256'],'actual source/video/pose binding')
 # Pure metadata function; no pose extractor or numeric evaluator is called.
 import evaluate
 parent=legacy.LEGACY/legacy.P['parents']['normal_native']['pose'];require(sha(parent)==legacy.P['parents']['normal_native']['pose_sha256'],'parent pose changed')
 provenance=evaluate.check_provenance(read(source)['provenance'],raw['provenance'],[read(parent)['provenance']],read(source)['video']['sha256'])
 whole=read(arc/'final/WHOLE_SCAN_SUMMARY.json');require(whole==e['whole_scan_summary'],'existing scan summary differs')
 common={}
 for f in sorted((arc/'final').glob('COMMON_*.json')):
  d=read(f);label,conf=f.stem[len('COMMON_'):].rsplit('_',1);common.setdefault(label,{})[conf]={'status':d['status'],'rows':len(d['rows'])}
 audit=read(arc/'audit/counterfactual'/f'{run}.json')['counterfactual'];job=read(arc/'logs'/f'{run}_job.json');capture=read(arc/'audit/x0'/run/'manifest.json')
 efficiency={'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'actual_NFE':20,'actual_Euler_updates':20,'current_Native_observations':20,'Full_branches':0,'observer_wall_seconds':sum(x['wall_seconds'] for x in audit['measurements']),'branch_model_seconds_synchronized':sum(x['model_seconds_synchronized'] for x in audit['branches']),'branch_condition_copy_hash_seconds':sum(x['condition_copy_hash_seconds'] for x in audit['branches']),'chosen20_capture_seconds':sum(x['capture_seconds'] for x in capture['captures']),'interpretation':'Existing timings only; old failed-final pose/metric wall not reconstructed; scopes overlap.'}
 summary={'video':str(video),'video_sha256':sha(video),'pose':str(pose),'pose_sha256':sha(pose),'source_pose_sha256':sha(source),'pose_provenance':provenance,'fixed_windows_scope':case['window_scope'],'whole_scan':whole['results'],'common_support':common,'NFE':20,'active_indices':[],'ON_episodes':ledger['ON_episodes_inclusive'],'restart_count':ledger['restart_count'],'normal_any_intervention':False,'all_OFF_final_AV':'independently checked actual final normalized video/audio tensors by verify_single','efficiency':efficiency,'manual_quality_review':'pending fixed frames/fullvideo inspection; pose alone not identity/shape success','scope':p['scope'],'original_failure_sha256':p['old_failure_sha256'],'RGB_diagnostic_sha256':p['rgb_results_sha256'],'RGB_difference':r['aggregate'],**scope_fields()}
 check_scope(summary);return summary,efficiency

def main():
 a=argparse.ArgumentParser();a.add_argument('--execute',action='store_true');args=a.parse_args()
 if not args.execute:print('Preparation only; --execute and explicit root limited-scope binding required.');return
 p,root,old,legacy=bootstrap(True);approve(p);started=time.monotonic();run=p['run']
 with legacy.locked():
  arc,anchors,receipt,inv,owner=legacy.adopted(run)
  require(not (arc/'CPU_COMPLETE.json').exists() and not (arc/'DERIVED_FILES.json').exists(),'already/partially committed: explicit reviewed resume required')
  checked_partial(arc/'final',p['partial_files'])
  legacy.verify_source_archive(root,arc,owner,run);legacy.verify_producer_sources(root,p['producer_manifest_sha256'],all_files=True)
  audit=read(arc/'audit/counterfactual'/f'{run}.json');require(len(audit['counterfactual']['measurements'])==20,'20 observations required')
  for i,m in enumerate(audit['counterfactual']['measurements']):
   d=legacy.index_for(anchors,receipt,inv,run,i);require(legacy.index_measurement(root,arc,run,i,m,inv)==d,'actual observation index differs');legacy.validate_replay(read(arc/'observer_replay'/f'{i:03d}.json'),d['expected_replay'])
  expected=set(inv)|{'FILE_INVENTORY.json','RUN_GATE.json','RUNTIME_GATE.json','DECISION_LEDGER.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json'}|{f'observer_replay/{i:03d}.json' for i in range(20)}|{'final/'+n for n in p['partial_files']}
  if (arc/'ADMIN_RELEASE_ACCEPTANCE.json').exists():expected.add('ADMIN_RELEASE_ACCEPTANCE.json')
  require(files(arc)==expected,'precommit raw+partial exact inventory differs')
  original_snapshot={n:sha(arc/n) for n in sorted(expected)}
  summary,efficiency=prepare_summary(p,legacy,arc)
  # All substantive computation already exists; only scalar bookkeeping is added.
  legacy.verify_source_archive(root,arc,owner,run);legacy.verify_producer_sources(root,p['producer_manifest_sha256'],all_files=True);checked_partial(arc/'final',p['partial_files'])
  require({n:sha(arc/n) for n in sorted(expected)}==original_snapshot,'existing bytes changed during recovery')
  save_new(HERE/'PRECOMMIT.json',{'run':run,'owner':owner,'original_and_partial_files':original_snapshot,'scope':scope_fields(),'protocol_sha256':sha(HERE/'PROTOCOL.json')})
  save_new(arc/'final/EFFICIENCY.json',efficiency);save_new(arc/'final/FINAL_SUMMARY.json',summary)
  done=dict(summary,passed=True,run_id=run,owner=owner,no_GPU=True,cleanup_claim=False,observer_replay_indices=list(range(20)),recovery_seconds=time.monotonic()-started,derived_outputs=sorted('final/'+n for n in files(arc/'final')),completion_status='complete_with_original_RGB_gate_failed',recovery_protocol_sha256=sha(HERE/'PROTOCOL.json'))
  check_scope(done);save_new(arc/'CPU_COMPLETE.json',done)
  generated={n:sha(arc/n) for n in sorted(files(arc)) if n not in inv and n not in ('DERIVED_FILES.json','ADMIN_RELEASE_ACCEPTANCE.json')};save_new(arc/'DERIVED_FILES.json',generated)
  legacy.validate_complete_inventory(arc);checked_partial(arc/'final',p['partial_files'],('EFFICIENCY.json','FINAL_SUMMARY.json'))
  save_new(HERE/'COMMIT_RECEIPT.json',{'passed':True,'run':run,'owner':owner,'completion_sha256':sha(arc/'CPU_COMPLETE.json'),'derived_inventory_sha256':sha(arc/'DERIVED_FILES.json'),'original_inventory_sha256':sha(arc/'FILE_INVENTORY.json'),'precommit_sha256':sha(HERE/'PRECOMMIT.json'),'old_partial_bytes_preserved':True,'elapsed_seconds':time.monotonic()-started,**scope_fields()})
 print(json.dumps({'status':'limited_final_complete','run':run,'seconds':time.monotonic()-started,**scope_fields()},allow_nan=False))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
