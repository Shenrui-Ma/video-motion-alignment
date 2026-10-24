"""Assemble local report inputs after six complete arms and six verified reviews.

Reads immutable collection artifacts only; performs no remote, GPU or Git work.
Missing official metrics produce a marked INPUT skeleton. Published HTML is not
read or written. The final ASSEMBLY_GATE binds every generated input by SHA256.
"""
import argparse
import base64
import copy
import json
import math
from pathlib import Path

import build_reports as b

HERE = Path(__file__).resolve().parent
COHORT = 'interval_short0177_20261024'


def interval(value, frames, label):
    b.require(isinstance(value, list) and len(value) == 2 and
              all(type(x) is int for x in value) and
              0 <= value[0] <= value[1] < frames, label + ': invalid frame interval')


def checked_collection(root):
    """Reuse the collector's actual provenance and full execution validation."""
    collector = b.module('short0177_local_collector', root / 'collect_completed.py')
    index = b.load(root / 'collection/LOCAL_COLLECTION.json')
    b.require(index.get('all_six_collected') is True and not index.get('errors') and
              not index.get('pending'), 'Six-arm collection gate is incomplete')
    b.require(index['cohort'] == COHORT and index['remote_root'] == collector.REMOTE_ROOT,
              'Collection cohort/root mismatch')
    collected = {}
    for role in b.METHODS:
        b.require(index['arms'][role]['status'] == 'completed', role + ': collection incomplete')
        item = collector.inspect_existing(root / 'collection' / role, role)
        b.require(item['status'] == 'collected', role + ': collection receipt incomplete')
        entries = item['artifacts']
        bundle = {'json': {key: {'base64': base64.b64encode(
            Path(entries[key]['path']).read_bytes()).decode()} for key in collector.FILES},
            'video_remote_path': entries['video']['remote_path'],
            'video_bytes': entries['video']['bytes']}
        _, values = collector.validate_bundle(role, bundle)
        b.require(item['video_sha256'] == entries['video']['sha256'] ==
                  values['result']['files'][0]['sha256'], role + ': collected video mismatch')
        b.require(index['arms'][role]['attempt_id'] == item['attempt_id'] and
                  index['arms'][role]['job_id'] == item['job_id'], role + ': index attempt mismatch')
        collected[role] = {'receipt': item, 'values': values}
    return collected


def checked_review(root, role, source, source_sha, item):
    path = root / 'visual' / role / 'REVIEW.json'
    review = b.load(path)
    b.require(review.get('review_completed') is True and review.get('root_verified') is True,
              role + ': visual review/root verification incomplete')
    b.require((review['case_id'], review['cohort'], review['arm']) == (b.NEW, COHORT, role),
              role + ': review identity mismatch')
    b.require(review['source_events_sha256'] == source_sha and
              Path(review['source_events_file']).resolve() == (root / 'SOURCE_EVENTS.json').resolve(),
              role + ': source-event SHA/path mismatch')
    video = item['artifacts']['video']
    b.require(review['raw_video_sha256'] == video['sha256'] and
              Path(review['raw_video']).resolve() == Path(video['path']).resolve(),
              role + ': review video mismatch')
    b.require(review['fps'] == source['fps'] and review['valid_frames'] == source['valid_frames'] and
              review['generated_frames'] == source['generated_frames'] and
              review['crop_xywh'] == source['source_crop'] and
              review['reviewed_frames'] == [0, source['valid_frames'] - 1] and
              review['frame_index'] == source['frame_index'], role + ': review frame domain mismatch')
    frozen = {e['id']: e for e in source['events']}
    reviewed = {e['id']: e for e in review['events']}
    b.require(len(reviewed) == len(review['events']) and set(reviewed) == set(frozen),
              role + ': frozen event set mismatch')
    for event_id, event in reviewed.items():
        expected = frozen[event_id]
        b.require(all(event[k] == expected[k] for k in ['label', 'definition']) and
                  event['source_interval'] == expected['source'], role + ': frozen event changed')
        b.require(isinstance(event['status'], str) and bool(event['status']) and event.get('evidence'),
                  role + ': event status/evidence required')
        output = event['output_interval']
        if output is None:
            b.require(event['status'] not in ['measured', 'matched'] and
                      event['offset_frames'] is None and event['absolute_offset_frames'] is None,
                      role + ': missing event has a measured offset')
        else:
            interval(output, source['valid_frames'], role + ':' + event_id)
            offset = (sum(output) - sum(expected['source'])) / 2
            b.require(event['status'] not in ['missing', 'missing_action'] and
                      event['offset_frames'] == offset and event['absolute_offset_frames'] == abs(offset),
                      role + ': interval/offset/status mismatch')
    for key in ['contact_sheets', 'full_resolution_evidence']:
        for evidence in review.get('coverage', {}).get(key, []):
            b.require(b.sha(evidence['path']) == evidence['sha256'], role + ': review evidence changed')
    return review, {'file': str(path), 'sha256': b.sha(path), 'root_verified': True}


