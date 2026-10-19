from pathlib import Path
import csv, json, hashlib, datetime
from PIL import Image
B=Path('/Users/researcher/DevProjects'); O=Path(__file__).resolve().parent
CACHE=B/'h3-flexiact-expanded-selection-20261018'; R49=B/'h3-timing-flexiact-native-r49-20261017'; REV='69d7747f93e1b913a3dca306bf8e91ee74fea7d4'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def rec(p):p=Path(p);return {'file':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
# Audit all available scientific contracts; exclude both already generated and prepared pairs.
contracts=[]; prior={}
for p in sorted(B.glob('h3-timing-*/configs/scientific_contract.json')):
 try:d=json.loads(p.read_text())
 except (ValueError,OSError):continue
 cases=d.get('cases',[])
 if not isinstance(cases,list):continue
 relevant=[]
 for c in cases:
  if not isinstance(c,dict):continue
  source=c.get('motion_source_id',c.get('source_id','').split('__')[0])
  target=c.get('identity','')
  if source not in ('fitness','one_leg','crouch') or '/human/' not in target:continue
  key=source+'__'+Path(target).stem
  row={'producer':str(p.parent.parent),'run_id':c.get('run_id'),'arm':c.get('arm'),'prompt_version':c.get('prompt_version','R49_original' if 'r49-' in str(p) else None),'target':target,'prompt_file':c.get('prompt_file'),'contract_sha256':sha(p)}
  prior.setdefault(key,[]).append(row);relevant.append(key)
 if relevant:contracts.append({'contract':rec(p),'pairs':sorted(set(relevant))})
visual={
'movie_man_2':{'description':'短发、眼镜、深灰西服及黑衬衫，正面略侧，脸和服装轮廓清楚。','visible':'头、肩、躯干至髋附近；手和下肢在画面外。','risk':'深色服装；全身运动需模型补全，动作观察须以生成结果实际可见部位为准。','priority':'high'},
'movie_man_1':{'description':'深发男子穿有显著胸部标记的蓝红紧身服，正面略侧，身份与衣服易辨。','visible':'头、肩、胸部、部分上臂；前臂、手、腿不在画面内。','risk':'胸像；斗篷可遮挡身体，背景还有虚化人物。','priority':'high'},
'movie_girl_1':{'description':'浅色衬衫、长发、正面笑脸，脸部清楚且背景简单。','visible':'头、肩与上胸；手和腿不在画面内。','risk':'长发遮肩；需补全手臂和下半身。','priority':'medium'},
'movie_man_10':{'description':'短发胡须男子裸上身、深色长裤，身体略侧，双臂和手可辨。','visible':'头、躯干、双臂、双手、上段大腿；膝以下被裁切。','risk':'膝和足部缺参考；室内背景较复杂。','priority':'high'},
'movie_man_7':{'description':'裸上身男子、黑色短裤，朝前站立，双臂下垂，身体轮廓和手清楚。','visible':'头、躯干、双臂、双手、大腿；下腿和脚被裁切。','risk':'下腿无参考，必须在成片检查膝抬起与足部接触；不因参考裁切直接判任务失败。','priority':'high'},
'movie_man_6':{'description':'蓝色西服、浅色衬衫的正面男子，清楚面部与衣服，街道背景。','visible':'头、躯干、上腿；双手插口袋，下腿和脚被裁切。','risk':'手部不可见且起始姿势有口袋先验；需检查蹲起过程中双手能否离开口袋并维持身份。','priority':'medium'},
'movie_man_8':{'description':'深色上衣男子在讲台上，身体接近正面，胸前双手可辨。','visible':'头、躯干、手臂、胸前双手；观众遮挡腰腿，人物占图比例小。','risk':'面部像素较少、多人观众与强前景遮挡，排队最后。','priority':'lower'},
}
selected=[('fitness','movie_man_2'),('one_leg','movie_man_10'),('crouch','movie_man_7'),('fitness','movie_man_1'),('one_leg','movie_man_7'),('fitness','movie_girl_1'),('crouch','movie_man_6'),('crouch','movie_man_8')]
cases=[]; inventories={}
for s in ['fitness','one_leg','crouch']:
 csvp=CACHE/'metadata'/f'flexiact_hf__benchmark__captions__human__{s}__val_image.csv';rows=list(csv.DictReader(csvp.open()))
 inventories[s]={'csv':rec(csvp),'official_row_count':len(rows),'remaining_unprepared_pairs':[s+'__'+Path(r['path']).stem for r in rows if s+'__'+Path(r['path']).stem not in prior],'prior_pairs':{s+'__'+Path(r['path']).stem:prior[s+'__'+Path(r['path']).stem] for r in rows if s+'__'+Path(r['path']).stem in prior}}
for rank,(s,t) in enumerate(selected,1):
 csvp=CACHE/'metadata'/f'flexiact_hf__benchmark__captions__human__{s}__val_image.csv';rows=list(csv.DictReader(csvp.open()));idx=next(i for i,r in enumerate(rows) if Path(r['path']).stem==t);r=rows[idx];key=s+'__'+t
 assert key not in prior,(key,prior[key])
 target=CACHE/'official_assets'/r['path']; im=Image.open(target)
 cropp=CACHE/'metadata'/f'flexiact_hf__benchmark__captions__human__{s}__crop.csv';sourcecaption=list(csv.DictReader(cropp.open()))[0]['caption']
 exactprompts=[]
 for prompt in B.glob('h3-timing-*/configs/prompts/'+key+'.txt'):exactprompts.append(rec(prompt))
 cases.append({'rank':rank,'pair_key':key,'motion_source_id':s,'target_id':t,'pair_kind':'official_CSV_pair','new_independent_motion_source':False,'prior_pair_contract_matches':[],
 'official_row_zero_based':idx,'official_csv_line_one_based':idx+2,'official_target_row':r,'official_csv':rec(csvp),'official_source_motion_caption':sourcecaption,'official_crop_csv':rec(cropp),
 'caption_semantic_review':'官方 val_image caption 写 resistance machine，与 crouch 原片和官方 crop.csv 的 squats 不符。原文保留；沿既有 R74 crouch P1 的 source-video 优先任务适配，需在派生 prompt 记录此矛盾。' if s=='crouch' else '动作语义与官方 source crop.csv 一致。',
 'official_row_url':f'https://huggingface.co/datasets/shiyi0408/FlexiAct/blob/{REV}/benchmark/captions/human/{s}/val_image.csv',
 'original_source':rec(R49/'inputs'/f'source_{s}_original.mp4'),'prepared_source':rec(R49/'inputs'/f'source_{s}_video.mp4'),'source_provenance':rec(R49/'inputs'/f'source_{s}_provenance.json'),
 'official_source_url':f'https://huggingface.co/datasets/shiyi0408/FlexiAct/resolve/{REV}/benchmark/reference_videos/human/{s}.mp4',
 'target':{**rec(target),'width':im.width,'height':im.height,'official_url':f'https://huggingface.co/datasets/shiyi0408/FlexiAct/resolve/{REV}/'+r['path'],'visual_review':visual[t]},
 'pair_specific_P1_exists':bool(exactprompts),'existing_pair_specific_P1_files':exactprompts,'P1_template_reference':str(B/'h3-timing-flexiact-official-six-r74-20261018/design/P1_TEMPLATE.txt'),
 'P1_status':'尚未编写本配对 prompt。模板可复用，Subject 1 外观描述须按目标图填写；本任务只选素材。',
 'evaluation_scope':'身份、服装和源动作顺序先检查；允许目标图场景。手脚离开画面或不可见的时段记录 UNKNOWN；不把截断本身当作时间偏移。',
 'source_timing':{'original_frames':49,'original_fps':8,'prepared_frames':158,'prepared_fps':24,'valid_prefix_frames':147,'tail_padding_frames':11,'original_sample_frame_indices_in_prepared':list(range(0,147,3))}})
assert len(cases)==8 and len({c['pair_key'] for c in cases})==8
sel={'schema':'flexiact-official-identity-expansion-source-target-only-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'dataset_revision':REV,'scope':'8 official identity pairs, 3 reused motion sources, 7 distinct target images; no generation-based selection','counts':{'pairs':8,'motion_sources':3,'new_motion_sources':0,'distinct_target_images':7,'fitness_pairs':3,'one_leg_pairs':2,'crouch_pairs':3},'all_targets_are_photographic_humans':True,'full_body_visibility':'仅为排序因素；半身目标仍允许全身动作迁移，实际任务成功需生成后检查。','status':'ASSET_SELECTION_ONLY_NO_GPU_NO_NEW_PROMPT','cases':cases,'inventory':inventories,'prior_contract_scan':contracts}
dump(O/'CANDIDATES.json',sel)
dump(O/'KNOWN_PAIR_INVENTORY.json',prior)
# Existing one_leg reuse evidence: actual jobs and runtime gates; no PT download/recompute.
def prior_entry(producer,consumer,key,run,host):
 p=B/producer;c=B/consumer if consumer else None
 if consumer:
  inc=c/'incoming'/key;job=inc/'native_job.json';gate=inc/'PAIR_RUNTIME_GATE.json';native=inc/'native.mp4';forced=inc/'forced.mp4';d=json.loads(job.read_text())
 else:
  batch=p/'analysis/postrun/captured/batch';job=batch/'logs'/f'{run}_job.json';d=json.loads(job.read_text());gate=p/'audit/RUNTIME_GATE.json';native=batch/'output'/f'{run}_00001_.mp4';forced=None
 return {'producer':str(p),'actual_host':host,'run_id':run,'actual_job':rec(job),'actual_status':d.get('status'),'service_pid':d['service_pid'],'actual_service_identity':d['service_identity'],'native_video':rec(native),'forced_video':rec(forced) if forced and forced.exists() else None,'paired_gate':rec(gate) if gate.exists() else None,'prompt_version':'R49_original/P0'}
a=prior_entry('h3-timing-flexiact-native-r49-20261017',None,'one_leg','r49_source_one_leg_seed2026101701_native','.9')
a['visual_scope']='已有 root_visual_one_leg 的6帧 (0,24,48,72,108,144) 与原片相同时刻复核；非全片逐帧精确计时。';a['task_quality']='目标眼镜西服男子身份连续可辨，双臂向头顶抬起及抬膝大阶段成立；裁切使脚部不可完整观察。不能由6帧认定精确零延迟。';a['native_reuse']='.9 已有有效 P0 Native；仅在原 P0、输入/权重/软件/seed/初始噪声/直接条件及前6步输出绑定相同的后续 fixed 实验里可以复用。改成 P1 时必须重新建立对应 Native。';a['existing_forced_other_host']='R65 在 .41 已重新运行 Native+forced，不能把 .41 forced 与旧 .9 Native 当同机对照。'
b=prior_entry('h3-timing-flexiact-forced-r65-20261018','h3-flexiact-forced-metrics-r65-20261018','one_leg','r65_one_leg_seed2026101701_native','.41');b['task_quality']='既有成对物理评测和展示已归档；本次未重新做全片人工判定。';b['reuse']='Native和fixed已齐全，直接复用现有 .41 成对结果；若改 P1 则是新提示诊断。'
c=prior_entry('h3-timing-flexiact-expanded-r66-20261018','h3-flexiact-expanded-evaluation-r66-20261018','one_leg__movie_man_11','r66_one_leg__movie_man_11_seed2026101701_native','.41');c['task_quality']='本次0/1/2/3/4/6秒定点复核：目标西服老人外观和场景持续，大阶段抬臂抬膝可辨；6秒时两编辑手臂均比参考更分开，Native与fixed非常接近，未见明确固定引导收益。下肢裁切限制足部判断。';c['review_image']=rec(O/'prior_one_leg_movie11_six.jpg');c['reuse']='Native与fixed已在 .41 成对完成。所核记录没有该配对 .9 Native，不能计划只补 .9 fixed 并把 .41 Native冒充同机对照。'
dump(O/'ONE_LEG_EXISTING_REUSE.json',{'scope':'Bounded local archive lookup; no remote PT reads, no new inference','runs':[a,b,c]})
lines=['FlexiAct 官方新增身份配对：素材清单','', '8 个未在本地已登记 producer 合同中运行或预排的官方配对：fitness 3、one_leg 2、crouch 3。共用 3 条已有动作源、7 张目标图，新增独立动作数为 0。', 'one_leg 官方总共只有 5 个目标；movie2/9/11 已跑，所以只能新增 movie7/10。图像全身与否用于排序；半身参考图仍可测试全身动作迁移。', '', '按脸部清晰、衣服辨识、可见身体与遮挡排序：']
for c in cases:
 v=c['target']['visual_review'];lines.append(f"{c['rank']}. {c['pair_key']}：{v['description']} {v['visible']} {v['risk']} 官方 CSV 数据行 {c['official_row_zero_based']}（从0计）。")
lines += ['', '三条 crouch 候选的官方 target caption 都误写 resistance machine；官方 source crop.csv 写 squats，原片也为蹲起。CANDIDATES.json逐字保存两份官方文本。派生提示应沿已核 crouch P1 的动作来源分工，并显式留存此适配；不能把原 caption 静默改成“官方正确文本”。', '这8对均没有现成的逐配对 P1 文件；现有 R74 模板可复用，但尚未为它们写入 producer 或启动推理。', '', '现成 one_leg 能否省掉 Native：', 'movie_man_2：R49 在 .9 已有有效 P0 Native。原条件、噪声、环境和前6步输出全部核对后，可用于同机 fixed 补跑；改 P1 应另建 Native。R65 已在 .41 完整跑过同目标 Native+fixed，可直接看现成对照。', 'movie_man_11：R66 在 .41 已有完整 Native+fixed；所核记录未见 .9 Native。六个固定时刻看目标外观/场景和抬臂抬膝大阶段成立，末段手臂形状仍有差异，两编辑很接近。', '所有原始视频、目标图、来源 CSV、官方原 caption、先前已用配对、prompt状态及SHA见 CANDIDATES.json；已有 Native 复用证据见 ONE_LEG_EXISTING_REUSE.json。', '', '范围：只查官方素材和现有归档，未新增GPU、未改科学协议、未将8对计为8条独立动作。官方版本：'+REV]
(O/'REPORT.txt').write_text('\n'.join(lines)+'\n')
files=[rec(p) for p in sorted(O.iterdir()) if p.is_file() and p.name!='MANIFEST.json'];dump(O/'MANIFEST.json',{'files':files,'status':'complete','checks':{'unique_pairs':8,'official_row_and_target_sha_bound':True,'no_prior_contract_pair_matches':True,'all_paths_exist':True,'pair_specific_P1_count':sum(c['pair_specific_P1_exists'] for c in cases)}})
print('PASS 8 official pairs / 3 reused motions / 7 targets');print(rec(O/'CANDIDATES.json'));print(rec(O/'REPORT.txt'));print(rec(O/'ONE_LEG_EXISTING_REUSE.json'))
