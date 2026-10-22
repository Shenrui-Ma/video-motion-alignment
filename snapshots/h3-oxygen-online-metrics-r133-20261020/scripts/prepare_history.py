"""Bind existing seed1703 media, events and scores; no model or network execution."""
from pathlib import Path
import json,hashlib,os,time
R=Path(__file__).resolve().parents[1];B=R.parent
C=B/'h3-oxygen-seed-replication-metrics-r113-host41-20261019'
M=B/'h3-ive-r113-seed-replication-mf-host41-20261020'
P=B/'h3-timing-oxygen-online-r133-20261020'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for v in iter(lambda:f.read(1048576),b''):h.update(v)
 return h.hexdigest()
def read(p):return json.loads(p.read_text())
def bound(p):return {'file':str(p),'sha256':sha(p)}
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def check(x):p=Path(x['file']);assert sha(p)==x['sha256'];return p
def link(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists():os.link(p,q)
 assert sha(q)==sha(p)
def local_remote(x):
 root=Path('/data4/researcher/h3_runs/ive_r113_seed_replication_mf_20261020')
 p=M/Path(x['file']).relative_to(root);assert sha(p)==x['sha256'];return p

def main():
 plan=R/'design/PRE_AUTORUN_PLAN.txt';plan.parent.mkdir(parents=True,exist_ok=True)
 if not plan.exists():plan.write_bytes((P/'design/PLAN.txt').read_bytes())
 source_input=C/'prepared/2026101703/MF_INPUTS.json';mi=read(source_input);mf=M/'cases/short_0252/INPUTS.json';m=read(mf)
 assert mi['seed']==2026101703 and mi['valid_frames']==98 and mi['total_frames']==107 and mi['physical_frame_indices']==list(range(98))
 assert mi['fps']==m['evaluation_fps']==24 and mi['crop_xywh']==m['crop_xywh']==[16,8,1280,720]
 assert m['valid_frames']==m['evaluation_frames']==98 and m['source_full_sha256']==mi['roles']['source']['full_video']['sha256']
 records={}
 for role in ['source','native','fixed']:
  rv=mi['roles'][role]
  for typ in ['full_video','score_video']:
   p=check(rv[typ]);link(p,R/'historical'/f'{role}_{typ}.mp4')
  records[role]={'full_video':bound(R/'historical'/f'{role}_full_video.mp4'),'score_video':bound(R/'historical'/f'{role}_score_video.mp4'),'frame_md5':rv['frame_md5']}
  if role=='source':
   rp=M/'cases/short_0252/tracks/source/REPORT.json';tr=rp.parent/'tracks.npz';r=read(rp)
   assert r['passed'] and sha(rp)==m['source_cache']['report_sha256'] and sha(tr)==m['source_cache']['tracks_sha256']==r['tracks_sha256']
   assert r['decoded_frame_md5']==rv['frame_md5'] and r['source_prepared_sha256']==m['source_full_sha256'] and r['source_score_sha256']==m['source_score_sha256'] and r['effective_frame_count']==98
  else:
   t=next(t for t in m['targets']if t['role']==f'seed2026101703_{role}')
   assert t['full_sha256']==rv['full_video']['sha256'] and t['score_sha256']==rv['score_video']['sha256']
   sp=M/f'results/short_0252/seed2026101703_{role}.json';s=read(sp)
   assert s['actual_generated_video_sha256']==rv['full_video']['sha256'] and s['source_full_sha256']==m['source_full_sha256'] and s['source_score_sha256']==m['source_score_sha256'] and s['valid_frames']==98
   assert s['case_input']['sha256']==sha(mf)
   rp=local_remote(s['target_report']);tr=rp.parent/'tracks.npz';r=read(rp)
   assert r['passed'] and sha(tr)==r['tracks_sha256'] and r['score_video']['sha256']==rv['score_video']['sha256'] and r['decoded_frame_md5']==rv['frame_md5']
   records[role]['official_MF']={'value':s['motion_fidelity'],'score_record':bound(sp),'reuse_only':True}
  assert r['official_commit']=='2dcf8900ee65197f43854c76f61c66a32bb8dbfc' and r['checkpoint_sha256']=='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
  records[role]['official_tracks']={'report':bound(rp),'tracks':bound(tr)}
 review=C/'audit/full98_review/2026101703/REVIEW.json';rv=read(review);assert rv['all_valid_frames_inspected'] and rv['examined_frames']==list(range(98))
 events=[]
 for index,e in enumerate(rv['events']):
  events.append({'id':['hands_leave_lap','grasp_yellow_mask','right_hand_raise'][index],'name':e['name'],'source_frames':e['source_frames'],'native_frames':e['native_frames'],'fixed_frames':e['fixed_frames'],'auto_frames':None,'auto_status':'NO_ACTUAL_OUTPUT','historical_note':e['note']})
 acceptance={'schema':'r133-pre-output-evaluation-plan-v1','historical_review':bound(review),'source_events':bound(C/'configs/PREREGISTERED_EVENTS.json'),'producer_plan_snapshot':bound(R/'design/PRE_AUTORUN_PLAN.txt'),'valid_frames':98,'fps':24,'events':events,'phase_pairs':[['hands_leave_lap','grasp_yellow_mask'],['grasp_yellow_mask','right_hand_raise']],'task_acceptance':['elderly woman identity','child and aircraft cabin retained','mask and grasp/raise action sequence retained','framing and unrequested changes checked over all98frames'],'missing_event_policy':'null; no invented event time','third_event_semantics':'right hand/strap to upper chest or face-side; not securely wearing the mask','new_auto_output_viewed':False,'same_source_count_increment':0,'historical_seed':2026101703,'render_groups':[['source','native','fixed','auto'],['source','native','auto'],['source','fixed','auto']],'captions':'black background with Chinese labels, same physical frame indices; no speed retiming','auto_runtime_audit':['all20step decisions incl UNKNOWN/no-candidate','ON and OFF decisions and reason','window/lag/confidence/gain','forward count20+ON and20Euler updates','same-current-state and RNG evidence at extra predictions','actual inputs/noise/condition bindings and prefix up to firstON','timing of H3/decoder/CPU pose and total','exact process and GPU release'], 'GPU_started_by_consumer':False}
 save(R/'configs/EVALUATION_PLAN.json',acceptance)
 gate=C/'incoming/actual/seed2026101703_PAIR_GATE.json';agg=C/'incoming/actual/AGGREGATE_GATE.json';release=C/'incoming/actual/ROOT_EXIT_RECEIPT.json'
 assert read(gate)['passed'] and read(agg)['passed'] and read(release)['passed']
 save(R/'configs/HISTORICAL_INPUTS.json',{'schema':'r133-historical-seed1703-bindings-v1','source_id':'short_0252','seed':2026101703,'fps':24,'valid_frames':98,'total_frames':107,'crop_xywh':[16,8,1280,720],'evaluation_indices':list(range(98)),'historical_roles':records,'official_MF_input_manifest':bound(mf),'consumer_input_manifest':bound(source_input),'pair_gate':bound(gate),'aggregate_gate':bound(agg),'producer_release':bound(release),'review':bound(review),'source_native_fixed_existing_presentation':bound(C/'showcase/2026101703/PRESENTATION.json'),'evaluation_plan':bound(R/'configs/EVALUATION_PLAN.json'),'score_policy':'Reuse exact historical source/native/fixed media, tracks and scores. Only a future actual auto video may need new tracking.','auto_contract_status':'WAITING_FOR_SEALED_POST_PREFLIGHT_AUTO_CONTRACT','created_unix':time.time()})
 save(R/'audit/HISTORY_READY.json',{'passed':True,'manifest':bound(R/'configs/HISTORICAL_INPUTS.json'),'evaluation_plan':bound(R/'configs/EVALUATION_PLAN.json'),'historical_media_count':3,'historical_scores_reused':{k:records[k]['official_MF']['value']for k in ['native','fixed']},'actual_auto_present':False,'GPU_started':False})
 print(json.dumps(read(R/'audit/HISTORY_READY.json')))
if __name__=='__main__':main()
