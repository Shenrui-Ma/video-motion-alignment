from pathlib import Path
import json, hashlib, time, math
from collections import Counter, defaultdict
ROOT=Path(__file__).resolve().parent
INV=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/inventory')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
# Explicit review-based classification; MF never determines task or visual class.
# PASS/PARTIAL/FAIL concern requested edit, scene and recognizable action content.
# Timing delay alone does not downgrade task acceptance. UNKNOWN = no independent task review recorded.
flex={
'flex_r65_fitness_fixed':('UNKNOWN','no_clear_improvement','Summary covers arm timing only; identity/scene acceptance unrecorded.'),
'flex_r65_one_leg_fixed':('UNKNOWN','no_clear_improvement','Summary covers arm timing only; identity/scene acceptance unrecorded.'),
'flex_r66_human2animal_1__movie_man_11':('FAIL','task_invalid','Retained source braid; action stages reversed.'),
'flex_r66_human2animal_1__game_man_4':('FAIL','task_invalid','Mixed identity and wrong target background.'),
'flex_r66_fitness__game_man_4':('PARTIAL','no_clear_improvement','Identity succeeds; required white scene replaced with mountains.'),
'flex_r66_one_leg__movie_man_11':('PASS','no_clear_improvement','Core identity/scene/action sequence succeeds; hands and feet cropped limits timing review.'),
'flex_r66_human2animal_3__movie_man_11':('UNKNOWN','no_clear_improvement','Identity/scene acceptance explicitly unknown; six-point action review close between versions.'),
'flex_r66_human2animal_3__game_man_4':('FAIL','task_invalid','Action order reversed and identity unclear.'),
'flex_r66_human2animal_2__movie_man_11':('FAIL','task_invalid','Cross-legged forward bend changed to pushup/kneeling.'),
'flex_r66_human2animal_2__game_man_4':('FAIL','task_invalid','Target identity absent.'),
'flex_r85_one_leg__movie_man_9_fixed':('PARTIAL','no_clear_improvement','Identity/scene succeed; additional palms-together action changes movement content.'),
'flex_r85_crouch__movie_man_5_fixed':('PARTIAL','no_clear_improvement','Partial identity and target white background absent.'),
'flex_r85_rotate__game_girl_1_fixed':('PARTIAL','no_clear_improvement','Identity/action succeeds; required target background only partly matches.'),
'flex_r101_human2animal_1__game_man_4_fixed':('PARTIAL','no_clear_improvement','Identity/scene succeed; terminal straight-arm arch replaced by elbow/chest lowering.'),
'flex_r104_fitness__game_man_4_fixed':('PASS','no_clear_improvement','Identity/scene/action sequence succeeds; overhead hands cropped.'),
'flex_r105_human2animal_2__movie_man_11_fixed':('PARTIAL','no_clear_improvement','Identity/scene/action class succeed; camera/amplitude differ. Hand-ground delay persists.'),
'flex_r104_human2animal_1__movie_man_11_fixed':('PARTIAL','no_clear_improvement','Identity/scene/action order succeed; view and amplitude differ.'),
}
ive={}
for i in ['r63_short_0210','r64_short_0092','r64_short_0114','r64_short_0126','r64_short_0392','r69_short_0230','r69_short_0263','r69_short_0352']:
 ive[i]=('FAIL','task_invalid','Existing review marks requested edit or original action content unsuccessful.')
for i in ['r69_short_0370','r73_short_0035','r73_short_0065','r73_short_0135','r73_short_0344','r89_short_0085','r89_short_0131','r89_short_0268','r89_short_0274','r89_short_0343','r96_long_0173','r89_short_0178','r99_short_0210','r99_short_0230','r102_short_0263','r108_short_0392']:
 ive[i]=('PASS','no_clear_improvement','Existing review accepts edit and recognizable action; no clear added alignment benefit within visible coverage.')
