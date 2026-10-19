"""Bind archived official MF scores to exact displayed outputs; no tracking/scoring."""
from pathlib import Path
import hashlib
import json
import math

B = Path('/Users/researcher/DevProjects')
COMMIT = 'de9fe1d536732c4d1a384577b5ae54f8fc1730d7'
INDICES = list(range(0, 147, 3))
TIMES = [j / 8 for j in range(49)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify_score(item, root, key, action, arm, version):
    """Fail closed on stale score, foreign output, wrong source or padded timebase."""
    evidence = []

    def load(path, expected=None):
        path = Path(path)
        assert path.is_file(), path
        if expected is not None:
            assert sha(path) == expected, ('evidence SHA mismatch', path)
        evidence.append(path)
        return read(path)

    score_path = root / f'scores/{arm}/{key}/SCORE.json'
    score = load(score_path)
    report_base = root
    if version == 65:
        report_base = root / f'audit/consumer_execution_20261018/{action}_mf_receipts'
    erp = report_base / f'tracks/{arm}/{key}/REPORT.json'
    rrp = report_base / f'tracks/reference/{action}/REPORT.json'
    er = load(erp, score.get('edit_report_sha256') or score['edit_report']['sha256'])
    rr = load(rrp, score.get('reference_report_sha256') or score['reference_report']['sha256'])
    for report in (er, rr):
        assert report['passed'] and report['tracks_shape'] == [3025, 49, 2]
        assert report['grid_size'] == 55 and report['mask'] is None
        assert [float(x['best_effort_timestamp_time']) for x in report['timebase']['frames']] == TIMES
        assert report['nonfinite_track_values'] == 0
    for field in ('checkpoint_sha256', 'metric_functions_sha256', 'vendor_manifest_sha256', 'torch_version', 'cuda_version'):
        assert er[field] == rr[field], ('tracker protocol mismatch', field)
    for field in ('hostname', 'gpu_name'):
        assert er['admission_before_cuda'][field] == rr['admission_before_cuda'][field]
    assert er['case']['role'] == 'generated' and er['case']['method'] == arm
    assert er['case']['generation_frame_indices'] == INDICES
    assert rr['case']['role'] == 'reference'
    eb = load(erp.parent / f'R{version}_BINDING.json')
    assert eb['report']['sha256'] == sha(erp)
    tr = load(root / f'prepared/{key}/{arm}/TRACK_INPUTS.json', er['manifest_sha256'])
    assert tr['inputs'] == [er['case']]
    mi_path = root / f'prepared/{key}/{arm}/METRIC_INPUTS.json'
    mp_path = root / f'prepared/{key}/{arm}/edited49_8fps.mapping.json'
    mi = load(mi_path, er['case']['generation_binding']['metric_inputs']['sha256'])
    mp = load(mp_path, er['case']['generation_binding']['release_mapping']['sha256'])
    video_field = 'ordinary_video_path' if arm == 'native' else 'guided_video_path'
    video_hash = sha(item[video_field])
    assert video_hash == item['media_sha256'][video_field]
    assert video_hash == mi['full158_output_sha256'] == mp['source_sha256'] == er['generation_binding_checked']['full158_sha256']
    assert mi['full_output_indices'] == mp['input_indices'] == INDICES
    assert mi['physical_seconds'] == mp['physical_seconds'] == TIMES
    assert mi['padding_evaluated'] is False and mp['terminal_padding_excluded']
    assert mp['decoded_frame_md5_equal']
    assert mi['edited49_sha256'] == mp['destination_sha256'] == er['case']['sha256']
    assert mi['original_source_sha256'] == rr['case']['sha256']
    assert item['valid_frames'] == 147 and item['fps'] == 24
    prov_path = root / ('inputs' if version == 65 else 'runtime/source_videos') / f'source_{action}_provenance.json'
    prov = load(prov_path, mi['source_provenance']['sha256'])
    assert prov['video_sha256'] == sha(item['reference_video_path']) == item['input_reference_video_sha256']
    assert prov['source_original_sha256'] == mi['original_source_sha256']
    assert prov['input_to_original'][:147] == [n // 3 for n in range(147)]
    assert prov['evaluate_indices'] == INDICES and prov['evaluate_seconds'] == TIMES
    assert prov['frames'] == 158 and prov['terminal_padding_frames'] == 11
    gate = load(root / f'incoming/{key}/PAIR_RUNTIME_GATE.json', mi['producer_receipt']['sha256'])
    assert gate['passed']
    if version == 66:
        assert score['pair_key'] == key and score['method'] == arm
        assert score['prepared_source_sha256'] == prov['video_sha256']
        assert score['portrait_sha256'] == item['input_reference_image_sha256']
        assert score['metric_inputs']['sha256'] == sha(mi_path)
        if score.get('reference_reuse_receipt'):
            reuse = load(rrp.parent / 'R66_SOURCE_REUSE.json', score['reference_reuse_receipt']['sha256'])
            assert reuse['report_preserved_byte_exact'] and reuse['source_sha256'] == rr['case']['sha256']
            assert reuse['files']['REPORT.json'] == sha(rrp)
    assert score['status'] == 'finite' and math.isfinite(score['score'])
    assert score['frames'] == 49 and score['points'] == 3025 and score['cuda_initialized'] is False
    return score['score'], evidence


def verify_early_score(item):
    """R49 Native, and the separately proved pixel-identical R50 chest reuse."""
    action = item['source_id']
    analysis = B / 'h3-timing-auto-motion-r26-20261017/analysis'
    nr = analysis / 'flexiact_native_scores_r49_20261017/native_mf_complete5'
    sr = analysis / 'flexiact_official_metric_20261017/audit/five_source_tracks'
    r49 = B / 'h3-timing-flexiact-native-r49-20261017'
    released = r49 / f'analysis/postrun/captured/batch/final/r49_source_{action}_seed2026101701_native'
    files = []

    def load(p, expected=None):
        p = Path(p)
        if expected is not None: assert sha(p) == expected, p
        files.append(p)
        return read(p)

    sp = nr / f'scores/native/{action}/SCORE.json'
    s = load(sp)
    ep = nr / f'tracks/native/{action}/REPORT.json'
    rp = sr / f'outputs/reference/{action}/REPORT.json'
    er = load(ep, s['edit_report_sha256'])
    rr = load(rp, s['reference_report_sha256'])
    for r in (er, rr):
        assert r['passed'] and r['tracks_shape'] == [3025,49,2]
        assert r['grid_size'] == 55 and r['mask'] is None
        assert [float(x['best_effort_timestamp_time']) for x in r['timebase']['frames']] == TIMES
    for k in ('checkpoint_sha256','metric_functions_sha256','vendor_manifest_sha256','torch_version','cuda_version'):
        assert er[k] == rr[k]
    mi = load(released/'METRIC_INPUTS.json', er['generation_binding_checked']['metric_inputs_sha256'])
    mp = load(released/'edited49_8fps.mapping.json', er['generation_binding_checked']['release_mapping_sha256'])
    original = sha(item['ordinary_video_path'])
    assert original == item['media_sha256']['ordinary_video_path'] == mi['full158_output_sha256'] == er['generation_binding_checked']['full158_sha256'] == mp['source_sha256']
    assert mi['target_sha256'] == item['input_reference_image_sha256']
    assert mi['original_source_sha256'] == rr['case']['sha256']
    assert mi['full_output_indices'] == mp['input_indices'] == er['case']['generation_frame_indices'] == INDICES
    assert mi['physical_seconds'] == mp['physical_seconds'] == TIMES
    assert mi['padding_evaluated'] is False and mp['terminal_padding_excluded'] and mp['decoded_frame_md5_equal']
    assert mi['edited49_sha256'] == er['case']['sha256'] == mp['destination_sha256']
    prov = load(r49/f'inputs/source_{action}_provenance.json')
    assert prov['source_original_sha256'] == rr['case']['sha256']
    assert prov['video_sha256'] == sha(item['reference_video_path']) == item['input_reference_video_sha256']
    assert prov['evaluate_indices'] == INDICES and prov['input_to_original'][:147] == [n//3 for n in range(147)]
    assert s['status'] == 'finite' and math.isfinite(s['score']) and s['frames'] == 49
    guided = None
    if item['id'] == 'flex_r50_chest_auto':
        d = B/'h3-timing-flexiact-auto-r50-retry-20261017/analysis/postrun/audit/media_identity/chest'
        reuse = load(d/'REUSED_MF_SCORE.json')
        assert reuse['cached_native_score']['sha256'] == sha(sp)
        assert reuse['motion_fidelity'] == s['score'] and reuse['new_tracker_invocations'] == 0
        full = load(d/'full158_output.json',reuse['full_video_identity_proof']['sha256'])
        edit = load(d/'edited49.json',reuse['score_input_identity_proof']['sha256'])
        assert full['comparison']['exact'] and edit['comparison']['exact']
        assert full['same_physical_timebase'] and edit['same_physical_timebase']
        assert full['left']['sha256'] == original
        assert full['right']['sha256'] == sha(item['guided_video_path']) == item['media_sha256']['guided_video_path']
        assert edit['left']['sha256'] == edit['right']['sha256'] == mi['edited49_sha256']
        guided = s['score']
    return s['score'], guided, files


def enrich(items):
    ledger = []
    for item in items:
        metric = dict(native=None, guided=None, delta=None, higher_is_better=True,
                      status='pending', protocol=f'FlexiAct official MF (commit {COMMIT})',
                      source_files=[], source_sha256={}, valid_frames=147,
                      scope='当前输出尚无逐文件绑定的官方MF评分；缺值保留null。')
        spec = None
        if item['id'].startswith('flex_r65_'):
            spec = (65, 'h3-flexiact-forced-metrics-r65-20261018', item['source_id'])
        elif item['id'].startswith('flex_r66_'):
            spec = (66, 'h3-flexiact-expanded-evaluation-r66-20261018', item['id'].removeprefix('flex_r66_'))
        if spec:
            version, dirname, key = spec
            evidence = []
            for arm, field in [('native', 'native'), ('forced', 'guided')]:
                metric[field], files = verify_score(item, B / dirname, key, item['source_id'], arm, version)
                evidence.extend(files)
            metric['delta'] = metric['guided'] - metric['native']
            metric['status'] = 'complete'
            metric['source_files'] = sorted(set(str(p) for p in evidence))
            metric['source_sha256'] = {p: sha(p) for p in metric['source_files']}
            metric['scope'] = ('当前成片的官方MF；49个原始8fps时刻，输出索引0,3,…144，排除11帧尾部padding。'
                               '整帧轨迹方向相似度，未分人体/背景；不能单独判断身份、场景或毫秒时延。'
                               + item['pair_group'] + '，与其他分组分别呈现。')
        if item['id'].startswith('flex_r49_') or item['id'] == 'flex_r50_chest_auto':
            metric['native'], metric['guided'], evidence = verify_early_score(item)
            metric['delta'] = metric['guided'] - metric['native'] if metric['guided'] is not None else None
            metric['status'] = 'complete'
            metric['source_files'] = sorted(set(str(p) for p in evidence))
            metric['source_sha256'] = {p: sha(p) for p in metric['source_files']}
            metric['scope'] = ('R49实际普通编辑的官方MF；49个8fps时刻，输出0,3,…144，尾pad排除。'
                               'R50 chest仅在官方loader逐帧像素与时间戳相同的独立证明下复用，实际0次干预。'
                               if metric['guided'] is not None else
                               'R49实际普通编辑的官方MF；49个8fps时刻，输出0,3,…144，尾pad排除。')
        if item['comparison_kind'] != 'guided_pair':
            metric['scope'] += ' 当前条目无真实引导对照，guided和delta不适用。'
        item.setdefault('quantitative_metrics', {})['motion_fidelity'] = metric
        ledger.append({'id': item['id'], **metric})
    return ledger
