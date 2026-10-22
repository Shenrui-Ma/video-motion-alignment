from pathlib import Path
import copy,json,hashlib,os,time,collections
B=Path('/Users/researcher/DevProjects');R=B/'h3-benchmark-all-results-showcase-20261018';A=Path(__file__).parent
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic(p,x):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
def verify_tree(x):
 if isinstance(x,dict):
  if 'file' in x and 'sha256' in x and Path(x['file']).is_file():assert H(x['file'])==x['sha256'],x['file']
  for v in x.values():verify_tree(v)
 elif isinstance(x,list):
  for v in x:verify_tree(v)
p=R/'inventory/ivebench.json';before=H(p);x=json.loads(p.read_text());rows=x['items'];existing={r['id'] for r in rows}
assert 'r138_short_0252_seed2026101703_visible_only' not in existing and 'r140_short_0163_generic_retention' not in existing
(A/'ivebench_before.json').write_bytes(p.read_bytes())
prepared=json.loads((A/'PREPARED_ROWS.json').read_text());assert prepared['inventory_sha256']==before
n=prepared['rows'][0]
for f,s in n['evidence_sha256'].items():assert H(f)==s,f
n['task_fulfillment']={'native':'FAIL_POSITION_EDIT','guided':None};n['guidance_decision']='skip';n['guidance_effect']='NOT_RUN';n['release_status']='exact_released'
rows.append(n)
hp=B/'h3-oxygen-online-recovery-metrics-r138-20261020/audit/REPORT_HANDOFF.json';assert H(hp)=='7520fb7bd7f2193fa9a0bbce8fd77db83ab0ffc60f3302ad5f582e914bd30432';h=json.loads(hp.read_text());verify_tree(h)
r=copy.deepcopy(next(r for r in rows if r['id']=='r113_short_0252_seed2026101703_fixed'))
r.update(id=h['inventory_id'],variant='R138 · seed2026101703 · 在线自动引导（恢复执行）',comparison_kind=h['comparison_kind'],method_label='自动时序引导（可见部位观察器）',actual_role='visible_only',display_role_map={'guided':'visible_only'},column_labels=['1.参考视频','2.普通编辑','3.自动时序引导'],review_summary=h['summary'],review_status=h['summary'],display_summary=h['summary'],review_status_code='event_timing_benefit',actual_routed_blocks=350,guidance_activation='online_active',action_alignment_bool={'native':False,'guided':True},action_alignment_by_method=h['alignment'],key_same_frame_indices=[50,72],task_fulfillment={'native':'PASS_CORE_EDIT','guided':'PASS_CORE_EDIT'},guidance_effect='EVENT_TIMING_BENEFIT',supports_timing_improvement=True,whole_sequence_alignment_established=True,full_frame_review_path=h['full_frame_review']['file'],review_attribution='continue_metrics 完整98帧审阅；历史普通/固定成片精确复用。',events=h['events'],phase_durations=h['phase_durations'],release_status='exact_released',formal_batch_gate_pending=False,count_as_complete_task_success=True,main_fixed_same_bin_pair=False,independent_source_increment=0,manual_source_roi_retained=True,limitations=h['limits'],recovery_execution=h['cost'],execution_seconds=h['recorded_timings_seconds'])
for field,role in [('reference_video_path','source'),('ordinary_video_path','native'),('guided_video_path','visible_only')]:r[field]=h['video_roles'][role]['file']
r['comparison_video_path']=h['comparison_media']['source_native_visible_only']['videos'][0]['file'];r['alternative_video_path']=None;r['native_comparison_video_path']=None
r['historical_fixed_comparison']=h['comparison_media']['source_fixed_visible_only'];r['historical_reuse']={'native':'r113_short_0252_seed2026101703_fixed','fixed':'r113_short_0252_seed2026101703_fixed','roles':{k:h['video_roles'][k] for k in ['native','fixed']}}
r['prompt']=h['actual_prompt']['text'];r['prompt_protocol']['actual_prompt']=r['prompt'];r['prompt_protocol']['same_prompt_native_guided']=True
r['actual_prompt_by_column']={'ordinary':copy.deepcopy(r.get('actual_prompt_by_column',{}).get('ordinary',{})),'guided':{'text':r['prompt'],'prompt_sha256':h['actual_prompt']['sha256'],'protocol':h['actual_prompt']['prompt_family'],'actual_role':'visible_only','graph_binding':h['actual_prompt']['graph']}}
r['media_sha256']={k:H(r[k]) for k in ['reference_video_path','ordinary_video_path','guided_video_path','comparison_video_path']}
r['quantitative_metrics']={'motion_fidelity':{'native':h['official_MF']['native']['value'],'fixed':h['official_MF']['fixed']['value'],'visible_only':h['official_MF']['visible_only']['value'],'guided':None,'delta':h['official_MF']['visible_only']['value']-h['official_MF']['native']['value'],'status':'complete','higher_is_better':True,'protocol':h['official_MF']['protocol'],'valid_frames':98,'evidence':h['official_MF'],'display_roles':['native','visible_only']},'event_timing':h['descriptive_timing']}
r['control']=h['control'];r['event_semantics']=h['event_semantics'];r['alignment_scope']=h['alignment']['rule'];r['whole_sequence_alignment_scope']='三项预登记可见事件与两段持续时间；98有效帧。';r['terminal_pose']='举带至上胸/脸侧；未把它记作完成佩戴面罩。'
evidence={str(hp):H(hp)}
def collect(z):
 if isinstance(z,dict):
  if 'file' in z and 'sha256' in z and Path(z['file']).is_file():evidence[z['file']]=z['sha256']
  for v in z.values():collect(v)
 elif isinstance(z,list):
  for v in z:collect(v)
