"""Validate one new six-arm cohort; stage R150 and a local V1.1 append only.

Default operation never writes the published reports. --publish copies fully
validated staging files and preserves pre-publication report bytes in backups.
"""
import argparse
import base64
import copy
import hashlib
import html
import importlib.util
import json
import math
import re
import shutil
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[3]
EVAL = PROJECT.parent / 'h3-guidance-schedule-eval-r150-20261021'
REFRESH = EVAL / 'main10_refresh_20261022'
R150 = PROJECT / 'reports/R150_十组引导区间对照_单文件.html'
V11 = PROJECT / 'reports/视频编辑中动作时间对齐-研究进展V1.1.html'
ROLES = ['source', 'native', 'early', 'fixed', 'late', 'split', 'global_weak']
METHODS = ROLES[1:]
NUMERIC = ['subject_consistency', 'background_consistency', 'temporal_flickering',
           'motion_smoothness', 'vtss', 'overall_semantic_consistency',
           'phrase_semantic_consistency', 'semantic_fidelity', 'motion_fidelity']
METRICS = NUMERIC + ['instruction_satisfaction', 'quantity_accuracy', 'content_fidelity']
STEPS = {'native': [], 'early': list(range(9)), 'fixed': list(range(6, 15)),
         'late': list(range(11, 20)), 'split': [*range(4), *range(15, 20)],
         'global_weak': list(range(20))}
LABELS = dict(zip(ROLES, ['参考视频', '普通编辑', '1–9步强引导', '7–15步强引导',
                         '12–20步强引导', '1–4＋16–20步强引导', '全程弱引导 α=0.25']))
MAIN9 = ['short_0252', 'short_0358', 'long_0039', 'long_0059', 'short_0343',
         'short_0114', 'long_0167', 'short_0085', 'short_0274']
HISTORICAL = ['05_real_megumi_v', 'musk05', 'firefly06', 'sam07']
FLEX = 'crouch__movie_man_4'
NEW = 'short_0177'


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def resolve(root, value):
    p = Path(value)
    return p if p.is_absolute() else root / p


def data_url(path, mime):
    return 'data:' + mime + ';base64,' + base64.b64encode(Path(path).read_bytes()).decode()


def require(value, message):
    if not value:
        raise ValueError(message)


