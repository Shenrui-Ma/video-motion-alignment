from pathlib import Path
import copy,json,hashlib,time
R=Path(__file__).resolve().parents[1];D=R.parent;C=D/'h3-ive-task-repair-metrics-r102-20261019';P=D/'h3-timing-ive-task-repair-r102-20261019'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
path=R/'inventory/ivebench.json';previous=sha(path);doc=read(path);old=copy.deepcopy(doc['items']);id='r102_short_0092';assert not any(x['id']==id for x in old)
presentation=C/'showcase/short_0092/PRESENTATION.json';p=read(presentation);assert sha(presentation)=='0704b6b8fec5138237595b041ed33bd1ffcbfa5b409db7c5467238285db80ec5'
gate=C/'incoming/short_0092/NATIVE_RUNTIME_GATE.json';g=read(gate);review_file=C/'audit/root_native_review/short_0092/REVIEW.json';review=read(review_file)
assert g['passed'] and all(g['checks'].values()) and review['task_acceptance']=='partial' and review['reviewed_all_valid_frames'] and review['decision']=='skip'
collection=C/'incoming/short_0092/COLLECTION.json';assert sha(collection)=='59772f8257871c4ef46e2de12fc8ecb31be35010df75b4bf8b834a74aee0b65d'
for e in p['inputs']:assert sha(e['file'])==e['sha256']
video=C/'showcase/short_0092'/p['videos'][0]['file'];assert sha(video)==p['videos'][0]['sha256'];assert p['timeline']['valid_frames']==58 and p['timeline']['total_frames']==73
evidence=[P/'configs/scientific_contract.json',P/'configs/graphs/r102_short_0092_seed2026101701_native.json',C/'inputs/short_0092_provenance.json',gate,collection,presentation,review_file,review_file.with_name('FRAME_LEDGER.json')]
row={
 'id':id,'benchmark':'IVEBench','source_id':'short_0092','variant':'R102 / P1-local-v1 / ordinary / .9','title':'室内录影：移除植物（仍有小盆栽残留）',
 'task':p['original_task']['edit_prompt'],'display_task':'移除房间内植物，保留女子、家具、摄像机和原动作。','reference_image_used':False,'reference_image_path':None,
 'reference_video_path':p['inputs'][0]['file'],'ordinary_video_path':p['inputs'][1]['file'],'guided_video_path':None,'comparison_video_path':None,'alternative_video_path':None,'native_comparison_video_path':str(video),
 'review_summary':'root全58有效帧审阅：背景大株植物已移除，桌面小盆栽及架子上的叶片、花朵仍保留，移除任务完成不全。挥手和手向胸口移动的可见阶段已较同步，后段前景摄像机遮挡使时刻无法判断。按审阅记录跳过引导，保留普通编辑失败记录。',
 'review_status':'植物移除不完整；跳过引导','review_status_code':'native_only_task_partial_skipped','display_summary':'大株植物移除，小盆栽与架子花叶仍在；可见手势已较同步。该条保留为任务不完整的普通编辑。',
 'evidence_paths':[str(x) for x in evidence],'evidence_sha256':{str(x):sha(x) for x in evidence},'valid_frames':58,'generated_frames':73,'fps':24,
 'method_label':'普通编辑；基础任务不完整，已跳过引导','comparison_kind':'native_only','column_labels':['1.参考视频','2.普通编辑'],'original_task':p['original_task'],'prompt_version':p['prompt_version'],
 'actual_routed_blocks':0,'guidance_activation':'not_applicable','screening_decision':'skip','independent_sample':False,'parent_inventory_id':'r64_short_0092',
 'count_as_complete_task_success':False,'support_for_clear_whole_event_repair':False,'native_comparison_properties':p['videos'][0]['properties'],
 'preview_html':'/Users/researcher/Downloads/H3_R102_short_0092_普通编辑预览_20261019.html',
 'event_review':{'file':str(review_file),'sha256':sha(review_file),'events':review['motion_findings'],'scope':'root全部58有效帧审阅；后段手被前景摄像机遮挡，时差UNKNOWN'},
 'quantitative_metrics':{'motion_fidelity':{'native':None,'guided':None,'delta':None,'higher_is_better':True,'status':'pending','source_files':[],'source_sha256':{},'valid_frames':58,'scope':'普通编辑单版官方MF待测；引导已按任务不完整跳过。','protocol':'IVEBench official MF; commit 2dcf8900ee65197f43854c76f61c66a32bb8dbfc; CoTracker3 offline, grid10, window60'}},
 'sampling_seconds_rounded_from_log':review['sampling_seconds_rounded_from_log']
}
assert any(x['id']==row['parent_inventory_id'] for x in old)
row['media_sha256']={k:sha(row[k]) for k in ['reference_video_path','ordinary_video_path','native_comparison_video_path']};assert Path(row['preview_html']).is_file()
doc['items'].append(row);assert doc['items'][:-1]==old
items=doc['items'];doc['counts']={'items':len(items),'unique_sources':len({x['source_id'] for x in items}),'guided_pairs':sum(x['comparison_kind']=='guided_pair' for x in items),'activated_fixed_pairs':sum(x['comparison_kind']=='guided_pair' and x.get('guidance_activation')=='active' for x in items),'zero_intervention_pairs':sum(x.get('guidance_activation')=='zero' for x in items),'prompt_controls':sum(x['comparison_kind']=='prompt_control' for x in items),'native_only':sum(x['comparison_kind']=='native_only' for x in items),'native_only_skipped_after_review':sum(x['comparison_kind']=='native_only' and x.get('screening_decision')=='skip' for x in items)}
doc['previous_inventory_sha256']=previous;doc['updated_unix']=time.time();assert sha(path)==previous
a=R/'audit/r102_0092_native_20261019';a.mkdir(exist_ok=True);assert not (a/'PREVIOUS_INVENTORY.json').exists();(a/'PREVIOUS_INVENTORY.json').write_bytes(path.read_bytes())
path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n');receipt={'before_sha256':previous,'after_sha256':sha(path),'added':id,'other_rows_unchanged':True,'counts':doc['counts']};(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
