"""Read historical evidence; write only this extension's candidate inventory."""
import json, hashlib, datetime
from pathlib import Path
B=Path('/Users/researcher/DevProjects'); OUT=Path(__file__).parent

def read(p): return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def ref(p,expected=None):
 p=Path(p);r={'file':str(p),'exists_local':p.is_file()}
 if p.is_file():
  r.update(sha256=sha(p),bytes=p.stat().st_size)
  if expected:r['matches_recorded_sha256']=r['sha256']==expected;assert r['matches_recorded_sha256'],str(p)
 return r

def graph_info(p):
 g=read(p);n=g.get('6',{}).get('inputs',{});a=g.get('5',{}).get('inputs',{})
 return {'graph':ref(p),'prompt':a.get('prompt'),'prompt_sha256':hashlib.sha256(a.get('prompt','').encode()).hexdigest(),
  'seed':n.get('noise_seed'), 'noise_registration':n,'condition_registration':{k:v for k,v in a.items() if k!='prompt'},
  'recipe_nodes':{k:v for k,v in g.items() if v.get('class_type') in ['UNETLoader','CLIPLoader','VAELoader','MiniMaxH3SigmaShift','KSamplerSelect','ManualSigmas','H3TemporalRouter','H3EventEmphasis','H3PairConditionSnapshot']},
  'input_nodes':{k:v for k,v in g.items() if v.get('class_type') in ['LoadVideo','LoadImage']}}