def validate(config_path):
    c = load(config_path)
    base = Path(config_path).resolve().parent
    require(c['schema'] == 'ive-six-setting-report-v1' and c['case_id'] == NEW, 'Wrong report contract')
    require(c['cohort'] == 'interval_short0177_20261024', 'Use the new independent six-arm cohort')
    require(set(c['job_ids']) == set(ROLES) and len(set(c['job_ids'].values())) == 7, 'Seven unique job IDs required')
    require(set(c['video_sha256']) == set(ROLES), 'Seven source/video SHA values required')
    require(all(re.fullmatch('[0-9a-f]{64}', v) for v in c['video_sha256'].values()), 'Malformed video SHA')
    geometry = c['geometry']
    require(geometry['fps'] == 24 and geometry['valid_frames'] > 0, 'Frame domain mismatch')
    records = {}
    for role in METHODS:
        result = load(resolve(base, c['result_files'][role]))
        audit = load(resolve(base, c['router_files'][role]))
        m = result['metadata']
        require(result['job_id'] == c['inference_job_ids'][role], role + ': result job mismatch')
        require(m['task_id'] == NEW and m['method'] == role and m['cohort'] == c['cohort'], role + ': result cohort mismatch')
        require(m['seed'] == c['seed'] and m.get('prompt', m.get('recommended_prompt')) == c['prompt'], role + ': seed/prompt mismatch')
        require(m['valid_frames'] == geometry['valid_frames'] and m['fps'] == geometry['fps'], role + ': result frames mismatch')
        videos = [f for f in result['files'] if f['path'].endswith('.mp4')]
        require(len(videos) == 1 and videos[0]['sha256'] == c['video_sha256'][role], role + ': video SHA mismatch')
        require(audit['run_id'] == result['attempt_id'], role + ': audit attempt mismatch')
        require(audit['completed_forward_calls'] == 20 and audit['completed_calls'] == 1000, role + ': incomplete 20×50 execution')
        require(audit['calls_by_forward'] == [50] * 20, role + ': incomplete forward blocks')
        require(audit['schedule'] == role and audit['step_set_zero_based'] == STEPS[role], role + ': wrong schedule')
        require(audit['routed_calls'] == len(STEPS[role]) * 50, role + ': routing count mismatch')
        require(audit['routed_by_forward'] == [50 if i in STEPS[role] else 0 for i in range(20)], role + ': actual routing mismatch')
        require(audit['mode'] == ('native' if role == 'native' else 'mass_preserve'), role + ': mode mismatch')
        require(audit['alpha'] == (.25 if role == 'global_weak' else 1), role + ': alpha mismatch')
        require(audit['pixel_interval_inclusive'] == [0, geometry['valid_frames'] - 1] and audit['block_interval_half_open'] == [0, 50], role + ': frame/block range mismatch')
        records[role] = {'result': result, 'audit': audit}
    manifest = load(resolve(base, c['metrics_manifest']))
    jobs = {j['id']: j for j in manifest['jobs']}
    rows = load(resolve(base, c['metrics_rows']))
    rows = rows['rows'] if isinstance(rows, dict) else rows
    scores = {}
    for role in ROLES:
        job = jobs[c['job_ids'][role]]
        require(job['task_id'] == NEW and job['method'] == role and job['cohort'] == c['cohort'], role + ': metric job mismatch')
        require(job['sha256'] == c['video_sha256'][role], role + ': scored video mismatch')
        require(job['valid_frames'] == geometry['valid_frames'] and job['fps'] == geometry['fps'], role + ': metric frames mismatch')
        require(job['crop_xywh'] == geometry['crop_xywh'], role + ': metric crop mismatch')
        scores[role] = {}
        for key in METRICS:
            found = [r for r in rows if r['job_id'] == job['id'] and r['metric'] == key]
            require(len(found) <= 1, role + ': duplicate metric ' + key)
            r = found[0] if found else {'status': 'pending', 'score': None}
            if found:
                require(r['cohort'] == c['cohort'] and r['task_id'] == NEW and r['method'] == role, role + ': metric row cohort mismatch')
            if key in NUMERIC:
                require(r['status'] == 'done' and isinstance(r['score'], (int, float)) and math.isfinite(r['score']), role + ': missing numeric metric ' + key)
            scores[role][key] = {k: r[k] for k in ['status', 'score']}
    annotation = load(resolve(base, c['annotation']))
    require(annotation['case_id'] == NEW and annotation['fps'] == 24 and annotation['valid_frames'] == geometry['valid_frames'], 'Annotation frame mismatch')
    require(annotation['video_sha256'] == c['video_sha256'], 'Annotation source/video SHA mismatch')
    require(annotation.get('review_completed') is True and annotation['events'], 'Completed visual annotation required')
    measure = module('existing_action_offsets', REFRESH / 'action_offsets.py').measure
    measurement = measure(annotation)
    pp = resolve(base, c['presentation'])
    presentation = load(pp)
    require(presentation['task_id'] == NEW and presentation['roles'] == ROLES, 'Presentation order mismatch')
    require(presentation['valid_frames'] == geometry['valid_frames'] == presentation['full_decode_frames'] and presentation['fps'] == 24, 'Presentation frame mismatch')
    require(presentation['width'] == 1920 and presentation['height'] == 1232, 'Expected existing three-row comparison layout')
    require(0 <= presentation['screenshot_frame'] < geometry['valid_frames'], 'Screenshot outside valid frames')
    for role in ROLES:
        require(presentation['inputs'][role] == {'job': c['job_ids'][role], 'sha256': c['video_sha256'][role]}, role + ': presentation provenance mismatch')
    for name in ['comparison.mp4', 'same_frame.jpg']:
        require(sha(pp.parent / name) == presentation['files'][name], 'Presentation file SHA mismatch: ' + name)
    return c, records, scores, annotation, measurement, presentation, pp


def aggregate(cases):
    result = {}
    for role in ROLES:
        result[role] = {}
        for key in METRICS:
            rr = [c['official_metrics'][role].get(key, {'status': 'pending', 'score': None}) for c in cases]
            values = [r['score'] for r in rr if r.get('status') == 'done' and isinstance(r.get('score'), (int, float))]
            result[role][key] = dict(mean=statistics.mean(values) if values else None,
                n_expected=len(cases), n_done=len(values),
                n_not_applicable=sum(r['status'] == 'not_applicable' for r in rr),
                n_failed=sum(r['status'] == 'failed' for r in rr), n_pending=sum(r['status'] not in ['done', 'not_applicable', 'failed'] for r in rr))
        deltas = [c['official_metrics'][role]['motion_fidelity']['score'] - c['official_metrics']['source']['motion_fidelity']['score'] for c in cases]
        result[role]['motion_fidelity_delta_from_reference'] = dict(mean=statistics.mean(deltas), n_paired=len(deltas))
    return result


