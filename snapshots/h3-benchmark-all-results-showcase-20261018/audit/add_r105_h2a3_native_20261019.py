from pathlib import Path
import json, hashlib, time, copy, re, collections

R = Path(__file__).resolve().parents[1]
C = R.parent / 'h3-flexiact-remaining-repair-metrics-r105-20261019'
source = 'human2animal_3__game_man_4'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
p = R / 'inventory/flexiact.json'
before = sha(p)
assert before == '4b0ac00786a3a5986533bed06b09417fa3c18d7a67e0c125e63c361f54176f95'
d = read(p)
old = copy.deepcopy(d['items'])
row = copy.deepcopy(next(x for x in old if x['id'] == 'flex_r105_crouch__movie_man_4_native'))
c = next(x for x in read(C / 'configs/contract.json')['sources'] if x['source_id'] == source)
a, s = C / 'incoming' / source, C / 'showcase' / source
g, pr = read(a / 'NATIVE_RUNTIME_GATE.json'), read(s / 'PRESENTATION.json')
review = C / 'audit/ROOT_NATIVE_REVIEW_human2animal_3__game_man_4.json'
v = read(review)
assert sha(review) == 'd4f76355b2a4b898950f5c36bede8c345e8a5d7caab77332fcf0ab832921d5ef'
assert g['passed'] and all(g['checks'].values()) and g['runs']['native']['routed_blocks'] == 0
assert v['coverage']['all_frames_visually_viewed'] and v['coverage']['count'] == 147 and v['decision'] == 'skip'
media = {'reference_image_path': str(C / c['portrait']['file']), 'reference_video_path': str(C / c['source']['file']), 'ordinary_video_path': str(a / 'native.mp4'), 'native_comparison_video_path': str(s / 'source_native_full_valid.mp4')}
assert sha(media['ordinary_video_path']) == g['runs']['native']['video']['sha256']
assert sha(media['native_comparison_video_path']) == pr['videos'][0]['sha256']
evidence = [C / 'configs/contract.json', a / 'NATIVE_RUNTIME_GATE.json', a / 'COLLECTION.json', s / 'PRESENTATION.json', review, C / 'audit/full_frame_review' / source / 'native/MEDIA_BINDINGS.json', Path(v['source_event_plan']['file']), C / 'prepared' / source / 'native/MF_INPUTS.json']
summary = '完整147有效帧由两位审阅者核对：目标绿披肩动漫男子替换成功，低位支撑、屈腿抬升、上举倒立和末端伸腿顺序保留。人物放大使头、手及后段双脚被裁出，披肩遮挡髋背，精确接触与跨髋时刻无法可靠测量。可见抬腿和伸腿阶段与参考重叠，本轮保留普通编辑并跳过引导。'
html = Path('/Users/researcher/Downloads') / f'H3_R105_{source}_普通编辑预览_20261019.html'
row.update(id='flex_r105_human2animal_3__game_man_4_native', source_id='human2animal_3', reference_image_id='game_man_4', title='屈腿抬升与倒立伸腿 · game_man_4', task=c['display_task'], display_task=c['display_task'], **media, preview_html=str(html), review_status='目标人物与动作顺序保留，裁切和披肩遮挡影响测时；普通编辑', review_summary=summary, display_summary=summary, identity_success={'native': True, 'guided': None}, motion_transfer='ordered_low_support_tuck_inversion_extension_partial_framing', pair_group='官方素材交叉配对', prompt=c['prompt'], prompt_version=c['prompt_version'], input_reference_image_sha256=c['portrait']['sha256'], input_reference_video_sha256=c['source']['sha256'], scene_requirement='目标图白背景', judgment_source='root及continue_r111_r103均完整审阅147有效帧与目标图，身份、粗动作顺序及遮挡裁切分别验收。', event_review={'file': str(review), 'sha256': sha(review)}, parent_inventory_id='flex_r66_human2animal_3__game_man_4', runtime={'native_job_wall_seconds': g['runs']['native']['job_wall_seconds']}, evidence_paths=[str(x) for x in evidence], evidence_sha256={str(x): sha(x) for x in evidence}, media_sha256={k: sha(x) for k, x in media.items()})
row['quantitative_metrics']['motion_fidelity']['source_files'] = [str(C / 'prepared' / source / 'native/MF_INPUTS.json')]
assert 'crouch__movie_man_4' not in json.dumps(row, ensure_ascii=False)
assert not any(x['id'] == row['id'] for x in old)
corrections = []
for x in d['items']:
    if x['id'] in ('flex_r104_human2animal_1__movie_man_11_fixed', 'flex_r105_human2animal_2__movie_man_11_fixed'):
        corrections.append({'id': x['id'], 'previous_pair_group': x['pair_group'], 'new_pair_group': '官方素材交叉配对'})
        x['pair_group'] = '官方素材交叉配对'
d['items'].append(row)
assert all({k: v for k, v in x.items() if k != 'pair_group'} == {k: v for k, v in y.items() if k != 'pair_group'} for x, y in zip(d['items'][:-1], old))
d['previous_inventory_sha256'], d['updated_unix'] = before, time.time()
d['counts'] = dict(collections.Counter(x['comparison_kind'] for x in d['items']))
d['distinct_motion_sources'] = len({x['source_id'] for x in d['items']})
audit = R / 'audit/r105_h2a3_native_20261019'
audit.mkdir(exist_ok=False)
(audit / 'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes())
assert sha(p) == before
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
s0 = html.read_text()
assets = re.findall(r'data:[^"\s>]+', s0)
assert 'id="native-review"' not in s0
s1 = s0.replace('<figure>', '<section id="native-review"><h2>全片检查结果</h2><p>' + summary + '</p><p>本例使用官方视频与官方角色图的交叉配对。官方 Motion Fidelity 等待评分。</p></section><figure>', 1)
assert re.findall(r'data:[^"\s>]+', s1) == assets
html.write_text(s1)
receipt = {'before_sha256': before, 'after_sha256': sha(p), 'rows': len(d['items']), 'id': row['id'], 'review_sha256': sha(review), 'pair_group_corrections': corrections, 'html': str(html), 'html_sha256': sha(html), 'embedded_assets_unchanged': True}
(audit / 'RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
(C / 'audit/h2a3_native_HTML_UPDATE.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt, ensure_ascii=False))
