from pathlib import Path
import json,copy,hashlib,time
R=Path(__file__).resolve().parent;S=R.parents[1];D=S.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def req(x,t):
 if not x:raise ValueError(t)
def bound(p):return {'file':str(p),'sha256':sha(p)}
inventory=read(S/'inventory/ivebench.json');published=read(S/'audit/SHOWCASE_MANIFEST.json');remote=read(R/'REMOTE_PARENT_EVIDENCE.json');stats=read(R/'REMOTE_PARENT_TENSOR_PRESENCE.json')
configs=[('short_0210','r71','p1','h3-timing-ivebench-prompt-pair-r71-20261018','audit/consumer/incoming','PAIR_RUNTIME_GATE.json','p1_logs_history.json','p1_logs_job.json','p1.mp4','p1_audit_conditioning.json','r71_short_0210'),('short_0230','r80','native','h3-timing-local-edit-repair-r80-20261018','audit/input_decode_recovery_v2/incoming/short_0230','NATIVE_RUNTIME_GATE_HOST9_v2.json','history.json','job.json','native.mp4',None,'r80_short_0230'),('short_0352','r80','native','h3-timing-local-edit-repair-r80-20261018','audit/input_decode_recovery_v2/incoming/short_0352','NATIVE_RUNTIME_GATE_HOST9_v2.json','history.json','job.json','native.mp4',None,'r80_short_0352')]
parents=[]
for source,tag,arm,name,inc,gname,hname,jname,vname,cname,iid in configs:
 root=D/name;incoming=root/inc;g=read(incoming/gname);run=g['runs'][arm];rid=run['run_id'];h=read(incoming/hname);j=read(incoming/jname);graph=root/'configs/graphs'/f'{rid}.json';gg=read(graph);contract=read(root/'configs/scientific_contract.json');case=next(x for x in contract['cases'] if x['run_id']==rid);item=next(x for x in inventory['items'] if x['id']==iid)
 req(g['passed'] and all(v is True for v in g['checks'].values()),'gate failed');req(j['status']=='success' and sha(incoming/hname)==run['history_sha256'] and sha(incoming/jname)==run['job_sha256'],'actual job/history mismatch');req(sha(graph)==j['graph_sha256'],'graph changed');req(sha(incoming/vname)==run['video']['sha256'],'output changed')
 # Confirm actual saved history graph and successful execution.
 hh=h if 'status' in h else h[j['prompt_id']];req(hh['status']['completed'] is True and hh['status']['status_str']=='success','history execution incomplete');req(hh['prompt'][2]==gg,'executed graph differs')
 remote_root=g['runtime_profile']['remote_root'];cn=remote_root+'/audit/'+rid+'_conditioning.json';nn=remote_root+'/audit/'+rid+'_noise.json';c=remote['files'][cn]['value'];n=remote['files'][nn]['value'];shared=remote_root+'/audit/'+c['pair_snapshot']['source_manifest'];req(c['pair_snapshot']['verified'] and remote['files'][shared]['sha256']==c['pair_snapshot']['source_manifest_sha256'],'shared condition binding differs');req(c['prompt']==case['prompt']==gg['5']['inputs']['prompt'],'actual prompt differs');req(case['reference_image_count']==0 and case['reference_video_count']==1,'reference modality mismatch');req(run['routed_blocks']==0 and run['NFE']==20 and run['Euler_updates']==20,'not Native20')
 if cname:req(sha(incoming/cname)==remote['files'][cn]['sha256'],'archived conditioning changed')
 refs=[]
 def walk(x):
  if isinstance(x,dict):
   if 'tensor_file' in x:refs.append({'file':remote_root+'/audit/'+x['tensor_file'],'tensor_signature':{k:v for k,v in x.items() if k!='tensor_file'}})
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(c)
 gt={x['file']:x for x in g['condition_tensor_files']}
 for x in refs:
  req(stats['files'][x['file']]['exists'],'missing condition PT');req(x['file'] in gt,'condition not covered by actual gate');x['gate_file_sha256']=gt[x['file']]['sha256'];x['current_stat']=stats['files'][x['file']]
 prefix=run['snapshots'][:6]
 for x in prefix:req(stats['files'][x['file']]['exists'] and stats['files'][x['file']]['bytes']==x['bytes'],'prefix missing')
 req(stats['files'][n['cache_file']]['exists'],'noise missing');noise={**n,'current_file':stats['files'][n['cache_file']]}
 reviews=[Path(p) for p in item['evidence_paths'] if p.endswith('HUMAN_REVIEW.json') or p.endswith('VISUAL_REVIEW.json')]
 parent={'source_id':source,'latest_inventory_id':iid,'producer_local':str(root),'producer_remote':remote_root,'consumer_incoming':str(incoming),'run_id':rid,'graph':bound(graph),'history':bound(incoming/hname),'job':bound(incoming/jname),'gate':bound(incoming/gname),'native_video':bound(incoming/vname),'runtime':g['runtime_profile'],'runtime_profile_sha256':g['runtime_profile_sha256'],'actual_service':{'pid':j['service_pid'],'identity':j['service_identity']},'valid_frames':run['valid_frames'],'full_video_properties':run['video']['properties'],'reference_images':0,'reference_video':{'file':str(root/'inputs'/case['video']),'sha256':case['video_sha256']},'condition_manifest':{'file':cn,'sha256':remote['files'][cn]['sha256']},'shared_manifest':{'file':shared,'sha256':remote['files'][shared]['sha256']},'condition_tensors':refs,'noise':noise,'first_six_predictions':prefix,'core_bindings':bound(root/'configs/parent_core_hashes.json'),'numeric_modules':bound(root/'configs/runtime_kernel_hashes.json'),'checkpoint_bindings':bound(root/'configs/expected_checkpoint_hashes.json'),'task_acceptance':{'status':'task_valid_in_existing_six_time_review','independent_recheck':'本次再次查看保存的六时刻图：主体/目标颜色与原场景、动作阶段保留。尚未新增全逐帧验收。','review_files':[bound(p) for p in reviews]},'matched_guided_exists':False,'matching_guided_recommendation':'可在同一.9 core/数值配置下只新跑匹配引导，复用父条件张量与原AV噪声。实际新门必须逐项验证条件、noise和去噪0–5步AV预测exact；若到.41或数值前缀不等，则另做fresh Native+guided同机对。','no_target_identity_image':'任务仅以Video1+文本替换人物/颜色；没有独立目标人像图。'}
 parents.append(parent)