def augment(original, validated):
    c, records, scores, annotation, measurement, presentation, pp = validated
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', original, re.S).group(1))
    old = {x['source_id']: x for x in data['cases']}
    require(set(old) in [set(MAIN9 + [FLEX] + HISTORICAL), set(MAIN9 + [FLEX, NEW] + HISTORICAL)], 'Unexpected existing sample set')
    new = dict(id=NEW, source_id=NEW, title=c['title'], dataset='IVEBench', geometry=c['geometry'], seed=c['seed'], prompt=c['prompt'],
        prompt_source_label='本轮原始编辑提示词', reference_image=False, events=annotation['events'], old_MF={r: scores[r]['motion_fidelity']['score'] for r in ['native', 'fixed']},
        control_verdicts={}, control_reviews={}, arms={}, overview=dict(video=data_url(pp.parent / 'comparison.mp4', 'video/mp4'), default_frame=presentation['screenshot_frame'],
        frames=[dict(frame=presentation['screenshot_frame'], url=data_url(pp.parent / 'same_frame.jpg', 'image/jpeg'))]), pending=False, preservation=False,
        source_MF=scores['source']['motion_fidelity']['score'], arm_offsets={r: None for r in ROLES}, new_batch=True,
        display_summary=c['display_summary'], official_metrics=scores, event_offsets=measurement['event_offsets'], mean_absolute_offset=measurement['mean_absolute_offset'],
        timing_measurement=dict(measurement, annotation_source=annotation['annotation_source'], notes=annotation.get('notes', [])), cohort=c['cohort'],
        execution_evidence={r: {'job_id': records[r]['result']['job_id'], 'attempt_id': records[r]['result']['attempt_id'], 'video_sha256': c['video_sha256'][r]} for r in METHODS})
    for role in ['early', 'late', 'split', 'global_weak']:
        a = records[role]['audit']
        new['arms'][role] = dict(score=scores[role]['motion_fidelity']['score'], schedule_parameters=dict(alpha=a['alpha'], physical_query_window=a['pixel_interval_inclusive'], actual_routed_steps_zero_based=STEPS[role]), sampling_seconds=records[role]['result'].get('timing', {}).get('sampling_seconds'))
    old[NEW] = new
    order = [NEW] + MAIN9 + [FLEX] + HISTORICAL
    for sid in order:
        old[sid]['main_cohort'] = sid in [NEW] + MAIN9
        old[sid]['display_group'] = 'IVEBench' if sid in [NEW] + MAIN9 else ('FlexiAct' if sid == FLEX else '历史自有素材')
    data['cases'] = [old[sid] for sid in order]
    data['tasks'] = 10
    data['independent_sources'] = 10
    data['displayed_tasks'] = 15
    data['metric_scopes'] = {scope: aggregate(selected) for scope, selected in [
        ('main_IVEBench', [old[s] for s in [NEW] + MAIN9]), ('FlexiAct', [old[FLEX]]), ('all_benchmarks', [old[s] for s in [NEW] + MAIN9 + [FLEX]])]}
    data['scope_counts'] = {'main_IVEBench': 10, 'FlexiAct': 1, 'all_benchmarks': 11}
    data['metric_means'] = data['metric_scopes']['main_IVEBench']
    data['cohort_update'] = {'new_case': NEW, 'new_cohort': c['cohort'], 'retained_cases': MAIN9 + [FLEX] + HISTORICAL}
    return data


def render_r150(original, data):
    template = (ROOT / 'showcase_template.html').read_text()
    svg = re.search(r'<div class="diagram scroll">(.*?)</div>', original, re.S).group(1)
    pub = module('existing_published_results', REFRESH / 'published_results.py').render_published_results
    published = pub(data['published_results'], data['metric_scopes']['main_IVEBench'])
    published = published.replace('其中9条混合子集（6条short、3条long）', '其中10条混合子集（7条short、3条long）').replace('IVEBench 9条混合子集', 'IVEBench 10条混合子集').replace('9（6 short＋3 long）', '10（7 short＋3 long）').replace('采用9/9组', '采用10/10组').replace('ours-ive9', 'ours-ive10')
    template = template.replace('<section class="intro" id="paper-comparison"><h2>公开论文结果</h2><p class="muted">文献对照整理中。</p></section>', published)
    return template.replace('__DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')).replace('__SCHEDULE_SVG__', svg)


