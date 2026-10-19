from pathlib import Path
import copy, json, hashlib, time, subprocess
R = Path(__file__).resolve().parents[1]
C = R.parent / 'h3-sampler-control-metrics-r106-20261019'
P = R.parent / 'h3-timing-sampler-control-r106-20261019'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
p = R / 'inventory/ivebench.json'
before = sha(p); doc = read(p); old = copy.deepcopy(doc['items'])
ID = 'r106_short_0252_sampler_control'
assert not any(x['id'] == ID for x in old)
parent = next(x for x in old if x['id'] == 'r73_short_0252')
presentation = C / 'showcase/PRESENTATION.json'; pres = read(presentation)
reviewfile = C / 'audit/root_full_frame_review/REVIEW.json'; review = read(reviewfile)
assert sorted(n for page in review['reviewed_pages'] for n in page['frames']) == list(range(98))
gate = C / 'incoming/gate.json'; g = read(gate)
assert g['passed'] and all(g['checks'].values())
for role in ('source', 'euler', 'res_multistep'):
    assert sha(C / f'incoming/{role}.mp4') == pres['input_properties'][role]['sha256']
assert sha(pres['comparison']['file']) == pres['comparison']['sha256']
props = json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames', '-of', 'json', pres['comparison']['file']]))['streams'][0]
assert props['nb_read_frames'] == '98'
summary = '两种采样器均完成年长女人替换并保留机舱、孩子和面罩。98帧逐帧审阅中，Euler与res_multistep的初段抬手、握面罩均比参考约晚15帧（0.625秒），动作时序在当前视觉精度内相近；末端额前姿态均保留。这个同条件对照记录采样器影响，两个结果都采用普通编辑。'
row = {k: copy.deepcopy(parent[k]) for k in ('benchmark', 'source_id', 'task', 'display_task', 'reference_image_used', 'reference_image_path', 'original_task')}
row.update(id=ID, variant='R106 fresh Euler / res_multistep', title='机舱人物替换：两种采样器的动作时序',
    reference_video_path=str(C/'incoming/source.mp4'), ordinary_video_path=str(C/'incoming/euler.mp4'),
    alternative_video_path=str(C/'incoming/res_multistep.mp4'), guided_video_path=None,
    comparison_video_path=pres['comparison']['file'], comparison_properties=props, preview_html=pres['html'],
    preview_html_sha256=sha(pres['html']), column_labels=pres['column_labels'], valid_frames=98, fps=24,
    comparison_kind='sampler_control', method_label='Euler与res_multistep：相同20步sigma序列',
    review_summary=summary, display_summary=summary, review_status='两种采样器均有初段动作延后',
    review_status_code='sampler_control_similar_delay', guidance_activation='not_applicable', actual_routed_blocks=0,
    prompt_version='P1', independent_sample=False, parent_inventory_id='r73_short_0252',
    count_as_basic_edit_success=True, count_as_complete_task_success=True, supports_guidance_benefit=False,
    task_acceptance='PASS_both_solvers', event_review={'file':str(reviewfile),'sha256':sha(reviewfile),'events':review['events']},
    efficiency={role:{'job_wall_seconds':g['runs'][role]['job_wall_seconds'],'capture_seconds':g['runs'][role]['capture_seconds'],'NFE':g['runs'][role]['NFE']} for role in ('euler','res_multistep')})
row['quantitative_metrics'] = {
    'motion_fidelity': {'euler':None,'res_multistep':None,'delta':None,'higher_is_better':True,'status':'pending',
        'protocol':parent['quantitative_metrics']['motion_fidelity']['protocol'],'source_files':[],'source_sha256':{},
        'valid_frames':98,'scope':'两个新鲜普通编辑结果的官方MF待评分；采样器对照。'},
    'event_timing': {'measurement':'98帧逐帧视觉审阅','fps':24,'events':review['events'],
        'source_file':str(reviewfile),'source_sha256':sha(reviewfile),'scope':review['annotation_policy']}}
evidence = [P/'configs/scientific_contract.json', gate, C/'incoming/COLLECTION.json', C/'incoming/COMPLETE.json',
    C/'incoming/ROOT_EXIT_RECEIPT.json', presentation, reviewfile, C/'audit/root_full_frame_review/HTML_UPDATE.json', C/'audit/PRE_OUTPUT_EVENT_PLAN.json']
row['evidence_paths'] = [str(x) for x in evidence]
row['evidence_sha256'] = {str(x):sha(x) for x in evidence}
row['media_sha256'] = {k:sha(row[k]) for k in ('reference_video_path','ordinary_video_path','alternative_video_path','comparison_video_path')}
doc['items'].append(row); assert doc['items'][:-1] == old
items = doc['items']
doc['counts'] = {'items':len(items),'unique_sources':len({x['source_id'] for x in items}),
    'guided_pairs':sum(x['comparison_kind']=='guided_pair' for x in items),
    'activated_fixed_pairs':sum(x['comparison_kind']=='guided_pair' and x.get('guidance_activation')=='active' for x in items),
    'zero_intervention_pairs':sum(x.get('guidance_activation')=='zero' for x in items),
    'prompt_controls':sum(x['comparison_kind']=='prompt_control' for x in items),
    'sampler_controls':sum(x['comparison_kind']=='sampler_control' for x in items),
    'native_only':sum(x['comparison_kind']=='native_only' for x in items),
    'native_only_skipped_after_review':sum(x['comparison_kind']=='native_only' and x.get('screening_decision')=='skip' for x in items)}
doc['previous_inventory_sha256'] = before; doc['updated_unix'] = time.time(); assert sha(p) == before
a = R / 'audit/r106_sampler_20261019'; a.mkdir(exist_ok=False)
(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes())
p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
receipt = {'before_sha256':before,'after_sha256':sha(p),'added':ID,'other_rows_unchanged':True,'counts':doc['counts']}
(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps(receipt))