def metrics_state(manifest_path, summary_path, video_sha, source):
    """Check individual bound rows before accepting the evaluator's completion flag."""
    jobs = {r: 'interval20261024_short_0177__' + r for r in b.ROLES}
    state = {'status': 'pending', 'complete': False, 'numeric_done': 0, 'expected_numeric': 63,
             'manifest_file': str(manifest_path), 'summary_file': str(summary_path)}
    if not manifest_path.exists():
        b.require(not summary_path.exists(), 'Metrics SUMMARY exists without its manifest')
        return jobs, state
    manifest = b.load(manifest_path)
    by_role = {j['method']: j for j in manifest['jobs']}
    b.require(len(manifest['jobs']) == 7 and set(by_role) == set(b.ROLES), 'Metrics manifest roles mismatch')
    for role, job in by_role.items():
        b.require(job['id'] == jobs[role] and job['task_id'] == b.NEW and job['cohort'] == COHORT,
                  role + ': metrics identity mismatch')
        b.require(job['sha256'] == video_sha[role] and job['fps'] == source['fps'] and
                  job['valid_frames'] == source['valid_frames'] and job['crop_xywh'] == source['source_crop'],
                  role + ': scored video/frame mismatch')
    state['manifest_sha256'] = b.sha(manifest_path)
    if not summary_path.exists():
        return jobs, state
    summary = b.load(summary_path)
    seen, done, qa, failed = set(), 0, 0, 0
    for row in summary['rows']:
        role, metric = row['method'], row['metric']
        b.require(role in jobs and row['job_id'] == jobs[role] and row['cohort'] == COHORT and
                  row['task_id'] == b.NEW and metric in b.METRICS, 'Metrics row identity mismatch')
        key = (role, metric)
        b.require(key not in seen, 'Duplicate metrics row')
        seen.add(key)
        if metric in b.NUMERIC and row['status'] == 'done':
            b.require(type(row['score']) in (int, float) and math.isfinite(row['score']), 'Invalid numeric score')
            done += 1
        if metric == 'quantity_accuracy' and row['status'] == 'not_applicable':
            qa += 1
        failed += row['status'] == 'failed'
    b.require(summary['expected_numeric'] == 63 and summary['numeric_done'] == done and
              summary['qa_not_applicable'] == qa and summary['failed'] == failed,
              'Metrics summary totals differ from individual rows')
    complete = done == 63 and qa == 7 and failed == 0
    b.require(summary.get('passed') is complete, 'Metrics passed flag differs from individual rows')
    state.update(status='complete' if complete else 'pending', complete=complete, numeric_done=done,
                 qa_not_applicable=qa, failed=failed, summary_sha256=b.sha(summary_path))
    return jobs, state


