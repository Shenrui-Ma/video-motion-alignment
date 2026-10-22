"""Build a concise research update from verified, actual experimental records."""
from pathlib import Path
from html import escape
import base64
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
INVENTORY = Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/inventory')
IDS = [
    'r73_short_0252', 'r89_short_0358', 'r99_short_0230',
    'r107_long_0174', 'flex_r101_human2animal_1__game_man_4_fixed',
    'r110_short_0114_promptcontrol',
    'r111_long_0174_spatial', 'flex_r90_one_leg__movie_man_9_prompt_control',
    'r106_short_0252_sampler_control',
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def embed(path, digest, mime):
    path = Path(path)
    assert sha(path) == digest, f'Changed media: {path}'
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()


def main():
    rows = {}
    bound = []
    evidence = {}

    def bind(path, digest=None):
        actual = sha(path)
        assert digest is None or actual == digest, f'Changed evidence: {path}'
        evidence[str(path)] = actual
        return read(path)

    def validate_row(row):
        for path, digest in row.get('evidence_sha256', {}).items():
            bind(path, digest)
        for path, digest in row.get('quantitative_metrics', {}).get('motion_fidelity', {}).get('source_sha256', {}).items():
            bind(path, digest)

    def event_row(title, name, values):
        cells = [title, name]
        for value in values:
            cells.append('–'.join(map(str, value)) if isinstance(value, list) else str(value or 'UNKNOWN：时刻无法判定'))
        return '<tr>' + ''.join('<td>' + escape(x) + '</td>' for x in cells) + '</tr>'
    for name in ('ivebench', 'flexiact'):
        path = INVENTORY / (name + '.json')
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        snapshot = ROOT / (name + '_' + digest[:16] + '.json')
        if snapshot.exists():
            assert snapshot.read_bytes() == content
        else:
            snapshot.write_bytes(content)
        bound.append({'path': str(snapshot), 'sha256': digest})
        for row in json.loads(content)['items']:
            assert row['id'] not in rows
            rows[row['id']] = row

    selected = [rows[k] for k in IDS]
    figures, table, events = [], [], []
    for row in selected:
        validate_row(row)
        mf = row.get('quantitative_metrics', {}).get('motion_fidelity', {})
        if mf.get('status') == 'complete' and row.get('comparison_kind') == 'guided_pair' and row['id'] != 'r111_long_0174_spatial':
            n, g = mf['native'], mf['guided']
            assert math.isfinite(n) and math.isfinite(g)
            assert abs((g - n) - mf['delta']) < 1e-9
            table.append('<tr>' + ''.join('<td>' + escape(x) + '</td>' for x in [
                row['benchmark'], row['title'], f'{n:.4f}', f'{g:.4f}',
                f'{g-n:+.4f}', row.get('display_summary', row['review_summary'])
            ]) + '</tr>')
        quant = row.get('quantitative_metrics', {}).get('event_timing', {})
        if quant and row.get('comparison_kind') == 'guided_pair':
            source_events = bind(quant['source_file'], quant['source_sha256'])
            for e in quant['events']:
                events.append(event_row(row['title'], e['name'], [e.get(k) for k in ('source_frames', 'native_frames', 'guided_frames')]))
            if row['id'] == 'r73_short_0252':
                last = source_events['events'][-1]
                assert last['source_visible_frames'] == last['native_visible_frames'] == last['forced_visible_frames'] == [96, 97]
                events.append(event_row(row['title'], last['name'], ['96–97 可见；到达时刻未定'] * 3))
        if row['id'] == 'r107_long_0174':
            review_path = next(p for p in row['evidence_sha256'] if p.endswith('/full_frame_review/REVIEW.json'))
            review = bind(review_path, row['evidence_sha256'][review_path])
            for e in review['events']:
                values = [e.get(k) for k in ('source_frames', 'native_frames', 'guided_frames')]
                if e.get('guided_comparability') == 'joint-event-not-comparable':
                    values[-1] = '动作分开：先转头、后抬手；联合事件不可比'
                events.append(event_row(row['title'], e['definition'], values))
            terminal = review['terminal_motion']
            events.append(event_row(row['title'], terminal['source_description'], [terminal['source_frames'], terminal['native'], terminal['guided']]))
        img = ''
        if row.get('reference_image_used') and row.get('reference_image_path'):
            p = row['reference_image_path']
            mime = 'image/png' if Path(p).suffix.lower() == '.png' else 'image/jpeg'
            img = '<div class="reference"><img alt="实际角色参考图" src="' + embed(p, row['media_sha256']['reference_image_path'], mime) + '"><span>实际角色参考图</span></div>'
        video = embed(row['comparison_video_path'], row['media_sha256']['comparison_video_path'], 'video/mp4')
        labels = '　｜　'.join(row['column_labels'])
        figures.append(
            '<figure id="' + escape(row['id']) + '"><div class="case-title"><span>' + escape(row['benchmark']) + '</span><h3>' + escape(row['title']) + '</h3></div>'
            + '<p>' + escape(row.get('display_task', row['task'])) + '</p>' + img
            + '<video controls muted playsinline preload="none" src="' + video + '"></video>'
            + '<figcaption>' + escape(labels) + '</figcaption><p class="finding">' + escape(row.get('display_summary', row['review_summary'])) + '</p></figure>'
        )
    template = (ROOT / 'template.html').read_text()
    method = (ROOT / 'method.svg').read_text()
    html = template.replace('@@METHOD@@', method).replace('@@RESULTS@@', ''.join(figures))
    attention = bind(ROOT / 'attention_readout_receipt.json')
    assert sha(attention['svg']) == attention['sha256']
    bind(attention['snapshot'], attention['snapshot_sha256'])
    evidence[attention['svg']] = attention['sha256']
    html = html.replace('@@ATTENTION@@', Path(attention['svg']).read_text())
    html = html.replace('@@MF_ROWS@@', ''.join(table)).replace('@@EVENT_ROWS@@', ''.join(events))
    interval_path = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/audit/event_interval_uncertainty_20261019/RESULT.json')
    intervals = bind(interval_path, 'ee5ca1dafa0a5780487c96a15f7a217997f2a9f45702ef73c782124396074c89')
    for case in intervals['cases']:
        bind(case['annotation']['file'], case['annotation']['sha256'])
    for name, digest in intervals['code_sha256'].items():
        code = interval_path.parent / name
        assert sha(code) == digest
        evidence[str(code)] = digest
    bounds = {case['case_id']: case['events'] for case in intervals['cases']}
    mask = bounds['r73_short_0252']
    drink = bounds['r89_short_0358'][0]
    assert mask[0]['absolute_error_change_frames'] == mask[1]['absolute_error_change_frames']
    def reduction_text(event):
        lo, hi = event['absolute_error_change_frames']
        assert lo <= hi < 0
        return f'{-hi:g}–{-lo:g}'
    summary = (
        f'在上述视觉标注范围内，机舱抬手和抓住面罩的绝对时间误差各减少 {reduction_text(mask[0])} 帧，'
        f'饮酒样例的第一次降瓶减少 {reduction_text(drink)} 帧。'
        '计算时两版共享同一个参考事件时刻；这些数值是标注区间内的算术范围，未计入区间外的标注误差。'
    )
    html = html.replace('@@EVENT_BOUND_SUMMARY@@', escape(summary))
    spatial_mf = rows['r111_long_0174_spatial']['quantitative_metrics']['motion_fidelity']
    assert spatial_mf['status'] == 'complete'
    assert abs(spatial_mf['fixed_control'] - rows['r107_long_0174']['quantitative_metrics']['motion_fidelity']['guided']) < 1e-12
    for name, key in [('NATIVE', 'native'), ('FIXED', 'fixed_control'), ('NEW', 'guided')]:
        html = html.replace('@@SPATIAL_' + name + '_MF@@', f'{spatial_mf[key]:.4f}')
    sampler_mf = rows['r106_short_0252_sampler_control']['quantitative_metrics']['motion_fidelity']
    assert sampler_mf['status'] == 'complete'
    assert abs(sampler_mf['res_multistep'] - sampler_mf['euler'] - sampler_mf['delta']) < 1e-12
    for name, key in [('EULER', 'euler'), ('RES', 'res_multistep')]:
        html = html.replace('@@SAMPLER_' + name + '_MF@@', f'{sampler_mf[key]:.4f}')
    extended = rows['r97_short_0358_extended']
    validate_row(extended)
    ext_mf = extended['quantitative_metrics']['motion_fidelity']
    ext_review_path = next(p for p in extended['evidence_sha256'] if p.endswith('/root_full_review/REVIEW.json'))
    ext_review = bind(ext_review_path, extended['evidence_sha256'][ext_review_path])
    away = ext_review['event_intervals']['bottle_away']
    assert away['source'] == [80, 84] and away['fixed'] == away['extended'] == [94, 97]
    assert abs(ext_mf['original_fixed'] - rows['r89_short_0358']['quantitative_metrics']['motion_fidelity']['guided']) < 1e-12
    diag_path = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/audit/mf_time_sensitivity_20261019/RESULT.json')
    diag = bind(diag_path)
    assert sha(diag['official_file']) == diag['official_file_sha256']
    evidence[diag['official_file']] = diag['official_file_sha256']
    counter = diag['visibility_counterexample']
    assert counter['physical_delay_frames'] == 24 and counter['different_visibility_intervals_score'] == 1
    html = html.replace('@@FIXED_MF@@', f"{ext_mf['original_fixed']:.4f}").replace('@@EXTENDED_MF@@', f"{ext_mf['guided']:.4f}")
    html = html.replace('@@DIAGNOSTIC_DELAY@@', str(counter['physical_delay_frames'])).replace('@@DIAGNOSTIC_SCORE@@', f"{counter['different_visibility_intervals_score']:g}")
    assert '@@' not in html
    assert html.count('<video ') == len(selected)
    assert html.count('src="data:video/mp4;base64,') == len(selected)
    assert '<script src=' not in html and 'src="file:' not in html
    out = ROOT / 'DRAFT.html'
    out.write_text(html)
    receipt = {
        'output': str(out), 'sha256': sha(out), 'bytes': out.stat().st_size,
        'inventory_snapshots': bound, 'selected_ids': IDS,
        'bound_evidence_sha256': evidence,
        'selection': 'Representative positive, partial, neutral and failed task outcomes; not a benchmark aggregate.',
        'videos': len(selected), 'verification': 'Bound evidence hashes and embedded media checked; browser UI unavailable.',
        'publication': 'Built from verified inventory snapshots; publication is recorded separately.',
    }
    (ROOT / 'BUILD_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
