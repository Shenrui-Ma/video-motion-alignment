"""Freeze source/Native-only event evidence for selected extension tasks."""
from pathlib import Path
import json,datetime,hashlib
from common import ROOT,read,write,bound
B=ROOT.parent;manifest=read(ROOT/'EVALUATION_MANIFEST.json');selected=read(ROOT/'SELECTED_TASKS.json')
entries=[]
def event(i,label,s,n,kind='visible_action_interval'):
 return {'id':i,'label':label,'measurement_kind':kind,'source_interval_inclusive':s,'native_interval_inclusive':n,'new_outputs':{a:None for a in ['fixed7_15_new','early','late','split','global_weak']},'absent_event_rule':'null with absence reason; never infinite delay or substitute a different action'}
for c in manifest['cases']:
 es=[]
 labels={'hand_approaches_eye':'抬手接近眼部','eye_wiping_contact':'手帕接触眼部开始擦拭','hand_leaves_face':'手帕撤离脸部'}
 for e in c['events']:
  q=event(e['id'],labels.get(e['id'],e['label']),e['source'],e['native']);q['historical_fixed_interval_inclusive']=e['fixed'];es.append(q)
 entries.append({'candidate_id':c['source_id'],'source_id':c['source_id'],'valid_frames':c['geometry']['valid_frames'],'search_frame_domain':[0,c['geometry']['valid_frames']-1],'native_timing_status':'clear_delay','events':es,'evidence':[c['historical_review'],c['historical_pair_gate']]})
for sid,labels in [('short_0085',['上胸持杯与微笑','杯子逐渐下放至画面下沿','低位持杯与微笑继续']),('short_0274',['由前倾低头逐渐抬起','身体站直与抬头','站立后视线与上身轻微调整'])]:
 p=B/'h3-ive-subject-capacity-metrics-r89-20261018/audit'/('visual_review_'+sid.replace('_',''))/'REVIEW.json';r=read(p);es=[]
 for i,row in enumerate(r['events'][:3]):
  span=row.get('frames',row.get('source_indices'))
  e=event('phase_'+str(i+1),labels[i],span,span,'previously_reviewed_broad_phase_interval')
  e['precision_note']='旧记录支持此宽阶段近同步；该区间不是精确动作起始边界，勿把区间中点当已测时差。新输出先按固定阶段/全片检查保留性，只有对源和Native同定义复核后才新增边界数值。'
  e['instant_event_boundary_source']=None;e['instant_event_boundary_native']=None
  es.append(e)
 entries.append({'candidate_id':'r89_'+sid,'source_id':sid,'valid_frames':66 if sid=='short_0085' else 72,'search_frame_domain':[0,65 if sid=='short_0085' else 71],'native_timing_status':'no_clear_delay_preservation_control','events':es,'evidence':[bound(p)]})
p=B/'h3-musk-real-dance-pair-20261014/analysis/pair_visual_review.json';r=read(p);es=[]
for key,label in [('face_sweep','手臂横过脸部'),('temple_adjacent_hand','手靠近眼侧/太阳穴'),('hand_release','手离开头部')]:
 v=next(x for x in r['landmarks'] if x['landmark']==key);e=event(key,label,v['source_frames_inclusive'],v['baseline_frames_inclusive']);e['uncertainty_frames']=v['boundary_uncertainty_frames_plus_minus'];es.append(e)
entries.append({'candidate_id':'musk05','source_id':'05_real_megumi_v','valid_frames':141,'search_frame_domain':[0,140],'detail_window':[35,105],'native_timing_status':'clear_delay','events':es,'evidence':[bound(p)],'legacy_weight3_is_not_fixed':True})
p=B/'h3-short-event-switching-20261013/REPORT.txt'
entries.append({'candidate_id':'firefly06','source_id':'06_anime_eye_insert','valid_frames':141,'search_frame_domain':[0,140],'detail_window':[30,80],'native_timing_status':'early_local_action_relation_missing',
 'events':[event('early_eye_insert','第一次短暂手—眼/上脸插入',[39,44],None),event('later_v_pose_and_leg_raise','随后较长眼旁V形手势与抬腿',[54,68],[52,67])],
 'native_absence_evidence':'A seed1312在36–41为较低胸肩旁手势、42–46向外指；其手—眼关系缺失，不将较低手势填成延后眼旁动作。','evidence':[bound(p)],'legacy_weight3_is_not_fixed':True})
p=B/'h3-four-pair-evidence-review-20261015/sam07/motion_review.json';r=read(p)
labels=['手在口鼻旁且后腿保持弯起','手从口鼻旁向上离开','后弯腿放下']
es=[]
for i,v in enumerate(r['landmarks']):
 e=event('landmark_'+str(i+1),labels[i],v['source_frames'],v['baseline_frames']);e['uncertainty_frames']=v['uncertainty_frames'];es.append(e)
entries.append({'candidate_id':'sam07','source_id':'07_real_ary_v','valid_frames':141,'search_frame_domain':[0,140],'detail_window':[45,95],'native_timing_status':'clear_local_delay','events':es,'evidence':[bound(p)],'legacy_weight3_is_not_fixed':True})
assert {e['candidate_id'] for e in entries}=={x['candidate_id'] for x in selected['selected']}
doc={'schema':'r150-selected-source-native-event-freeze-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inputs':'Existing source and Native records only; no R150 output viewed','fps':24,'index_base':0,'interval_endpoints':'inclusive','full_clip_quality_review_required':True,'time_error_rule':'Only same named action and comparable boundary may yield signed frame difference; missing=null. Broad phase ranges remain phases.','selection':bound(ROOT/'SELECTED_TASKS.json'),'cases':entries}
write(ROOT/'EVALUATION_EVENTS.json',doc)
write(ROOT/'audit/EVENT_FREEZE.json',{'record':bound(ROOT/'EVALUATION_EVENTS.json'),'new_output_observation_used':False,'case_count':7,'event_count':sum(len(x['events']) for x in entries)})
print('Frozen7 cases',sum(len(x['events']) for x in entries),'events/phases; no new output data.')
