from pathlib import Path
import copy,json,hashlib,time
R=Path(__file__).resolve().parents[1];D=R.parent
C=D/'h3-ive-task-repair-metrics-r102-20261019';P=D/'h3-timing-ive-task-repair-r102-20261019'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
path=R/'inventory/ivebench.json';previous=sha(path);doc=read(path);old=copy.deepcopy(doc['items']);assert not any(x['id']=='r102_short_0263' for x in old)
a=R/'audit/r102_0263_native_20261019';a.mkdir(exist_ok=True);(a/'PREVIOUS_INVENTORY.json').write_bytes(path.read_bytes())
presentation_file=C/'showcase/short_0263/PRESENTATION.json';p=read(presentation_file)
gate_file=C/'incoming/short_0263/NATIVE_RUNTIME_GATE.json';g=read(gate_file)
review_file=C/'audit/root_native_review/short_0263/REVIEW.json';review=read(review_file)
assert g['passed'] and all(g['checks'].values()) and review['task_acceptance']=='pass' and review['reviewed_all_valid_frames']
for entry in p['inputs']:assert sha(entry['file'])==entry['sha256']
video=C/'showcase/short_0263'/p['videos'][0]['file'];assert sha(video)==p['videos'][0]['sha256']
assert p['timeline']['valid_frames']==74 and p['timeline']['total_frames']==90
evidence=[P/'configs/scientific_contract.json',P/'configs/graphs/r102_short_0263_seed2026101701_native.json',C/'inputs/short_0263_provenance.json',gate_file,C/'incoming/short_0263/COLLECTION.json',presentation_file,review_file,review_file.with_name('FRAME_LEDGER.json')]
item={'id':'r102_short_0263','benchmark':'IVEBench','source_id':'short_0263','variant':'R102 / P1-local-v1 / ordinary preview / .9','title':'躺椅读书：女人替换为小女孩（修复后的普通编辑）','task':p['original_task']['edit_prompt'],'display_task':'将蓝色躺椅上读书的女人替换为小女孩，保留书、椅子、植物与翻页动作。','reference_image_used':False,'reference_image_path':None,'reference_video_path':p['inputs'][0]['file'],'ordinary_video_path':p['inputs'][1]['file'],'guided_video_path':None,'comparison_video_path':None,'alternative_video_path':None,'native_comparison_video_path':str(video),'review_summary':'全74有效帧审阅：小女孩替换成功，蓝色躺椅、书本、植物、花朵及镜头构图保留。第38–54帧翻页阶段已大致对齐；末段抬头与视线幅度可能有差别，时间错位尚不能确定。匹配时序引导正在生成。','review_status':'基础任务完成；匹配引导待成片','review_status_code':'native_only_pending_guidance','evidence_paths':[str(x) for x in evidence],'evidence_sha256':{str(x):sha(x) for x in evidence},'valid_frames':74,'generated_frames':90,'fps':24,'method_label':'普通编辑；匹配时序引导正在生成','comparison_kind':'native_only','column_labels':['1.参考视频','2.普通编辑'],'original_task':p['original_task'],'prompt_version':p['prompt_version'],'actual_routed_blocks':0,'guidance_activation':'pending','screening_decision':'guide','independent_sample':False,'parent_inventory_id':'r64_short_0263','count_as_complete_task_success':True,'support_for_clear_whole_event_repair':False,'native_comparison_properties':p['videos'][0]['properties'],'preview_html':'/Users/researcher/Downloads/H3_R102_short_0263_普通编辑预览_20261019.html','event_review':{'file':str(review_file),'sha256':sha(review_file),'events':review['motion_findings'],'scope':'root逐帧审阅；后段head/gaze的时差UNKNOWN'},'quantitative_metrics':{'motion_fidelity':{'native':None,'guided':None,'delta':None,'higher_is_better':True,'status':'pending','source_files':[],'source_sha256':{},'valid_frames':74,'scope':'实际普通编辑已经完成，匹配引导及官方MF待完成。','protocol':'IVEBench official MF; commit 2dcf8900ee65197f43854c76f61c66a32bb8dbfc; CoTracker3 offline, grid10, window60'}}}
item['parent_inventory_id']='r69_short_0263'
assert any(x['id']==item['parent_inventory_id'] for x in old)
item['media_sha256']={k:sha(item[k]) for k in ['reference_video_path','ordinary_video_path','native_comparison_video_path']}
assert Path(item['preview_html']).is_file();doc['items'].append(item)
assert doc['items'][:-1]==old
items=doc['items'];doc['counts']={'items':len(items),'unique_sources':len({x['source_id'] for x in items}),'guided_pairs':sum(x['comparison_kind']=='guided_pair' for x in items),'activated_fixed_pairs':sum(x['comparison_kind']=='guided_pair' and x.get('guidance_activation')=='active' for x in items),'zero_intervention_pairs':sum(x.get('guidance_activation')=='zero' for x in items),'prompt_controls':sum(x['comparison_kind']=='prompt_control' for x in items),'native_only':sum(x['comparison_kind']=='native_only' for x in items),'native_only_skipped_after_review':sum(x['comparison_kind']=='native_only' and x.get('screening_decision')=='skip' for x in items)}
doc['previous_inventory_sha256']=previous;doc['updated_unix']=time.time();assert sha(path)==previous
path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
receipt={'before_sha256':previous,'after_sha256':sha(path),'added':'r102_short_0263','other_rows_unchanged':True,'counts':doc['counts']};(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