ive.update({
'r73_short_0252':('PASS','local_timing_improvement','Mask reach/grasp/strap phases earlier, source-matched locally; not a whole-video success count.'),
'r89_short_0358':('PASS','local_timing_improvement','First bottle lowering/return improves locally; final mouth departure remains late.'),
'r97_short_0358_extended':('PASS','local_timing_improvement_repeated_source','Actual full review has source/native/extended intervals: partial early improvement persists; no added gain over prior fixed. Repeated drinking source, not a new independent source.'),
'r100_short_0114':('PARTIAL','small_phase_change_partial_task','About one frame earlier for first two bounces; camera/crop mismatch persists.'),
'r99_short_0352':('PASS','unwanted_action_removed','Extra pointing gesture at frames66–73 removed; action-content improvement, no numeric tempo claim.'),
'r107_long_0174':('PASS','no_clear_whole_event_improvement','Requested clothing edit succeeds. Full joint turn-arm event and early delays remain; timing is assessed separately.'),
'r111_long_0174_spatial':('PARTIAL','regression_changed_action','Clothing change succeeds but unrequested hat/book removal and altered path make registered events incomparable.'),
})
assert len(flex)==17 and len(ive)==31
allmap={**flex,**ive};rows=[];excluded=[];bindings={}
for b in ['flexiact','ivebench']:
 src=INV/(b+'.json');snapshot=ROOT/(b+'_inventory_snapshot.json')
 if not snapshot.exists():snapshot.write_bytes(src.read_bytes())
 data=load(snapshot);bindings[b]={'snapshot':str(snapshot),'sha256':sha(snapshot),'original_path':str(src)}
 for r in data['items']:
  if not (r.get('guidance_activation')=='active' and r.get('guided_video_path') and r.get('ordinary_video_path')):
   excluded.append({k:r.get(k) for k in ['id','benchmark','source_id','guidance_activation','comparison_kind']});continue
  ident=r['id'];assert ident in allmap
  task,effect,note=allmap[ident];mf=r['quantitative_metrics']['motion_fidelity'];a=mf.get('native');z=mf.get('guided')
  assert isinstance(a,(int,float)) and isinstance(z,(int,float)) and math.isfinite(a+z)
  assert Path(r['ordinary_video_path']).is_file() and Path(r['guided_video_path']).is_file()
  delta=z-a;direction='up' if delta>0 else 'down' if delta<0 else 'equal'
  rows.append({'id':ident,'benchmark':b,'source_id':r['source_id'],'variant':r.get('variant'),'method':r.get('method_label'),'task_acceptance':task,'manual_effect_class':effect,'classification_note':note,'review_status':r.get('review_status'),'review_status_code':r.get('review_status_code'),'review_summary':r.get('review_summary'),'evidence_paths':r.get('evidence_paths'),'ordinary_video_path':r['ordinary_video_path'],'guided_video_path':r['guided_video_path'],'mf_native':a,'mf_guided':z,'mf_delta':delta,'mf_direction':direction,'mf_protocol':mf.get('protocol'),'metric_source_files':mf.get('source_files',[]),'metric_source_sha256':mf.get('source_sha256',{})})
assert len(rows)==48 and set(allmap)=={r['id'] for r in rows}
def summary(rs):
 return {'version_pairs':len(rs),'distinct_source_ids':len({r['source_id'] for r in rs}),'mf_direction':dict(Counter(r['mf_direction'] for r in rs)),'task_acceptance':dict(Counter(r['task_acceptance'] for r in rs)),'manual_effect':dict(Counter(r['manual_effect_class'] for r in rs)),'task_by_mf':{t:dict(Counter(r['mf_direction'] for r in rs if r['task_acceptance']==t)) for t in ['PASS','PARTIAL','FAIL','UNKNOWN']},'manual_effect_by_mf':{e:dict(Counter(r['mf_direction'] for r in rs if r['manual_effect_class']==e)) for e in sorted({r['manual_effect_class'] for r in rs})},'mean_mf_delta_descriptive_only':sum(r['mf_delta'] for r in rs)/len(rs)}
