"""Freeze two historical controls and event definitions before R150 outputs."""
import copy, hashlib
from pathlib import Path
from common import ROOT, PREVIOUS, read,write,bound,verify_record,require
OLD=ROOT.with_name('h3-guidance-schedule-eval-r149-20261020')
prior=read(PREVIOUS/'EVALUATION_MANIFEST.json');schedules=read(OLD/'EVALUATION_MANIFEST.json')['schedules']
mf=PREVIOUS/'mf_preparation';mfremote=read(mf/'configs/RUNTIME.json')['remote_root'];release=mf/'audit/FINAL_RELEASE_VERIFIED.json'
require(read(release)['passed'] is True,'Historical MF release required')
cases=[]
for original in prior['cases']:
 sid=original['source_id']
 if sid not in ['long_0039','long_0059']:continue
 c=copy.deepcopy(original)
 c.pop('R148',None);c['dataset']='IVEBench'
 c['title']='外观编辑 — 将书封改为蓝色' if sid=='long_0039' else '物体编辑 — 换成白色手帕擦眼'
 c['prompt_source_label']='沿用历史实验完整提示词，固定新旧对照'
 c['media']={k:v for k,v in c['media'].items() if k in ['source','native','fixed']}
 c['historical_runs']={r:{k:v for k,v in c['historical_runs'][r].items() if k in ['run_id','graph','router_node_50','history']} for r in ['native','fixed']}
 c['official_MF']={r:original['official_MF'][r] for r in ['native','fixed']}
 c['fixed_schedule']={'label':'时序引导 7–15','steps_0based':list(range(6,15)),'steps_1based':list(range(7,16))}
 r=c['historical_runs']['fixed']['router_node_50']['inputs'];require((r['step_start'],r['step_end'])==(6,15),'Historical schedule differs')
 c['invariant_router']={k:r[k] for k in ['mode','alpha','radius','time_offset','start_frame','end_frame','block_start','block_end']};c['phase_offset']=0
 c['events']=[{k:v for k,v in e.items() if k!='fixed_phase'} for e in c['events']]
 for e in c['events']:
  for arm in schedules:e[arm]=None
 c['event_rules']=['先核编辑、人物和场景，再核相同事件。','沿用R148之前已冻结的原事件，不按新输出更换。','事件缺失记null；保留全部相邻阶段和失败结果。']
 ip=mf/'cases'/sid/'INPUTS.json';inputs=read(ip);result=read(mf/'results'/sid/'fixed_phase.json')
 rp=mf/Path(result['source_report']['file']).relative_to(mfremote);report=read(rp);tp=rp.with_name('tracks.npz');g=c['geometry']
 require(inputs['source_full_sha256']==c['media']['source']['sha256'] and inputs['valid_frames']==g['valid_frames'] and inputs['crop_xywh']==g['crop_xywh'],'Source MF domain differs')
 require(bound(rp)['sha256']==result['source_report']['sha256'] and report['passed'] and bound(tp)['sha256']==report['tracks_sha256'],'Source cache differs')
 c['MF_source_cache']={'historical_inputs':bound(ip),'report':bound(rp),'tracks':bound(tp),'remote_report':result['source_report']['file'],'remote_tracks':str(Path(result['source_report']['file']).with_name('tracks.npz')),
 'source_full_sha256':inputs['source_full_sha256'],'source_score_sha256':inputs['source_score_sha256'],'source_frame_md5':inputs['source_frame_md5'],'selection_sha256':inputs['selection_sha256'],
 'official_commit':report['official_commit'],'checkpoint_sha256':report['checkpoint_sha256'],'tracker':report['tracker'],'prior_release':bound(release)}
 require(hashlib.sha256(c['prompt'].encode()).hexdigest()==c['prompt_sha256'],'Prompt changed')
 for v in [*c['media'].values(),*[r['graph'] for r in c['historical_runs'].values()],c['historical_pair_gate'],c['historical_review']]:verify_record(v)
 cases.append(c)
manifest={'schema':'r150-schedule-evaluation-v1','status':'PREPARED_NO_NEW_OUTPUT','historical_manifest':bound(PREVIOUS/'EVALUATION_MANIFEST.json'),'schedules':schedules,'display_index_base':1,'code_index_base':0,'roles':['source','native','fixed','selected_schedule'],'cases':cases,'ordered_overview_roles':['source','native','early','fixed','late','split','global_weak']}
p=ROOT/'EVALUATION_MANIFEST.json'
if p.exists():require(read(p)==manifest,'Existing manifest differs; archive before approved amendment')
else:write(p,manifest)
plan={'schema':'r150-frozen-event-evaluation-v1','source_event_manifest':bound(p),'rules':['All historical event definitions and intervals remain fixed.','New outputs pending actual per-job gate; release remains pending until true aggregate+COMPLETE+ROOT_EXIT.','MF reuses exact source tracks; no existing source/native/fixed retracking.'],
'cases':[{ 'source_id':c['source_id'],'valid_frames':c['geometry']['valid_frames'],'events':c['events'],'phases':c.get('phases'),'full_frame_review':True} for c in cases]}
write(ROOT/'EVALUATION_PLAN.json',plan)
write(ROOT/'EVALUATION_FREEZE.json',{'schema':'r150-evaluation-freeze-v1','files':[bound(p),bound(ROOT/'EVALUATION_PLAN.json'),bound(ROOT/'audit/REUSE_ADAPTER.json')]})
print('Prepared',[(c['source_id'],c['geometry']['valid_frames']) for c in cases],'8 pending outputs, 0 new source trackers.')