def render_v11(original, data, config):
    case = next(c for c in data['cases'] if c['source_id'] == NEW)
    esc = html.escape
    def table(headers, rows):
        return '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(str(x)) + '</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'
    values = []
    for role in METHODS:
        mae = case['mean_absolute_offset'][role]
        values.append([LABELS[role], f"{case['official_metrics'][role]['motion_fidelity']['score']:.6f}", '无共同可定位事件' if mae is None else f'{mae:.3f}'])
    means = data['metric_scopes']['main_IVEBench']
    section = '<section id="ive10-addition-20261024"><div class="prose"><h2>IVEBench 区间对照补充 · 2026-10-24</h2><p>新增 ' + esc(config['title']) + '（short_0177），原提示词、初始种子、帧数与采样设置在六种配置间一致。既有九项 IVEBench 结果与本例组成十项 IVE 展示；FlexiAct 蹲起单列，四项自有历史样例继续保留。</p><p>' + esc(config['display_summary']) + '</p>'
    section += table(['配置', 'MF ↑', '动作 MAE（帧）↓'], values)
    section += '<p>十项 IVEBench 的 MF 均值：普通编辑 ' + f"{means['native']['motion_fidelity']['mean']:.6f}" + '，全程弱引导 ' + f"{means['global_weak']['motion_fidelity']['mean']:.6f}" + '。新增样例的六条成片使用本次独立运行与评分。历史十项混合数据集统计保留在原小节。</p></div>'
    section += '<div class="comparison-labels" style="grid-template-columns:repeat(7,minmax(0,1fr))">' + ''.join('<span>' + esc(LABELS[r]) + '</span>' for r in ROLES) + '</div>'
    section += '<figure><img loading="lazy" src="' + case['overview']['frames'][0]['url'] + '" alt="七配置同帧对照"><figcaption>有效帧 ' + str(case['overview']['default_frame']) + '，相同帧编号与裁剪。</figcaption></figure>'
    section += '<video controls playsinline preload="none" src="' + case['overview']['video'] + '"></video><p>完整九项指标、源视频对照及逐事件偏移见<a href="R150_十组引导区间对照_单文件.html">区间对照报告</a>。</p></section>'
    begin = '<!-- BEGIN IVE10 ADDITION 20261024 -->'
    end = '<!-- END IVE10 ADDITION 20261024 -->'
    if begin in original:
        original, n = re.subn(re.escape(begin) + '.*?' + re.escape(end), '', original, flags=re.S)
        require(n == 1, 'Duplicate V1.1 addition')
    require(original.count('<section id="discussion">') == 1, 'V1.1 insertion anchor changed')
    return original.replace('<section id="discussion">', begin + section + end + '<section id="discussion">', 1)


def build(config_path, publish=False):
    validated = validate(config_path)
    c = validated[0]
    before_r150, before_v11 = R150.read_text(), V11.read_text()
    data = augment(before_r150, validated)
    staging = ROOT / 'staging'
    staging.mkdir(exist_ok=True)
    r150, v11 = staging / R150.name, staging / V11.name
    r150.write_text(render_r150(before_r150, data))
    v11.write_text(render_v11(before_v11, data, c))
    write(staging / 'DATA_WITHOUT_MEDIA.json', {**data, 'cases': [{k: v for k, v in x.items() if k != 'overview'} for x in data['cases']]})
    event_scopes = {}
    for scope in data['scope_counts']:
        selected = [x for x in data['cases'] if (x['main_cohort'] if scope == 'main_IVEBench' else x['dataset'] == 'FlexiAct' if scope == 'FlexiAct' else x['main_cohort'] or x['dataset'] == 'FlexiAct')]
        measured = [x for x in selected if all(isinstance(x.get('mean_absolute_offset', {}).get(r), (int, float)) for r in METHODS)]
        event_scopes[scope] = dict(checked=len(selected), measured=len(measured), case_ids=[x['source_id'] for x in measured], means={r: statistics.mean(x['mean_absolute_offset'][r] for x in measured) if measured else None for r in ROLES})
    write(staging / 'ACTION_OFFSET_SUMMARY.json', dict(protocol='零基闭区间中点差；共同事件内绝对差均值，再按视频等权。', scopes=event_scopes))
    receipt = {'schema': 'ive10-report-build-v1', 'config': str(Path(config_path).resolve()), 'case_count': 15, 'IVEBench': 10, 'FlexiAct': 1, 'historical': 4,
        'new_numeric_metrics': 63, 'source_sha256': {str(R150): hashlib.sha256(before_r150.encode()).hexdigest(), str(V11): hashlib.sha256(before_v11.encode()).hexdigest()},
        'outputs': {str(r150): sha(r150), str(v11): sha(v11)}, 'published': False}
    require(R150.read_text() == before_r150 and V11.read_text() == before_v11, 'Report changed concurrently')
    write(staging / 'BUILD_RECEIPT.json', receipt)
    if publish:
        backup = ROOT / 'backups'
        backup.mkdir(exist_ok=True)
        for target, source in [(R150, r150), (V11, v11)]:
            archived = backup / (target.stem + '_' + sha(target)[:12] + target.suffix)
            if not archived.exists():
                shutil.copy2(target, archived)
            temp = target.with_name(target.name + '.tmp')
            shutil.copy2(source, temp)
            temp.replace(target)
        shutil.copy2(R150, EVAL / 'index.html')
        receipt['published'] = True
        write(ROOT / 'PUBLISHED.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT / 'INPUT.json')
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    build(args.input, args.publish)