def assemble(root, output, display_summary, manifest_path=None, summary_path=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    b.require(isinstance(display_summary, str) and display_summary.strip(), 'Root display_summary text required')
    collected = checked_collection(root)
    source_path = root / 'SOURCE_EVENTS.json'
    source, source_sha = b.load(source_path), b.sha(source_path)
    b.require(source['case_id'] == b.NEW and source['fps'] == 24 and source['valid_frames'] == 60 and
              source['generated_frames'] == 73 and source['source_crop'] == [16, 8, 1280, 720] and
              source['reviewed_frames'] == [0, 59] and source['frozen_before_new_outputs'] is True,
              'Frozen source event/frame contract mismatch')
    b.require(source['events'] and len({e['id'] for e in source['events']}) == len(source['events']),
              'Distinct frozen source events required')
    for event in source['events']:
        interval(event['source'], source['valid_frames'], event['id'])
    b.require(b.sha(source['source_video']) == source['source_sha256'], 'Frozen source video SHA mismatch')
    reviews, provenance = {}, {}
    video_sha = {'source': source['source_sha256']}
    videos = {'source': {'file': source['source_video'], 'sha256': source['source_sha256']}}
    for role, item in collected.items():
        receipt, result = item['receipt'], item['values']['result']
        b.require(result['metadata']['source_sha256'] == source['source_sha256'], role + ': inference source mismatch')
        reviews[role], provenance[role] = checked_review(root, role, source, source_sha, receipt)
        video_sha[role] = receipt['video_sha256']
        videos[role] = {'file': receipt['artifacts']['video']['path'], 'sha256': video_sha[role]}
    manifest_path = Path(manifest_path).resolve() if manifest_path else root / 'metrics/prepared/manifest.json'
    summary_path = Path(summary_path).resolve() if summary_path else root / 'metrics/SUMMARY.json'
    jobs, metric_state = metrics_state(manifest_path, summary_path, video_sha, source)
    events = []
    for frozen in source['events']:
        event = copy.deepcopy(frozen)
        event.update(status_by_role={'source': 'measured'}, evidence_by_role={}, review_event_by_role={})
        for role in b.METHODS:
            reviewed = next(e for e in reviews[role]['events'] if e['id'] == frozen['id'])
            event[role] = copy.deepcopy(reviewed['output_interval'])
            event['status_by_role'][role] = reviewed['status']
            event['evidence_by_role'][role] = reviewed['evidence']
            event['review_event_by_role'][role] = copy.deepcopy(reviewed)
        events.append(event)
    annotation = dict(schema='ive-six-setting-annotation-v1', case_id=b.NEW, cohort=COHORT,
        fps=source['fps'], valid_frames=source['valid_frames'], frame_index=source['frame_index'],
        video_sha256=video_sha, review_completed=True, root_verified=True,
        annotation_source='AI visual frame review; root independently verified each method',
        source_events_file=str(source_path), source_events_sha256=source_sha,
        source_evidence=source['source_evidence'], protocol=source['protocol'], events=events,
        review_sources=provenance, method_reviews=reviews,
        observable_actions_by_role={r: copy.deepcopy(reviews[r].get('observable_actions', [])) for r in b.METHODS})
    for role in b.ROLES:
        videos[role]['job_id'] = jobs[role]
    bindings = dict(case_id=b.NEW, task_id=b.NEW, cohort=COHORT, fps=source['fps'],
        valid_frames=source['valid_frames'], crop_xywh=source['source_crop'], videos=videos,
        completion_gate=str(output / 'ASSEMBLY_GATE.json'))
    metadata = collected['native']['values']['result']['metadata']
    config = dict(schema='ive-six-setting-report-v1', case_id=b.NEW, cohort=COHORT,
        title=source['title'], prompt=metadata['prompt'], seed=metadata['seed'],
        geometry=dict(width=1312, height=736, sampled_frames=73, valid_frames=60, fps=24,
                      crop_xywh=source['source_crop']), display_summary=display_summary.strip(),
        job_ids=jobs, inference_job_ids={r: collected[r]['receipt']['job_id'] for r in b.METHODS},
        video_sha256=video_sha,
        result_files={r: collected[r]['receipt']['artifacts']['result']['path'] for r in b.METHODS},
        router_files={r: collected[r]['receipt']['artifacts']['router']['path'] for r in b.METHODS},
        metrics_manifest=str(manifest_path), metrics_rows=str(summary_path), annotation='ANNOTATION.json',
        presentation='media/PRESENTATION.json',
        assembly_status='metrics_complete' if metric_state['complete'] else 'awaiting_metrics',
        metrics_readiness=metric_state)
    gate = dict(schema='short0177-report-assembly-gate-v1', passed=True, case_id=b.NEW, cohort=COHORT,
        six_arms_complete=True, six_root_verified_reviews=True, source_events_sha256=source_sha,
        source_video_sha256=source['source_sha256'],
        collection_index_sha256=b.sha(root / 'collection/LOCAL_COLLECTION.json'), review_sources=provenance,
        video_sha256=video_sha, metrics_readiness=metric_state,
        scope='Six locally verified complete arms and six root-verified visual reviews; official metric readiness is separate.')
    return {'ANNOTATION.json': annotation, 'MEDIA_BINDINGS.json': bindings, 'INPUT.json': config,
            'ASSEMBLY_GATE.json': gate}


def write_inputs(output, documents):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    gate = copy.deepcopy(documents['ASSEMBLY_GATE.json'])
    for name, value in documents.items():
        if name == 'ASSEMBLY_GATE.json':
            continue
        temporary = output / (name + '.tmp')
        b.write(temporary, value)
        temporary.replace(output / name)
    gate['generated_files'] = {n: b.sha(output / n) for n in documents if n != 'ASSEMBLY_GATE.json'}
    temporary = output / 'ASSEMBLY_GATE.json.tmp'
    b.write(temporary, gate)
    temporary.replace(output / 'ASSEMBLY_GATE.json')
    return gate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=HERE.parent)
    parser.add_argument('--output', type=Path, default=HERE)
    text = parser.add_mutually_exclusive_group(required=True)
    text.add_argument('--display-summary')
    text.add_argument('--display-summary-file', type=Path)
    parser.add_argument('--metrics-manifest', type=Path)
    parser.add_argument('--metrics-summary', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    summary_text = args.display_summary_file.read_text() if args.display_summary_file else args.display_summary
    docs = assemble(args.root, args.output, summary_text, args.metrics_manifest, args.metrics_summary)
    gate = docs['ASSEMBLY_GATE.json'] if args.check_only else write_inputs(args.output, docs)
    print(json.dumps({'passed': gate['passed'], 'write': not args.check_only,
                      'metrics_readiness': gate['metrics_readiness'], 'output': str(args.output)}, ensure_ascii=False))
