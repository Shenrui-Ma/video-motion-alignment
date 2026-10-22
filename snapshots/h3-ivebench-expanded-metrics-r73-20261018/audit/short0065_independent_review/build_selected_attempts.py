"""Presentation-only selection of successful technical retries; frozen metrics stay intact."""
import argparse
import base64
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import make_showcase
from common import METHODS, PAIRS, read, require, sha, verify_runtime

AUDIT = Path(__file__).resolve().parent
ORIGINAL_SUMMARY = make_showcase.summary


def selected_score(root, source, method, selection):
    sa, ta = selection['source_attempt'], selection['target_attempt']
    path = root / 'results' / source / f'{method}_source{sa}_target{ta}.json'
    require(sha(path) == selection['score_sha256'], 'selected score changed')
    result = read(path)
    require(result['pair_id'] == source and result['method'] == method, 'score identity differs')
    require(result['device'] == 'cpu' and result['cuda_initialized'] is False, 'score device differs')
    for kind, role, attempt in [('source', 'source', sa), ('target', method, ta)]:
        relative = Path('tracks') / role / source / f'attempt{attempt}' / 'REPORT.json'
        report = root / relative
        require(result[kind + '_report']['file'].endswith('/' + relative.as_posix()), 'score attempt differs')
        require(sha(report) == result[kind + '_report']['sha256'], 'track report changed')
        require(read(report)['passed'] is True, 'selected tracker did not pass')
    require(math.isfinite(result['motion_fidelity']), 'nonfinite score')
    return result['motion_fidelity']


def summary():
    result = ORIGINAL_SUMMARY()
    selection = read(AUDIT / 'SELECTED_ATTEMPTS.json')
    require(selection['fixed_sources'] == list(PAIRS), 'fixed denominator changed')
    for row in result['rows']:
        overrides = selection['overrides'].get(row['source'], {})
        for method, selected in overrides.items():
            require(method in METHODS, 'unknown method')
            row[method + '_mf'] = selected_score(ROOT, row['source'], method, selected)
        if overrides:
            row['selected_metric_attempts'] = overrides
        if all(row[m + '_mf'] is not None for m in METHODS):
            row['mf_delta'] = row['forced_mf'] - row['native_mf']
    for method in METHODS:
        values = [r[method + '_mf'] for r in result['rows'] if r[method + '_mf'] is not None]
        result['means'][method] = {'fixed_denominator': 5, 'valid_count': len(values),
            'mean_if_all_five_valid': sum(values) / 5 if len(values) == 5 else None}
    result['selected_attempts_receipt_sha256'] = sha(AUDIT / 'SELECTED_ATTEMPTS.json')
    return result


def build(output):
    verify_runtime()
    make_showcase.summary = summary
    result = make_showcase.build(output)
    embedded = re.findall(r'data:video/mp4;base64,([^\"]+)', Path(output).read_text())
    expected = []
    for source in PAIRS:
        presentation = ROOT / 'showcase' / source / 'PRESENTATION.json'
        if presentation.exists():
            expected.extend(ROOT / 'showcase' / source / (item['name'] + '.mp4')
                            for item in read(presentation)['videos'])
    require(len(embedded) == len(expected), 'embedded media count differs')
    for encoded, path in zip(embedded, expected):
        require(base64.b64decode(encoded, validate=True) == path.read_bytes(), 'embedded bytes differ')
    result.update(embedded_videos=len(embedded), embedded_bytes_verified=True,
                  selected_attempts_sha256=sha(AUDIT / 'SELECTED_ATTEMPTS.json'))
    (AUDIT / 'SELECTED_DISPLAY_RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True)
    print(json.dumps(build(p.parse_args().output), ensure_ascii=False))