collect(h);r['evidence_paths']=list(evidence);r['evidence_sha256']=evidence;rows.append(r)
proof=B/'h3-ive-position-edit-mf-host9-r137-20261020/audit/RESULTS_VERIFIED.json';assert H(proof)=='7f3fd1cc7a045521d6f0c974a7ba7ea01d61063816a82f5326df68fa16a76fe0'
target=next(v for v in rows if v['id']=='r137_long_0116_generic_retention');scores=json.loads(proof.read_text())['results'];s=next(z for z in scores if {'id':target['id'],'field':'native'} in z['inventory_bindings'])
assert s['actual_generated_video_sha256']==target['media_sha256']['ordinary_video_path'];assert s['valid_frames']==144
for fk,hk in [('result_file','result_sha256'),('release_file','release_sha256')]:assert H(s[fk])==s[hk]
files=[proof,proof.parent/'FINAL_RELEASE_VERIFIED.json',Path(s['result_file']),Path(s['release_file'])];target['quantitative_metrics']['motion_fidelity'].update(native=s['score'],status='complete',source_files=[str(f) for f in files],source_sha256={str(f):H(f) for f in files});target['evidence_paths'] += [str(f) for f in files];target['evidence_sha256'].update({str(f):H(f) for f in files})
x['updated_unix']=time.time();x['previous_inventory_sha256']=before;x['counts'].update(items=len(rows),unique_sources=len({r['source_id'] for r in rows}),native_only=sum(r.get('comparison_kind')=='native_only' for r in rows),native_only_skipped_after_review=sum(r.get('comparison_kind')=='native_only' and r.get('guidance_decision')=='skip' for r in rows),resumed_online_guidance=1)
assert H(p)==before;atomic(p,x)
overlay=R/'task_view_20261019/display_evidence.json';d=json.loads(overlay.read_text());(A/'display_evidence_before.json').write_bytes(overlay.read_bytes())
for z in [r,n]:d['versions'][z['id']]={'alignment_native':z['action_alignment_by_method']['native'],'alignment_guided':True if z is r else None,'summary':z['display_summary'],'still_frame':z['key_same_frame_indices'][0],'still_reason':'同帧动作与编辑目标核对','review_file':z['full_frame_review_path'],'review_sha256':H(z['full_frame_review_path']),'guided_presence':bool(z.get('guided_video_path')),'mode':z['comparison_kind']}
atomic(overlay,d)
flex=json.loads((R/'inventory/flexiact.json').read_text())['items'];allrows=flex+rows
snapshot={'schema':'small-progress-protocol-snapshot-v14','created_unix':time.time(),'inventory_bindings':{b:{'path':str(R/'inventory'/f'{b}.json'),'sha256':H(R/'inventory'/f'{b}.json')} for b in ['ivebench','flexiact']},'previous_snapshot':{'path':str(R/'audit/progress_protocol_snapshot_20261020_v13.json'),'sha256':H(R/'audit/progress_protocol_snapshot_20261020_v13.json')},'counts':{},'totals':{'result_versions':len(allrows),'independent_source_videos':len({(z['benchmark'],z['source_id']) for z in allrows}),'unique_task_combinations':len({(z['benchmark'],z['source_id'],z.get('reference_image_id') or '') for z in allrows})},'same_bin_fixed_pair_scope':'Main pair counts use comparison_kind=guided_pair; reference_origin_control, positional_control and resumed_online_guidance are separate.','independent_sources_with_local_timing_improvement':['short_0252','short_0358','long_0039'],'new_records':[{'id':z['id'],'comparison_kind':z['comparison_kind'],'source_id':z['source_id'],'summary':z['display_summary'],'motion_fidelity':z['quantitative_metrics']['motion_fidelity']} for z in [r,n]],'R137_MF':s['score'],'large_html_rebuilt':False,'active_owned_gpu_tasks':[],'next':'Parent schedules next experiments; R140 official MF pending.'}
for name,group in [('IVEBench',rows),('FlexiAct',flex)]:
 pair=[z for z in group if z.get('comparison_kind')=='guided_pair'];active=[z for z in pair if z.get('guidance_activation') in ('active','positive','fixed_active') or (z.get('actual_routed_blocks') or z.get('routed_block_calls') or 0)>0]
 snapshot['counts'][name]={'result_versions':len(group),'independent_source_videos':len({z['source_id'] for z in group}),'unique_task_combinations':len({(z['source_id'],z.get('reference_image_id') or '') for z in group}),'comparison_kinds':dict(collections.Counter(z.get('comparison_kind','guided_pair') for z in group)),'paired_versions':len(pair),'actual_guidance_versions':len(active)}
assert snapshot['totals']=={'result_versions':112,'independent_source_videos':50,'unique_task_combinations':59},snapshot['totals']
out=R/'audit/progress_protocol_snapshot_20261020_v14.json';assert not out.exists();atomic(out,snapshot)
receipt={'inventory_sha256':H(p),'snapshot':str(out),'snapshot_sha256':H(out),'totals':snapshot['totals'],'added':[r['id'],n['id']],'updated':['r137_long_0116_generic_retention'],'large_html_rebuilt':False};atomic(A/'RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False))