# Same configured core/numeric/model bindings across the three real parents.
for p in parents[1:]:
 for k in ['core_bindings','numeric_modules','checkpoint_bindings']:req(read(p[k]['file'])==read(parents[0][k]['file']),'parent core/numeric/model differ')
(R/'P1_PARENT_BINDINGS.json').write_text(json.dumps({'created_unix':time.time(),'parents':parents,'remote_evidence':bound(R/'REMOTE_PARENT_EVIDENCE.json'),'tensor_presence':bound(R/'REMOTE_PARENT_TENSOR_PRESENCE.json'),'large_condition_and_prefix_files':'存在性及文件大小此次只读核对；其SHA来自原实际gate，部署/配对时仍须逐项重验。三个9.8MB noise缓存本次重新hash。'},ensure_ascii=False,indent=2)+'\n')
latest={'short_0210':'r71_short_0210','short_0230':'r80_short_0230','short_0352':'r80_short_0352','short_0114':'r64_short_0114','short_0392':'r64_short_0392'}
notes={'short_0210':'最新R71 P1普通编辑保留蓝幕、站姿手势并替换为男人；旧P0三栏仍为任务失败。','short_0230':'最新R80 P1普通编辑头巾和围裙改蓝、原厨房与倒料动作保留；旧P0三栏仍改成勺子/碗近景。','short_0352':'最新R80 P1普通编辑为现代裙装女人，原木屋与抬手回落保留；旧P0三栏仍构图/动作不符。','short_0114':'只有R64 P0已成对；手运球被改成脚边球/持球，用户确认基础任务失败。R91 P1包已准备，但实际远端logs/processes/output均空。','short_0392':'仅R64 P0已成对；装饰壁炉未被清楚移除，用户确认基础任务失败。未找到已完成P1重跑。'}
rows=[]
for source,iid in latest.items():
 own=[i for i in inventory['items'] if i['source_id']==source];cur=[i for i in published['items'] if i['source_id']==source];li=next(i for i in own if i['id']==iid)
 for i in own:
  for f,h in i['media_sha256'].items():req(sha(i[f])==h,'inventory media mismatch')
 rows.append({'source_id':source,'official_task':li['task'],'display_task':li['display_task'],'latest_inventory_id':iid,'latest_task_valid_reviewed':source in [p['source_id'] for p in parents],'matched_guided_for_latest_P1':False,'latest_version_status':'completed_P1_Native_only' if source in [p['source_id'] for p in parents] else 'old_P0_completed_task_failure','finding':notes[source],'versions':[{'inventory_id':i['id'],'variant':i['variant'],'comparison_kind':i['comparison_kind'],'ordinary_video_path':i['ordinary_video_path'],'guided_video_path':i['guided_video_path'],'alternative_video_path':i.get('alternative_video_path'),'comparison_video_path':i.get('comparison_video_path'),'review_status':i['review_status'],'review_summary':i['review_summary'],'evidence_paths':i['evidence_paths'],'media_sha256':i['media_sha256']} for i in own],'currently_published_ids':[i['id'] for i in cur],'recommended_next':'matching P1 guided completion' if source in [p['source_id'] for p in parents] else 'P1 Native task repair then review before matched guidance'})
report={'created_unix':time.time(),'scope':'User identified task failures; five IVEBench tasks audited against completed outputs and actual gates. No inference, watcher, or source edits.','published_manifest':bound(S/'audit/SHOWCASE_MANIFEST.json'),'published_html':published['output'],'published_html_sha256':published['output_sha256'],'inventory_at_review':bound(S/'inventory/ivebench.json'),'rows':rows,'P1_parent_bindings':bound(R/'P1_PARENT_BINDINGS.json'),'search_scope':'Local h3 package scientific_contract files R56 onward; actual completion gates/history/media on mapped parents; remote R91 output/log/process directory check. Prepared metadata alone is not counted as completion.'}
(R/'REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(R/'REPORT.txt').write_text('\n'.join([source+': '+notes[source] for source in latest])+"\n\n0210/0230/0352 都在 .9 实际完成，无目标参考图，可优先复用父条件与AV噪声补匹配引导，最终以真实条件/前6步精确门验收。当前网页同时有旧失败P0和P1普通编辑/提示词对照，需最新版本索引。0114/0392优先基础编辑修复。\n")
print('PARENTS',sha(R/'P1_PARENT_BINDINGS.json'),'REVIEW',sha(R/'REVIEW.json'));print([(x['source_id'],x['run_id'],x['actual_service']['pid'],len(x['condition_tensors'])) for x in parents])
