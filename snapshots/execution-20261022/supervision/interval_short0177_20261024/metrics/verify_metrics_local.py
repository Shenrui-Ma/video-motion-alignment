"""Verify the final captured seven-video metric pass without changing raw results."""
import hashlib
import json
import math
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    config = read(HERE / 'config.json')
    manifest = read(HERE / 'prepared/manifest.json')
    prepared = read(HERE / 'prepared/PREPARED.json')
    run = read(HERE / 'RUN.json')
    exit_record = read(HERE / 'EXIT.json')
    summary = read(HERE / 'SUMMARY.json')
    progress = read(HERE / 'PROGRESS.json')
    captured = read(HERE / 'CAPTURE_SHA256.json')
    post_exit = read(HERE / 'POST_EXIT.json')
    assert not post_exit['metric_processes'] and not post_exit['gpu2_compute_apps']
    assert post_exit['boot_id'] == run['boot_id'] and post_exit['uid'] == run['uid']
    assert progress['exit'] == exit_record and not progress['processes']
    assert exit_record['exit_code'] == 0 and exit_record['summary_passed'] is True
    assert summary['passed'] is True and summary['numeric_done'] == 63
    assert summary['qa_not_applicable'] == 7 and summary['failed'] == 0
    assert run['uid'] == config['uid'] == 1016
    assert run['boot_id'] == progress['boot_id']
    assert run['gpu'] == 'GPU-REPLACE-WITH-DEVICE-UUID'
    assert run['manifest_sha256'] == sha(HERE / 'prepared/manifest.json')
    assert run['command'][run['command'].index('--retries') + 1] == '1'
    assert '--once' in run['command']
    assert len(manifest['jobs']) == 7 and {j['method'] for j in manifest['jobs']} == set(config['methods'])
    artifacts = {}
    for relative, digest in captured.items():
        path = HERE / ('raw/' + relative if relative.startswith('evaluation/') else relative)
        assert sha(path) == digest, relative
        artifacts[relative] = {'file': str(path), 'sha256': digest}
    rows = []
    for job in manifest['jobs']:
        method = job['method']
        assert job['sha256'] == prepared['videos'][method]['sha256']
        folder = HERE / 'raw/evaluation/results' / job['id']
        assert read(folder / 'job.json') == job
        assert job['cohort'] == config['cohort']
        assert job['metadata']['edit_prompt'] == config['metadata']['edit_prompt']
        for metric in config['numeric_metrics'] + ['quantity_accuracy']:
            item = read(folder / (metric + '.json'))
            for key, expected in [('job_id', job['id']), ('task_id', config['task_id']),
                                  ('cohort', config['cohort']), ('method', method), ('metric', metric)]:
                assert item[key] == expected, (method, metric, key)
            if metric == 'quantity_accuracy':
                assert item['status'] == 'not_applicable' and item['score'] is None
            else:
                assert item['status'] == 'done' and math.isfinite(item['score'])
                assert item['official_commit'] == config['official_commit']
                assert item['evaluation_seed'] == 0 and item['started'] >= run['time']
                state = read(HERE / 'raw/evaluation/states' / (job['id'] + '__' + metric + '.json'))
                assert state['attempts'] == 1 and state['status'] == 'done' and state['exit_code'] == 0
                assert (folder / (metric + '.log')).is_file()
            rows.append(item)
    by_key = lambda values: {(x['job_id'], x['metric']): x for x in values}
    assert len(summary['rows']) == len(rows) == 70 and by_key(summary['rows']) == by_key(rows)
    assert summary['is_cf_policy'] == config['is_cf_policy']
    source_mf = summary['method_scores']['source']['motion_fidelity']
    for method, scores in summary['method_scores'].items():
        assert scores['motion_fidelity_delta_from_reference'] == scores['motion_fidelity'] - source_mf
    output = dict(passed=True, verified_at=time.time(), numeric_done=63, qa_not_applicable=7,
                  numeric_attempts_each=1, failed=0, processes_after_exit=[],
                  manifest_sha256=run['manifest_sha256'], boot_id=run['boot_id'], gpu=run['gpu'],
                  summary=str(HERE / 'SUMMARY.json'), summary_sha256=sha(HERE / 'SUMMARY.json'),
                  raw_results=str(HERE / 'raw/evaluation/results'),
                  source_motion_fidelity=source_mf,
                  wall_seconds=exit_record['time']-run['time'],
                  post_exit=str(HERE / 'POST_EXIT.json'),
                  raw_bundle_receipt=str(HERE / 'RAW_BUNDLE_RECEIPT.json'), artifacts=artifacts)
    (HERE / 'FINAL_VERIFIED.json').write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in output.items() if k != 'artifacts'}, indent=2))


if __name__ == '__main__':
    main()
