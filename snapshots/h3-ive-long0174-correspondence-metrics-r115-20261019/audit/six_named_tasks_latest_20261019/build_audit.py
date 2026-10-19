from pathlib import Path
import hashlib
import json
import re
import subprocess
import time

ROOT = Path('/Users/researcher/DevProjects')
OUT = Path(__file__).resolve().parent
INV = ROOT / 'h3-benchmark-all-results-showcase-20261018/inventory'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def binding(path):
    p = Path(path)
    return {'file': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size}

items = {}
inventories = []
for name in ('ivebench.json', 'flexiact.json'):
    p = INV / name
    inventories.append(binding(p))
    items.update({x['id']: x for x in json.loads(p.read_text())['items']})

specs = [
    ('俯卧支撑 Game Man 4', 'flex_r101_human2animal_1__game_man_4_fixed',
     ['flex_r66_human2animal_1__game_man_4', 'flex_r98_human2animal_1__game_man_4_task_repair'],
     'PARTIAL', '先修复普通编辑中的侧面构图、末段伸臂拱背及身体完整入画，再对验收通过的普通编辑补匹配引导。R104 fitness 是另一个举臂动作，不能替代本项。'),
    ('舞台女讲者替换为男讲者', 'r99_short_0210', ['r55_short_0210', 'r63_short_0210', 'r71_short_0210'],
     'PASS', '最新完整配对已齐，展示应使用 R71 P1 普通编辑与 R99 引导。普通编辑已近同步；可保留为中性对照，当前没有缺失的引导成片。'),
    ('厨房头巾和围裙改蓝', 'r99_short_0230', ['r55_short_0230', 'r69_short_0230', 'r80_short_0230'],
     'PASS', '最新完整配对已齐，展示应使用 R80 普通编辑与 R99 引导。当前修复已完成，时序收益为中性。'),
    ('坐姿传统男替换为现代着装女', 'r99_short_0352', ['r55_short_0352', 'r69_short_0352', 'r80_short_0352'],
     'PASS', '最新完整配对已齐；展示第66–73帧普通编辑新增手势被抑制，同时保留原抬掌动作。归类为减少额外动作，时差改善另行评价。'),
    ('霓虹篮球', 'r110_short_0114_promptcontrol', ['r64_short_0114', 'r100_short_0114', 'r109_short_0114_promptcontrol'],
     'PARTIAL', '优先修复普通编辑的相机朝向、地面占比和上半身裁切。R110仅普通编辑，R100已有旧完整配对；等构图验收通过，再补同配置引导。'),
    ('移除装饰华丽的壁炉', 'r108_short_0392', ['r64_short_0392'],
     'PASS', '最新完整配对已齐，展示使用 R108 source/native/forced。壁炉移除已完成，普通编辑已近同步，可保留中性对照。'),
]

def read_record(record_id):
    x = items[record_id]
    selected = {k: x.get(k) for k in ('id','benchmark','source_id','title','task','reference_image_used','reference_image_path','reference_video_path','ordinary_video_path','guided_video_path','alternative_video_path','comparison_video_path','preview_html','valid_frames','fps','comparison_kind','review_status','review_summary','quantitative_metrics')}
    media = {}
    for key in ('reference_image_path','reference_video_path','ordinary_video_path','guided_video_path','alternative_video_path','comparison_video_path'):
        path = x.get(key)
        if not path:
            continue
        b = binding(path)
        expected = x.get('media_sha256', {}).get(key)
        b['inventory_expected_sha256'] = expected
        b['inventory_sha_matches'] = expected is None or b['sha256'] == expected
        assert b['inventory_sha_matches'], (record_id, key)
        if path.endswith('.mp4'):
            b['video_properties'] = json.loads(subprocess.check_output([
                '/opt/homebrew/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,avg_frame_rate,nb_frames', '-of', 'json', path
            ], text=True))['streams'][0]
        media[key] = b
    selected['verified_media'] = media
    evidence = []
    gates = []
    reviews = []
    for path in x.get('evidence_paths', []):
        p = Path(path)
        if p.name not in ('PAIR_RUNTIME_GATE.json', 'gate.json', 'REVIEW.json', 'SOURCE_POSE_CLARIFICATION.json', 'COLLECTION.json', 'RESULT_VERIFIED.json'):
            continue
        b = binding(p)
        expected = x.get('evidence_sha256', {}).get(path)
        b['inventory_expected_sha256'] = expected
        b['inventory_sha_matches'] = expected is None or b['sha256'] == expected
        assert b['inventory_sha_matches'], (record_id, path)
        evidence.append(b)
        d = json.loads(p.read_text())
        if p.name in ('PAIR_RUNTIME_GATE.json', 'gate.json'):
            assert d['passed'] is True
            runs = d.get('runs', {'native': d})
            simple = {k: {a: v.get(a) for a in ('run_id','valid_frames','routed_blocks','historical_parent')} for k,v in runs.items()}
            for name, run in runs.items():
                vsha = run.get('video',{}).get('sha256')
                simple[name]['video_sha256'] = vsha
                simple[name]['matching_local_media'] = [k for k,v in media.items() if v['sha256'] == vsha]
                assert simple[name]['matching_local_media'], (record_id,name,'unbound actual video')
            gates.append({'binding': b, 'passed': True, 'schema': d['schema'], 'runs': simple, 'checks': d.get('checks')})
        if p.name in ('REVIEW.json','SOURCE_POSE_CLARIFICATION.json'):
            reviews.append({'binding': b, 'actual_review': d})
    selected['actual_gates'] = gates
    selected['review_evidence'] = reviews
    selected['evidence_bindings'] = evidence
    selected['complete_pair'] = bool(x.get('ordinary_video_path') and x.get('guided_video_path') and gates)
    return selected

