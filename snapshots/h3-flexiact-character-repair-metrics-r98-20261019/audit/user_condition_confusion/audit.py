from pathlib import Path
import json,hashlib,difflib,re,datetime
P=Path('/Users/researcher/DevProjects/h3-timing-flexiact-character-repair-r98-20261019');C=Path('/Users/researcher/DevProjects/h3-flexiact-character-repair-metrics-r98-20261019');A=C/'audit/user_condition_confusion';OLD=P/'design/R66_ACTUAL'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):return {'file':str(p),'sha256':sha(p)}
def write(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
oldg=read(OLD/'native_graph.json');newg=read(C/'incoming/graph.json');oldgate=read(OLD/'PAIR_RUNTIME_GATE.json');newgate=read(C/'incoming/NATIVE_RUNTIME_GATE.json');pres=read(C/'showcase/PRESENTATION.json');oldrouter_path=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-evaluation-r66-20261018/incoming/human2animal_1__game_man_4/native_router.json');oldrouter=read(oldrouter_path);newrouter=read(A/'new_router.json')
assert sha(oldrouter_path)==oldgate['runs']['native']['router_file_sha256']
oldc=read(OLD/'r66_human2animal_1__game_man_4_seed2026101701_native_conditioning.json');newc=read(A/'new_conditioning.json');diff=[]
def compare(a,b,p=''):
 if isinstance(a,dict) and isinstance(b,dict):
  for k in sorted(set(a)|set(b)):
   if k not in a or k not in b:diff.append({'path':p+'/'+k,'old':a.get(k),'new':b.get(k)})
   else:compare(a[k],b[k],p+'/'+k)
 elif a!=b:diff.append({'path':p,'old':a,'new':b})
compare(oldg,newg)
admin={'audit_dir','run_id','pair_id','source_run_id','source_audit_dir','output_dir','filename_prefix'}
for x in diff:x['classification']='prompt_scientific_change' if x['path']=='/5/inputs/prompt' else 'administrative' if x['path'].split('/')[-1] in admin else 'UNEXPECTED'
assert sum(x['classification']=='prompt_scientific_change' for x in diff)==1
assert all(x['classification']!='UNEXPECTED' for x in diff)
write(A/'GRAPH_DIFF.json',{'old_graph':bind(OLD/'native_graph.json'),'new_actual_graph':bind(C/'incoming/graph.json'),'differences':diff})
(A/'old_prompt.txt').write_text(oldg['5']['inputs']['prompt']+'\n');(A/'new_prompt.txt').write_text(newg['5']['inputs']['prompt']+'\n')
(A/'PROMPT_DIFF.txt').write_text(''.join(difflib.unified_diff(oldg['5']['inputs']['prompt'].splitlines(True),newg['5']['inputs']['prompt'].splitlines(True),fromfile='R66 old Native',tofile='R98 new Native')))
for r in [oldrouter,newrouter]:
 assert r['mode']=='native' and r['routed_calls']==0 and r['routed_by_forward']==[0]*20 and r['native_override_calls']==1000
assert oldgate['runs']['native']['routed_blocks']==newgate['routed_blocks']==0
assert oldgate['runs']['forced']['video']['sha256']!=pres['inputs'][1]['sha256']
assert pres['inputs'][1]['sha256']==oldgate['runs']['native']['video']['sha256']
assert pres['inputs'][2]['sha256']==newgate['video']['sha256']
assert oldc['qwen_presentation'][1]['sampling']==newc['qwen_presentation'][1]['sampling']
assert oldc['qwen_presentation'][0]==newc['qwen_presentation'][0]
rows=[]
def sig(x):return {k:x[k] for k in ['shape','dtype','sha256']}
def add(n,o,nw):rows.append({'name':n,'old':o,'new':nw,'equal':o==nw})
add('decoded_input_video',sig(oldc['input_video']),sig(newc['input_video']))
for i,label in enumerate(['reference_image','reference_video']):
 for field in ['prepared_frames','latent']:add(label+'_'+field,sig(oldc['native_vae_calls'][i][field]),sig(newc['native_vae_calls'][i][field]))
add('Qwen_sampling_indices_and_physical_times',oldc['qwen_presentation'][1]['sampling'],newc['qwen_presentation'][1]['sampling'])
add('Qwen_sampled_video_RGB',sig(oldc['qwen_presentation'][1]['actual_sampled_frames']),sig(newc['qwen_presentation'][1]['actual_sampled_frames']))
for field in ['conditioning_embedding','token_tags']:add(field,sig(oldc[field]),sig(newc[field]))
add('target_latent_shapes',oldc['target_latent_shapes'],newc['target_latent_shapes'])
add('packed_position_ids',sig(oldc['packed_layout']['position_ids']),sig(newc['packed_layout']['position_ids']))
write(A/'CONDITION_COMPARISON.json',{'rows':rows,'raw_initial_AV_noise_equal':newgate['checks']['raw_initial_AV_noise_matches_R66'],'evidence':[bind(OLD/'r66_human2animal_1__game_man_4_seed2026101701_native_conditioning.json'),bind(A/'new_conditioning.json'),bind(A/'new_noise.json')],'interpretation':'Source media bytes are fixed, while decoded video and VAE results differ across hosts; Qwen receives identical image RGB and identical sampling times, but its sampled video RGB and joint output embeddings differ. Prompt and runtime confounds are explicit.'})
inherit=read(P/'configs/runtime_kernel_hashes.json')
for path,v in inherit.items():assert v['byte_equal'] and sha(P/path)==v['current_sha256']==v['parent_sha256']
htmlpath=Path('/Users/researcher/Downloads/H3_R98_俯卧支撑角色替换修复_20261019.html');html=htmlpath.read_text();visible=re.sub(r'data:[^;\"]+;base64,[A-Za-z0-9+/=]+','[embedded asset]',html)
assert '三栏：参考动作 / 旧普通编辑 / 新版普通编辑' in visible and '时序引导次数为0' in visible
assert pres['columns']==['参考动作','旧普通编辑','新版普通编辑'] and pres['guidance_routed_calls']==[0,0]
caption={'actual_presentation':bind(C/'showcase/PRESENTATION.json'),'published_html':bind(htmlpath),'actual_poster':bind(C/'showcase/poster.jpg'),'columns':pres['columns'],'visual_caption_check':'Viewed actual poster: 1.参考动作 / 2.旧普通编辑 / 3.新版普通编辑; source/old/new mapping matches SHA-bound inputs.','html_zero_guidance_text_present':True,'stale_review_note':'Published HTML still says pending full review; full147 review now exists independently. Root owns any publication update.','mislabelled_as_guided':False}
write(A/'CAPTION_CHECK.json',caption)
unchanged={k:{'class_type':newg[k]['class_type'],'inputs':newg[k]['inputs']} for k in ['1','2','3','4','41','7','8','9','21','22','23']};assert all(oldg[k]==newg[k] for k in unchanged)
result={'schema':'r98-user-condition-confusion-audit-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'conclusion':'R98第三列为0次时序引导的新版普通编辑；旧普通编辑也为0次。未发现实际图/路由日志/成片SHA映射将持续引导放入第三列的证据。',
'actual_execution':{'old_native':{'NFE':20,'Euler_updates':20,'mode':oldrouter['mode'],'routed_calls':oldrouter['routed_calls'],'routed_by_forward':oldrouter['routed_by_forward']},'new_native':{'NFE':20,'Euler_updates':20,'mode':newrouter['mode'],'routed_calls':newrouter['routed_calls'],'routed_by_forward':newrouter['routed_by_forward']}},
'native_mode_explanation':{'source_file':str(P/'extensions/H3TemporalRouter/core.py'),'lines':[222,223,224,413,417,418,419],'meaning':'mode=native在完整attention计算后直接返回；step范围0..20和alpha1只保存节点配置，未进入mass_preserve/hard_route分支。1000 native_override_calls=20步×50层的完整attention调用，不是1000次时序修正。'},
'graph_diff_counts':dict(__import__('collections').Counter(x['classification'] for x in diff)),'unchanged_model_sampler_and_input_nodes':unchanged,
'unchanged_other_axes':{'seed':2026101701,'geometry':[1152,768,158],'fps':24,'valid_frames':147,'image_then_video_reference':True,'Qwen_semantic_fps':2,'Qwen_phase_frames':0,'reference_image_size':'match','turbo_lora_nodes':0,'online_observer':False,'raw_initial_AV_noise_equal':True,'numeric_source_modules_byte_equal':len(inherit)},
'changed_variables':['prompt由原3句泛化指令改为官方六段格式，明确短黑发动漫男性、白背景、动作来源与段落','host .41 GPU2→.9 GPU3；Torch2.11/PyAV16.1→Torch2.5.1/PyAV16.0','same source bytes decoded RGB及clean VAE参考latent跨host哈希变化，幅值未读大tensor，不能声称差异为零或很小','joint Qwen条件embedding长度6736→7537，token tags和packed位置随提示上下文变化','run/cache/audit/output路径迁移；新文本条件独立生成'],
'causal_limit':'当前修复前后比较包含提示与运行环境变化，只能确认新版基础编辑成功和0引导事实。不能把外观改善或动作偏差全部归因于提示词，更不能作为时序方法效果。',
'condition_mapping':'同一目标图与视频文件进入原H3EventAuditReference→官方MiniMaxH3ReferenceToVideo；图像ref0和视频ref0分别编码，图像先于视频。输入时基、样本索引、VAE latent形状保留；实际张量差异单列。',
'evidence':[bind(OLD/'PAIR_RUNTIME_GATE.json'),bind(C/'incoming/NATIVE_RUNTIME_GATE.json'),bind(oldrouter_path),bind(A/'new_router.json'),bind(A/'GRAPH_DIFF.json'),bind(A/'CONDITION_COMPARISON.json'),bind(A/'CAPTION_CHECK.json'),bind(P/'configs/runtime_kernel_hashes.json'),bind(P/'extensions/H3TemporalRouter/core.py'),bind(P/'extensions/H3EventAudit/__init__.py')]}
write(A/'REPORT.json',result)
(A/'REPORT.txt').write_text('R98第三列已核：新版普通编辑，20步、0次时序引导；第二列是R66旧Native，也为20步、0次引导。R66另一个450次路由的旧forced视频没有混入本页。\n\n实际graph共14处差异：1处prompt科学字段、13处run/cache/audit/output行政字段。模型、seed、158帧、24fps、BasicGuider、Euler20、video12/audio3 sigma、参考图视频连线及native router参数均相同。图中0..20只是native节点范围；full attention直接返回，路由日志每步均0。\n\n提示改为六段格式明确动漫男性身份、纯白背景和视频动作。主机与软件从.41 Torch2.11/PyAV16.1换至.9 Torch2.5.1/PyAV16.0；源文件字节相同，但视频RGB及VAE参考latent实际哈希不同。目标图准备RGB相同，图像VAE latent不同。Qwen采样物理时刻相同、视频RGB不同，联合embedding长度6736→7537。原始AV噪声复用并实际验证相等。此轮不能单独归因提示词。\n\n实际视频底caption为“参考动作 / 旧普通编辑 / 新版普通编辑”，HTML写明0次引导；未见第三列误放持续引导输出的证据。页面尚有“待完整审阅”旧文本，新的147帧验收已另存，发布更新由root处理。\n')
print(json.dumps({'report':bind(A/'REPORT.json'),'graph_diffs':len(diff),'routing':[oldrouter['routed_calls'],newrouter['routed_calls']],'same_modules':len(inherit)},ensure_ascii=False))