result={'schema':'completed-active-guidance-version-pairs-v1','created_unix':time.time(),'count_unit':'One inventory version ordinary/primary guided pair. Repeated source videos, prompts, methods and seeds are retained. This is a retrospective exploration ledger, not independent test-set sampling. Extra stored control scores already represented elsewhere are not counted again.','classification_scope':'Read-only synthesis of existing task/frame reviews. No new visual annotation. PASS means requested edit/required scene/recognizable action are accepted at recorded review coverage; pure timing delay is evaluated separately. PARTIAL preserves remaining view, scene, amplitude or content faults. UNKNOWN denotes missing task validation. These labels are not official benchmark acceptance scores.','mf_direction_definition':'guided-native strict numeric sign; equal means exact equal. A positive sign does not imply statistical significance, task success or event timing improvement. Two benchmark MF protocols remain separate.','input_bindings':bindings,'by_benchmark':{b:summary([r for r in rows if r['benchmark']==b]) for b in bindings},'rows':rows,'excluded_rows':excluded,'excluded_count':len(excluded),'classification_source':str(Path(__file__))}
save(ROOT/'RESULT.json',result)
lines=['已完成实际引导对照的 CPU 汇总','',result['count_unit'],'','计数单位是实验版本，同源重跑和不同方法版本保留；此表用于阶段判断。普通/引导均已成片，guidance_activation=active；零触发、提示词、solver 对照与仅普通成片列在排除清单。','']
for b,s in result['by_benchmark'].items():
 lines.extend([f"{b}: {s['version_pairs']} 组版本 / {s['distinct_source_ids']} 个原源视频；MF 上升 {s['mf_direction'].get('up',0)}、下降 {s['mf_direction'].get('down',0)}、相同 {s['mf_direction'].get('equal',0)}。",'任务/内容验收：'+json.dumps(s['task_acceptance'],ensure_ascii=False),'验收分组内的 MF 方向：'+json.dumps(s['task_by_mf'],ensure_ascii=False),'已有逐帧/抽帧审阅结论：'+json.dumps(s['manual_effect'],ensure_ascii=False),''])
lines.extend(['现有明确局部时间改善落在 IVE 的氧气面罩和饮酒两个源；坐姿人物额外手势减少属于动作内容改善。篮球仅约 1 帧的局部相位变化，基础构图仍有偏差，单列。FlexiAct 当前审阅尚无清楚新增时序改善。','MF 与这些人工结论方向可不同：面罩 MF 轻微下降、坐姿额外动作消除后 MF 下降；饮酒局部改善时 MF 上升。任务失败版本也可能 MF 上升，故保留任务验收与事件审阅两列。','R97 原始全帧记录包含普通/延长版区间，确认早段局部改善仍保留，但相对原固定版无额外收益；它与 R89 饮酒是同一源、同一个普通视频，重复版本单列。R111 改变路径且事件不可比，保留负结果。','源帧覆盖、遮挡和视角限制沿每条原 review_summary；PASS 并不代表全部像素/细动作都已验收。不同方法和版本混合的数值方向计数不作为最终方法平均效果。'])
(ROOT/'SUMMARY.txt').write_text('\n'.join(lines)+'\n')
save(ROOT/'CHECKS.json',{'passed':True,'all_active_versions_classified':True,'all_48_pairs_have_finite_MF_and_existing_media':True,'all_48_ids_unique':len({r['id'] for r in rows})==48,'benchmark_sums_match':sum(s['version_pairs'] for s in result['by_benchmark'].values())==48,'result_sha256':sha(ROOT/'RESULT.json'),'script_sha256':sha(__file__)})
print(json.dumps(result['by_benchmark'],ensure_ascii=False,indent=2))