records = []
for title, latest_id, older_ids, status, next_step in specs:
    latest = read_record(latest_id)
    history = [{k: items[r].get(k) for k in ('id','variant','comparison_kind','review_status','review_summary')} for r in older_ids]
    row = {'requested_task': title, 'latest_trusted_record': latest,
           'basic_task_acceptance': status, 'previous_results': history,
           'recommended_next_step': next_step,
           'review_source':'existing complete-frame review and actual media/gate bindings read on this audit; this audit adds no new visual outcome judgement'}
    if latest_id == 'r110_short_0114_promptcontrol':
        row['latest_native_video'] = latest['verified_media']['alternative_video_path']
        row['latest_native_run_id'] = 'r110_short_0114_seed2026101701_native'
        row['presentation_alias_note'] = 'R110 incoming/plain.mp4 is actual latest reference-bound Native; incoming/p1.mp4 is historical R109 one-line Native. Both are unguided.'
        row['latest_complete_pair'] = read_record('r100_short_0114')
        row['matching_latest_native_guided_video'] = None
    records.append(row)

contract_scan = []
targets = ['short_0210','short_0230','short_0352','short_0114','short_0392','human2animal_1__game_man_4']
for p in sorted(ROOT.glob('h3-timing-*/configs/scientific_contract.json')):
    match = re.search(r'-r(\d+)-',str(p))
    if not match or int(match.group(1)) < 98:
        continue
    text = p.read_text()
    hit = [target for target in targets if target in text]
    if hit:
        contract_scan.append({**binding(p),'target_ids':hit})

report = {'schema':'six-named-tasks-latest-media-audit-v1','created_unix':time.time(),
          'inventories':inventories,'producer_contract_scan':contract_scan,
          'scope':'Read-only existing six task evidence; no GPU, inference queue, inventory, or sealed producer changes.',
          'findings':records,
          'summary':{'requested_tasks':6,'complete_pair_for_latest_task_configuration':5,
                     'basic_task_pass':4,'basic_task_partial':2,
                     'repair_priority':['俯卧支撑 Game Man 4','霓虹篮球'],
                     'existing_pair_ready_to_show':['舞台女讲者替换为男讲者','厨房头巾和围裙改蓝','坐姿传统男替换为现代着装女','移除装饰华丽的壁炉'],
                     'generation_performed_in_this_audit':False}}
(OUT/'AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines = ['六项任务的最新实际成片审计','',
         '四项的基础编辑已修复且完整对照已归档：舞台、厨房、坐姿人物、壁炉。',
         '俯卧支撑的角色与背景已修复，但末段动作形态仍不正确。篮球的霓虹外观和运球已恢复，构图仍失真。',
         'R104 fitness/Game Man 4 是举臂动作，不计作俯卧支撑任务修复。','']
for row in records:
    latest = row['latest_trusted_record']
    lines += [row['requested_task']+' | '+latest['id']+' | '+row['basic_task_acceptance'],
              latest['review_summary'],row['recommended_next_step'],'']
lines += ['R110文件别名注意：incoming/plain.mp4是新显式参考提示词的普通编辑；incoming/p1.mp4是旧R109一句话普通编辑。R110没有引导版本。',
          '审计逐项重算媒体SHA、读取实际gate、核对既有完整帧审阅；各绝对路径、run ID、参考图与量化分数见AUDIT.json。']
(OUT/'REPORT.txt').write_text('\n'.join(lines)+'\n')
(OUT/'CHECKS.json').write_text(json.dumps({'passed':True,'tasks':6,'media_sha_verified':True,'actual_gate_media_bound':True,'actual_review_references_bound':True,'no_gpu_job':True,'audit_sha256':sha(OUT/'AUDIT.json'),'report_sha256':sha(OUT/'REPORT.txt')},indent=2)+'\n')
print(json.dumps({'audit':str(OUT/'AUDIT.json'),'audit_sha256':sha(OUT/'AUDIT.json'),'summary':report['summary']},ensure_ascii=False,indent=2))