def picture(root,sid=None):
 root=Path(root)
 for sub in ['showcase_pairs','showcase','audit/full_frame_review','review/compact','review','analysis']:
  p=root/sub
  if sid and (p/sid).is_dir():p=p/sid
  if p.exists():
   fs=sorted(x for x in p.rglob('*') if x.suffix.lower() in ['.jpg','.png'] and (sid is None or sid in str(x) or sub.startswith('review')))
   if fs:return ref(fs[len(fs)//2])
 return None

inv={}
for ds in ['ivebench','flexiact']:
 p=B/'h3-benchmark-all-results-showcase-20261018/inventory'/f'{ds}.json'
 for row in read(p)['items']:inv[row['id']]=(row,p)
rows=[]
r148=B/'h3-timing-phase-combined-eval-r148-20261020/EVALUATION_MANIFEST.json'
for sid in ['long_0039','long_0059']:
 c=next(x for x in read(r148)['cases'] if x['source_id']==sid)
 media={k:ref(v['file'],v['sha256']) for k,v in c['media'].items() if k in ['source','native','fixed']}
 rows.append({'candidate_id':sid,'source_id':sid,'source_group':sid,'task':c['title'],'basic_edit_status':'PASS_CORE_EDIT','selection_status':'ready_samebin_history',
 'edit_evidence':c['historical_review'],'historical_manifest':ref(r148),'media':media,'valid_frames':c['geometry']['valid_frames'],'geometry':c['geometry'],
 'seed':c['seed'],'prompt':c['prompt'],'prompt_sha256':c['prompt_sha256'],'graphs':{k:graph_info(v['graph']['file']) for k,v in c['historical_runs'].items()},
 'noise':c['historical_initial_noise'],'cache_binding':c['historical_input_binding'],'remote_media':c['remote41_media_cache_pointers'],
 'historical_fixed_method':'mass_preserve same-bin alpha1, steps zero-based6..14, 50blocks, exact window in graph',
 'official_MF':{k:v for k,v in c['official_MF'].items() if k in ['native','fixed']},'events':c['events'],
 'review_frame':picture(B/'h3-timing-phase-combined-eval-r148-20261020',sid),
 'qualification':'蓝书任务成立，五动作存在且普通版延后；旧fixed局部提前但伸手阶段拉长。' if sid=='long_0039' else '白手帕编辑与场景成立，抬手/触眼近同步，撤手两版均晚约16帧。'})

spec=[
 ('r89_short_0085','h3-timing-ive-subject-capacity-r89-20261018'),
 ('r89_short_0274','h3-timing-ive-subject-capacity-r89-20261018'),
 ('r99_short_0210','h3-timing-ive-p1-guidance-r99-20261019'),
 ('r99_short_0230','h3-timing-ive-p1-guidance-r99-20261019'),
 ('flex_r104_fitness__game_man_4_fixed','h3-timing-flexiact-remaining-repair-r104-20261019'),
 ('r89_short_0268','h3-timing-ive-subject-capacity-r89-20261018'),
]
for iid,pkg in spec:
 x,ip=inv[iid];sid=x['source_id'];prod=B/pkg;cp=prod/'configs/scientific_contract.json';contract=read(cp)
 cases=[c for c in contract['cases'] if c.get('source_id')==sid or c.get('pair_key')==sid or (c.get('motion_source_id')==sid and c.get('pair_key','') in iid)]
 gates=[Path(v) for v in x['evidence_paths'] if 'PAIR_RUNTIME_GATE.json' in v];gate=read(gates[0]);assert gate['passed']
 consumer=Path(x['ordinary_video_path']).parents[2]
 graphs={}
 for role,run in gate['runs'].items():
  gp=prod/'configs/graphs'/f"{run['run_id']}.json"
  if gp.exists():graphs[role]=graph_info(gp)
  else:
   found=list((consumer/'configs').rglob(f"{run['run_id']}.json")) if (consumer/'configs').exists() else []
   if found:graphs[role]=graph_info(found[0])
 bindings={}
 for role,run in gate['runs'].items():
  remote=run['video']['file'].split('/output/')[0]
  bindings[role]={'run_id':run['run_id'],'remote_video':run['video'],'cache_and_noise_artifacts':{remote+'/'+k:v for k,v in run.get('binding_artifacts',{}).items() if 'condition' in k or 'noise' in k},'NFE':run.get('NFE'),'routed_blocks':run.get('routed_blocks')}
 metric=x.get('quantitative_metrics',{}).get('motion_fidelity',{})
 rows.append({'candidate_id':iid,'source_id':sid,'source_group':sid.split('__')[0],'task':x['task'],'title':x['title'],'basic_edit_status':'PASS_CORE_EDIT','selection_status':'ready_samebin_history',
  'inventory_record':{'file':str(ip),'sha256':sha(ip),'item_id':iid},'producer':str(prod),'contract':ref(cp),'pair_gate':ref(gates[0]),
  'media':{r:ref(x[k]) for r,k in [('source','reference_video_path'),('native','ordinary_video_path'),('fixed','guided_video_path')]},
  'valid_frames':x['valid_frames'],'fps':x['fps'],'seed':cases[0]['seed'],'prompt':cases[0].get('prompt'),'graphs':graphs,
  'actual_runs':bindings,'cached_condition_tensors':gate.get('condition_tensor_files'), 'runtime_profile':gate.get('runtime_profile'),
  'historical_fixed_method':'mass_preserve same-bin alpha1, steps zero-based6..14; graph records physical window and exact recipe',
  'edit_evidence':[ref(v) for v in x['evidence_paths'] if 'REVIEW.json' in v], 'qualification':x['review_summary'],
  'official_MF':metric,'review_frame':picture(consumer,sid), 'scientific_contract_case':cases})

legacy=[
 ('musk05','05_real_megumi_v','h3-musk-real-dance-pair-20261014','05_musk_s1_baseline','h3-musk-real-dance-pair-20261014','05_musk_s1_weight3','角色替换—Musk复现书记舞','PASS_RECOGNIZABLE_IDENTITY_WITH_ARTIFACTS','完整既有审阅确认Musk替换与舞蹈；普通开头0–1帧额外掌状残影，精细手形限制保留。'),
 ('firefly06','06_anime_eye_insert','h3-short-event-switching-20261013','06_anime_eye_insert_a_s2','h3-event-emphasis-factor3-20261014','06_seed2_emphasis3','角色替换—流萤复现动画书记舞','PASS_IDENTITY_ACTION_MICROEVENT_MISSING','seed1312可辨流萤，黑边保留；39–44早期手眼插入被低位手势代替，原三倍未恢复。'),
 ('silverwolf06','06_anime_eye_insert','h3-silverwolf-baseline-20261014','06_silverwolf_seed2_baseline','h3-event-emphasis-silverwolf-20261014','06_silverwolf_seed2_emphasis3','角色替换—银狼复现动画书记舞','PASS_RECOGNIZABLE_IDENTITY_CROSS_HOST','银狼外观与大动作成立；未加权/三倍跨主机编码不同，细手势关系不完全匹配。'),
 ('sam07','07_real_ary_v','h3-sam-real-dance-batch-20261015','07_sam_s1_baseline','h3-sam-real-dance-batch-20261015','07_sam_s1_weight3','角色替换—Sam Altman复现床边书记舞','NEEDS_ROOT_IDENTITY_SCENE_SPOT','旧报告仅全片间隔+关键窗审阅，局部延后改善；未完成全面身份/场景质量评估，待root看片决定。'),
]
for cid,sid,np,nrun,wp,wrun,title,status,note in legacy:
 nr,wr=B/np,B/wp
 ng=nr/'configs'/f'{nrun}.json';wg=wr/'configs'/f'{wrun}.json'
 if not ng.exists():
  found=list((nr/'configs').rglob(f'{nrun}.json'));assert found,(cid,'nativegraph');ng=found[0]
 info=graph_info(ng);gi=read(ng);inp=gi['22']['inputs'];source=nr/'inputs'/inp.get('file',inp.get('video',''))
 if not source.is_file():source=wr/'inputs'/f'{sid}.mp4'
 noise=nr/'audit'/f'{nrun}_noise.json'
 rows.append({'candidate_id':cid,'source_id':sid,'source_group':sid,'task':title,'basic_edit_status':status,
  'selection_status':'root_review_needed' if cid=='sam07' else 'legacy_baseline_reusable_new_samebin_required',
  'media':{'source':ref(source),'native':ref(nr/'outputs'/f'{nrun}_00001_.mp4'),'legacy_weight3':ref(wr/'outputs'/f'{wrun}_00001_.mp4'),'fixed':None},
  'valid_frames':141,'fps':24,'geometry':{'width':1312,'height':736,'sampled_frames':141,'crop_xywh':[0,0,1312,736]},
  'seed':info['seed'],'prompt':info['prompt'],'prompt_sha256':info['prompt_sha256'],'graphs':{'native':info,'legacy_weight3':graph_info(wg)},
  'noise_metadata':ref(noise),'noise_record':read(noise) if noise.exists() else None,
  'condition_metadata':[ref(p) for p in (nr/'audit').glob('*conditioning.json') if nrun in p.name or 'shared' in p.name],
  'historical_fixed_method':None,'legacy_method':'selected reference K/V duplicated twice (logits+ln3), all20steps/all50blocks; not same-bin7–15',
  'new_requirement':'Root-approved same-bin7–15 reference required before schedule comparison; never relabel weight3 as fixed.',
  'edit_evidence':[ref(nr/'REPORT.txt'),ref(wr/'REPORT.txt')], 'qualification':note,
  'official_MF':{'status':'not_located_in_completed_official_MF_records','native':None,'fixed':None},
  'review_frame':ref(B/'h3-event-emphasis-factor3-20261014/review/compact/compact_frames_041-043.png') if cid=='firefly06' else picture(nr), 'same_source_as_current_Sam':sid=='05_real_megumi_v'})

for i,x in enumerate(rows,1):x['rank_by_existing_edit_evidence']=i
excluded=[{'candidate_id':'flex_r116_human2animal_1__game_man_4_fixed','reason':'用户明确质疑普通版身份/场景；现有审阅同时记视角/幅度偏差。按最新要求不入12候选，不以旧PASS文本覆盖用户判断。'},
 {'candidate_id':'flex_r85_rotate__game_girl_1_fixed','reason':'背景仅部分符合目标图深青背景，严格任务优先下不选。'},
 {'candidate_id':'flex_r66_one_leg__movie_man_11','reason':'局部手脚裁切且完整动作对照有偏差，候选充足时不优先。'}]
existing=['short_0252','05_real_megumi_v','short_0358']
doc={'schema':'r150-candidate-inventory-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'scope':'read-only local completed evidence inventory; no new GPU, no automatic selection or new results',
 'existing_R149':{'tasks':3,'independent_source_ids':existing,'MF_display_records':12,'media_release_audit':ref(OUT.parent/'audit/FINAL_MEDIA_RELEASE_AUDIT.json')},
 'selection_required':7,'candidate_count':len(rows),'ready_samebin_history_count':sum(r['selection_status']=='ready_samebin_history' for r in rows),
 'source_count_rule':'Count unique original source_group, not seed/prompt/identity; Musk05 shares currentSam05; Firefly06/SilverWolf06 share one source.',
 'candidate_independent_source_count':len(set(r['source_group'] for r in rows)),
 'all_candidates_plus_existing_unique_sources':len(set(existing+[r['source_group'] for r in rows])),
 'candidates':rows,'excluded_or_deferred':excluded,'selection_note':'Root selects7 using basic edit completion first. Legacyfour are explicitly not current fixed references; Sam07 needs identity/scene review.'}
(OUT/'candidate_inventory.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
print('candidates',len(rows),'sources',doc['candidate_independent_source_count'],'samebin_ready',doc['ready_samebin_history_count'])
print('missing_media',[(r['candidate_id'],k) for r in rows for k,v in r['media'].items() if v and not v['exists_local']])
print('missing_frame',[r['candidate_id'] for r in rows if not r['review_frame']])
print('sha256',sha(OUT/'candidate_inventory.json'))
