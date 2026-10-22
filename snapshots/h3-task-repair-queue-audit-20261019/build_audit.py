from pathlib import Path
import json,hashlib,re,datetime,collections
ROOT=Path(__file__).resolve().parent; BASE=ROOT.parent
SHOW=BASE/'h3-benchmark-all-results-showcase-20261018'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def write(name,obj): (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def rec(p):p=Path(p);return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
invs={}
for n in ['ivebench','flexiact','repair_index']:
 p=SHOW/'inventory'/f'{n}.json';raw=p.read_bytes();(ROOT/'snapshots'/p.name).write_bytes(raw);invs[n]=json.loads(raw)
items={x['id']:x for n in ['ivebench','flexiact'] for x in invs[n]['items']}
fail=[x for x in items.values() if '失败' in x.get('review_status','')+x.get('review_summary','')]
assert len(fail)==22,len(fail)
parent_dirs={
 'r55':'h3-timing-ivebench-native-r54-20261017','r63':'h3-timing-ivebench-forced-r63-20261018','r64':'h3-timing-ivebench-heldout-r64-20261018','r69':'h3-timing-ivebench-remaining-r69-20261018',
 'flex_r50':'h3-timing-flexiact-native-r49-20261017','flex_r49':'h3-timing-flexiact-native-r49-20261017','flex_r66':'h3-timing-flexiact-expanded-r66-20261018','flex_r85':'h3-timing-flexiact-expanded-r85-20261018'}
rows=[]
for x in fail:
 keyprefix=next(k for k in parent_dirs if x['id'].startswith(k+'_'));p=BASE/parent_dirs[keyprefix];c=load(p/'configs/scientific_contract.json')
 candidates=[v for v in c['cases'] if v.get('motion_source_id',v['source_id'])==x['source_id'] and (not x.get('reference_image_path') or Path(v.get('portrait','')).name==Path(x['reference_image_path']).name)]
 assert candidates,(x['id'],p)
 v=next((v for v in candidates if v.get('arm')=='native' or v['run_id'].endswith('_native')),candidates[0])
 targetsha=sha(x['reference_image_path']) if x.get('reference_image_path') else None
 taskkey=('FlexiAct::'+x['source_id']+'::'+Path(v['identity']).stem) if targetsha else ('IVEBench::'+x['source_id']+'::'+x['task'])
 row={'item_id':x['id'],'task_key':taskkey,'source_id':x['source_id'],'title':x['title'],'historical_variant':x['variant'],'historical_review_status':x['review_status'],'historical_review_summary':x['review_summary'],'reference_image':rec(x['reference_image_path']) if targetsha else None,'reference_identity':v.get('identity'),'prompt_version':v.get('prompt_version',c.get('prompt_version','P0_or_R49_original')),'prompt_sha256':hashlib.sha256(v['prompt'].encode()).hexdigest(),'actual_prompt':v['prompt'],'source_contract':rec(p/'configs/scientific_contract.json'),'run_id':v['run_id'],'historical_evidence':[rec(q) for q in x['evidence_paths'] if Path(q).is_file() and Path(q).suffix in ['.json','.txt'] and Path(q).stat().st_size<2000000]}
 rows.append(row)
bykey=collections.defaultdict(list)
for r in rows:bykey[r['task_key']].append(r)
assert len(bykey)==18
ive_specs={
 'short_0210':('r71_short_0210','basic_edit_repaired_guidance_running','R99','P1普通编辑已保住男人、蓝幕舞台和站立手势；当前补匹配固定引导。','six_selected_times'),
 'short_0230':('r80_short_0230','basic_edit_repaired_guidance_pending','R99','P1普通编辑改蓝及厨房操作保留；当前同条件引导尚未完成。','six_selected_times'),
 'short_0352':('r80_short_0352','basic_edit_repaired_guidance_pending','R99','P1普通编辑人物、场景与抬手回落保留；当前同条件引导尚未完成。','six_selected_times'),
 'short_0263':(None,'awaiting_new_native',None,'旧P0出现女孩，但书、吊椅及坐姿阅读消失；现有注册包未见对应P1修复。','existing_review_only'),
 'short_0092':(None,'awaiting_new_native',None,'旧P0植物未移除且挥手变手机近景；现有注册包未见对应P1修复。','existing_review_only'),
 'short_0114':(None,'new_native_repair_running','R100','R100已启动新的P1-local-v1普通编辑；需验收霓虹球、原运球路径和接触后决定guide/skip。R91旧准备包覆盖同任务，不另重复启动。','new_output_pending'),
 'short_0126':(None,'awaiting_new_native',None,'旧P0猫已添加但原伸展变摸猫近景；未见对应P1修复。作为动作保持研究优先级较低。','existing_review_only'),
 'short_0392':(None,'new_native_repair_queued','R100','R100第二条待普通编辑修复，先验收整个壁炉/雕花外框消除及人物手势保留。','new_output_pending')}
flex_specs={
 'chest__game_girl_1':('awaiting_new_native',None,'原R49/R50目标铠甲女性未实现，0触发输出沿用原失败。R74 chest/game_man_5目标图不同，不能替代本任务。'),
 'crouch__movie_man_4':('awaiting_new_native',None,'原R49动作/构图改变；R85 crouch/movie_man_5目标图不同，不能当此任务修复。'),
 'human2animal_1__movie_man_11':('awaiting_new_native',None,'原身份长辫保留且动作阶段顺序错配，未见此目标新P1成片。'),
 'human2animal_1__game_man_4':('identity_scene_repaired_motion_partial','R101','R98全147有效帧确认短黑发男性、服装装备与白背景成功；支撑形状/幅度仍不同，部分转折提前。R101待匹配固定引导，旧身份失败已被修复。'),
 'fitness__game_man_4':('awaiting_scene_repair',None,'身份主要完成，目标白背景变山地；原本大阶段接近同步。R94 game_man_5是另一人物任务。'),
 'human2animal_3__game_man_4':('awaiting_new_native',None,'目标替换不明显，低支撑到倒立顺序反转；未见此任务新P1成片。'),
 'human2animal_2__movie_man_11':('awaiting_new_native',None,'原坐姿前屈被俯卧支撑到跪姿代替；未见此任务新P1成片。'),
 'human2animal_2__game_man_4':('awaiting_new_native',None,'源人物保留、目标动漫失败且前屈延后；未见此任务新P1成片。'),
 'one_leg__movie_man_9':('motion_repair_prepared','R90','R85身份和目标场景主要完成，晚举臂及新增胸前合掌路径未修复；R90同输入/噪声P1普通编辑准备就绪。'),
 'crouch__movie_man_5':('awaiting_identity_scene_repair',None,'R85身份仅部分/不确定，目标白背景失败；两次下蹲及胸前手势原本大致同相。')}
latest_binding=[];queue=[]
for key,grp in bykey.items():
 r=grp[0];isive=key.startswith('IVEBench');sid=r['source_id']
 if isive:
  latest,state,planned,note,scope=ive_specs[sid]
 else:
  pair=sid+'__'+Path(r['reference_identity']).stem;state,planned,note=flex_specs[pair];latest='flex_r98_human2animal_1__game_man_4_task_repair' if pair=='human2animal_1__game_man_4' else None;scope='all_147_valid_frames' if latest else 'existing_review_only'
 q={'task_key':key,'source_id':sid,'task_title':r['title'],'historical_item_ids':[a['item_id'] for a in grp],'historical_prompt_versions':[{'item_id':a['item_id'],'version':a['prompt_version'],'sha256':a['prompt_sha256']} for a in grp],'current_state':state,'latest_repair_item_id':latest,'registered_followup':planned,'assessment':note,'assessment_scope':scope,'reference_identity':r['reference_identity'],'reference_image_sha256':r['reference_image']['sha256'] if r['reference_image'] else None,'needs_basic_edit_repair':not state.startswith('basic_edit_repaired') and state!='identity_scene_repaired_motion_partial'}
 if latest:
  x=items[latest];media=x.get('alternative_video_path') or x['ordinary_video_path'];ev=[rec(v) for v in x['evidence_paths'] if Path(v).is_file() and Path(v).suffix in ['.json','.txt'] and Path(v).stat().st_size<2000000]
  q['latest_actual_native_media']=rec(media);q['latest_actual_evidence']=ev;q['latest_variant']=x['variant'];q['latest_review_summary']=x['review_summary'];latest_binding.append(q)
 queue.append(q)
# Registered scientific-contract search is deliberately bounded to small known-project metadata.
registry=[]
for p in sorted(BASE.glob('h3-timing-*/configs/scientific_contract.json')):
 m=re.search(r'-r(\d+)-',str(p));num=int(m[1]) if m else 0
 if num<66:continue
 try:d=load(p)
 except (ValueError,OSError):continue
 hits=[]
 for c in d.get('cases',[]):
  sid=c.get('motion_source_id',c.get('source_id'));ident=Path(c.get('identity','')).stem
  for q in queue:
   if q['source_id']!=sid:continue
   if q['reference_identity']:
    if ident!=Path(q['reference_identity']).stem:continue
   elif c.get('original_task',{}).get('edit_prompt',c.get('prompt'))!=items[q['historical_item_ids'][0]]['task'] and c.get('source_id')!=q['source_id']:continue
   hits.append({'task_key':q['task_key'],'run_id':c.get('run_id'),'prompt_version':c.get('prompt_version',d.get('prompt_version'))})
 if hits:registry.append({'contract':rec(p),'hits':hits})
write('REGISTERED_MATCHES.json',registry)
# Verify actual input bytes, prompt-in-graph and linked input roles in the three requested successor packages.
successors=[]
for name in ['h3-timing-flexiact-fitness-pair-r94-20261018','h3-timing-flexiact-p1-control-r90-20261018','h3-timing-ive-event-candidates-r93-20261018']:
 p=BASE/name;c=load(p/'configs/scientific_contract.json');checks=[]
 for a in c['cases']:
  if a['arm']!='native':continue
  g=load(p/'configs/graphs'/f"{a['run_id']}.json");text_values=[v for n in g.values() for v in n.get('inputs',{}).values() if isinstance(v,str)]
  blobs=[]
  for fld in ['video','portrait','provenance']:
   if a.get(fld):
    z=rec(p/'inputs'/a[fld]);exp=a.get(fld+'_sha256');z.update({'role':fld,'expected_sha256':exp,'matches_contract':exp is None or exp==z['sha256']});assert z['matches_contract'];blobs.append(z)
  assert a['prompt'] in text_values
  checks.append({'source_id':a['source_id'],'run_id':a['run_id'],'geometry':a['geometry'],'valid_frames':a['valid_frame_count'],'prompt_sha256':hashlib.sha256(a['prompt'].encode()).hexdigest(),'prompt_in_actual_graph_exact':True,'inputs':blobs,'reference_image_count':sum(n['class_type']=='LoadImage' for n in g.values()),'reference_video_count':sum(n['class_type']=='LoadVideo' for n in g.values())})
 successors.append({'project':name,'contract':rec(p/'configs/scientific_contract.json'),'handoff':rec(p/'ROOT_HANDOFF.txt'),'runtime':load(p/'configs/runtime.json'),'checks':checks})
write('SUCCESSOR_INPUT_AUDIT.json',successors)
write('FAILURE_ROW_MAPPING.json',{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'selection':'Already-labeled failure status/summary from frozen inventory snapshot. This enumerates historical records, not a new visual verdict.','historical_row_count':len(rows),'deduplicated_tasks':len(queue),'rows':rows})
write('DEDUP_REPAIR_QUEUE.json',{'distinct_historical_tasks':len(queue),'basic_edit_repair_not_yet_closed':sum(q['needs_basic_edit_repair'] for q in queue),'repaired_identity_or_edit_with_followup_pending':sum(not q['needs_basic_edit_repair'] for q in queue),'meaning':'14 not-yet-closed historical task/action failures include action-only and scene-only problems; they are not 14 identity failures. R98 has repaired identity/scene but retains motion differences.','tasks':queue})
write('AUDIT_MANIFEST.json',{'inventory_snapshots':[rec(ROOT/'snapshots'/f'{n}.json') for n in invs],'historical_rows':22,'unique_tasks':18,'ive_unique_tasks':8,'flex_unique_tasks':10,'successor_checks_passed':all(x['prompt_in_actual_graph_exact'] and all(i['matches_contract'] for i in x['inputs']) for s in successors for x in s['checks']),'scope':'Read-only current inventory, actual gates/reviews/media, small registered contracts, and 3 successor input files. No PT/model load, GPU, service change, producer/inventory mutation.','not_claimed':'No new visual validation or new scientific result; six-frame previous reviews retain their limited coverage.'})
print(json.dumps({'historical_rows':len(rows),'unique_tasks':len(queue),'still_open':sum(q['needs_basic_edit_repair'] for q in queue),'input_cases_checked':sum(len(s['checks']) for s in successors)},ensure_ascii=False))
