"""Local-only archival media QA. Writes only this subtask's report/evidence."""
import argparse
import datetime
from fractions import Fraction
import hashlib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import unquote, urlsplit

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'analysis/final_media_qa'
REPORT = ROOT / 'analysis/final_media_qa.json'
FFPROBE = shutil.which('ffprobe') or '/opt/homebrew/bin/ffprobe'
CACHE_FILE = EVIDENCE / 'media_cache.json'


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'a' and 'name' in attrs:
            self.ids.add(attrs['name'])
        for key in ('src', 'href'):
            if key in attrs:
                self.links.append({'tag': tag, 'attribute': key, 'url': attrs[key]})


def html_check(path):
    parsed = Links()
    parsed.feed(path.read_text())
    refs = []
    for link in parsed.links:
        url = urlsplit(link['url'])
        if url.scheme and url.scheme != 'file':
            refs.append(dict(link, local=False))
            continue
        target = (Path(unquote(url.path)) if url.path.startswith('/') else path.parent / unquote(url.path)) if url.path else path
        target = target.resolve()
        row = dict(link, local=True, resolved_path=str(target), exists=target.exists())
        if url.fragment:
            if target.exists() and target.suffix.lower() in ('.html', '.htm'):
                other = parsed if target == path.resolve() else Links()
                if other is not parsed:
                    other.feed(target.read_text())
                row['anchor_exists'] = unquote(url.fragment) in other.ids
            else:
                row['anchor_exists'] = False
        refs.append(row)
    return {'file': str(path.relative_to(ROOT)), 'sha256': digest(path),
            'ids': sorted(parsed.ids), 'references': refs,
            'all_local_references_exist': all(x['exists'] and x.get('anchor_exists', True) for x in refs if x['local'])}


class Check:
    def __init__(self):
        self.cache = read(CACHE_FILE) if CACHE_FILE.exists() else {}

    def media(self, path):
        stat = path.stat()
        key = str(path)
        identity = [stat.st_size, stat.st_mtime_ns]
        if self.cache.get(key, {}).get('identity') == identity:
            return self.cache[key]['result']
        raw = subprocess.check_output([FFPROBE, '-v', 'error', '-count_frames', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames,duration,codec_name:format=duration',
            '-of', 'json', str(path)], text=True, timeout=60)
        data = json.loads(raw)
        if len(data['streams']) != 1:
            raise ValueError('Expected one selected video stream')
        s = data['streams'][0]
        result = {'file': str(path.relative_to(ROOT)), 'sha256': digest(path),
                  'frames': int(s['nb_read_frames']), 'fps': str(Fraction(s['avg_frame_rate'])),
                  'width': s['width'], 'height': s['height'], 'codec': s.get('codec_name'),
                  'video_duration_seconds': float(s['duration']),
                  'container_duration_seconds': float(data['format']['duration'])}
        self.cache[key] = {'identity': identity, 'result': result}
        return result

    def sheet(self, path, expected_size):
        stat = path.stat()
        key = str(path)
        identity = [stat.st_size, stat.st_mtime_ns]
        if self.cache.get(key, {}).get('identity') == identity:
            result = self.cache[key]['result']
        else:
            with Image.open(path) as im:
                dimensions, fmt = list(im.size), im.format
                im.verify()
            result = {'file': str(path.relative_to(ROOT)), 'size': dimensions,
                      'format': fmt, 'image_decodes': True}
            self.cache[key] = {'identity': identity, 'result': result}
        return dict(result, expected_size=expected_size, dimensions_match=result['size'] == expected_size)

    def run(self):
        issues, pending = [], []
        queue = read(ROOT / 'configs/queue.json')
        meta = read(ROOT / 'inputs/source_manifest.json')
        expected = {f"{clip['clip_id']}_{arm}_s{seed}" for clip in meta['clips'] for arm in ('a', 'b') for seed in (1, 2)}
        jobs = queue['jobs']
        if not (queue.get('sealed') is True and queue.get('formal_output_cap') == 12 and len(jobs) == len(expected) == 12 and set(jobs) == expected):
            issues.append('Sealed queue does not exactly match three-source A/B x two-seed matrix')
        archive = read(ROOT / 'analysis/archive_validation.json')
        ledger = {row['run_id']: row for row in archive['formal_runs']}
        reviewed = read(ROOT / 'review/manifest.json')
        if reviewed.get('renderer_version') != 2:
            issues.append('Renderer version changed; prior renderer2 proof no longer sufficient')
        if reviewed.get('errors'):
            issues.append({'renderer_errors': reviewed['errors']})
        admission = read(ROOT / 'configs/queue_admission.json')
        formal = []
        for run in jobs:
            if ledger.get(run, {}).get('status') != 'complete':
                pending.append(run + ': formal archive not complete')
                continue
            try:
                graph_path = ROOT / f'configs/{run}.json'
                graph = read(graph_path)
                history = read(ROOT / f'logs/{run}_history.json')
                job = read(ROOT / f'logs/{run}_job.json')
                row = {'run_id': run, 'node14_is_unique_named_formal_SaveVideo':
                    graph.get('14', {}).get('class_type') == 'SaveVideo' and graph['14']['inputs']['filename_prefix'] == run
                    and sum(n.get('class_type') == 'SaveVideo' and n.get('inputs', {}).get('filename_prefix') == run for n in graph.values()) == 1,
                    'history_graph_matches': history['prompt'][2] == graph,
                    'graph_matches_frozen_admission_and_job': digest(graph_path) == admission['graph_sha256'][run] == job['graph_sha256'],
                    'history_prompt_matches_job': history['prompt'][1] == job['prompt_id'],
                    'history_success': history['status'].get('completed') is True and history['status'].get('status_str') == 'success'}
                artifacts = [a for a in history['outputs']['14'].get('images', []) if a.get('type') == 'output' and a.get('filename', '').endswith('.mp4')]
                if len(artifacts) != 1:
                    raise ValueError('History SaveVideo14 does not have exactly one MP4')
                a = artifacts[0]
                path = ROOT / 'outputs' / a.get('subfolder', '') / a['filename']
                matches = [p for p in (ROOT / 'outputs').rglob('*.mp4') if re.fullmatch(re.escape(run) + r'_\d+_\.mp4', p.name)]
                row['exact_formal_file_matches'] = [str(p.relative_to(ROOT)) for p in matches]
                row['unique_file_matches_history'] = len(matches) == 1 and matches[0] == path
                row['media'] = self.media(path)
                m = row['media']
                row['media_expected'] = m['frames'] == 141 and m['fps'] == '24' and (m['width'], m['height']) == (1312, 736) and abs(m['video_duration_seconds'] - 5.875) < 0.001
                row['output_hash_matches_archive'] = m['sha256'] == ledger[run]['output_sha256']
                if not all(v for k, v in row.items() if isinstance(v, bool)):
                    issues.append({'run_id': run, 'failed_checks': [k for k, v in row.items() if isinstance(v, bool) and not v]})
                formal.append(row)
            except Exception as exc:
                issues.append({'run_id': run, 'error': type(exc).__name__ + ': ' + str(exc)})
        comparisons, assets = [], {}
        expected_cases = {f"{clip['clip_id']}_s{seed}" for clip in meta['clips'] for seed in (1, 2)}
        actual_cases = [f"{c['clip_id']}_s{c['seed']}" for c in reviewed['cases']]
        if set(actual_cases) != expected_cases or len(actual_cases) != 6:
            issues.append('Review cases are not exactly six expected source/seed groups')
        for case in reviewed['cases']:
            case_id = f"{case['clip_id']}_s{case['seed']}"
            assets[case['source']['path']] = case['source']
            for asset in case.get('assets', {}).values():
                assets[asset['path']] = asset
            if case['status'] != 'ready':
                pending.append(case_id + ': comparison render not ready')
                continue
            try:
                result = case['render']
                row = {'case_id': case_id, 'original_frame_counts': result['original_frame_counts'],
                       'renderer_warning': result.get('warning', ''), 'videos': []}
                for key, fps, duration in [('comparison', '24', 5.875), ('quarter_speed', '6', 23.5)]:
                    m = self.media(Path(result[key]))
                    m['expected'] = m['frames'] == 141 and m['fps'] == fps and (m['width'], m['height']) == (1968, 416) and abs(m['video_duration_seconds'] - duration) < 0.001
                    row['videos'].append(dict(m, role=key))
                row['all_media_expected'] = all(m['expected'] for m in row['videos'])
                row['no_source_frame_mismatch'] = result['original_frame_counts'] == [141, 141, 141] and not row['renderer_warning']
                lo, hi = case['event_review_bounds_inclusive']
                event_sheets = []
                for index, raw_path in enumerate(result['event_sheets']):
                    count = min(4, hi - lo + 1 - index * 4)
                    event_sheets.append(self.sheet(Path(raw_path), [1968, count * 416]))
                row['event_sheets'] = event_sheets
                row['event_sheets_complete'] = len(event_sheets) == math.ceil((hi - lo + 1) / 4) and all(x['dimensions_match'] for x in event_sheets)
                if not all(row[k] for k in ('all_media_expected', 'no_source_frame_mismatch', 'event_sheets_complete')):
                    issues.append({'case_id': case_id, 'error': 'comparison video/event-sheet mismatch'})
                comparisons.append(row)
            except Exception as exc:
                issues.append({'case_id': case_id, 'error': type(exc).__name__ + ': ' + str(exc)})
        full_frame_sheets = []
        for raw_path, asset in assets.items():
            try:
                p = Path(raw_path)
                m = self.media(p)
                sheet_rows = []
                for index, relpath in enumerate(asset['sheets']):
                    count = min(30, 141 - index * 30)
                    if count <= 0:
                        raise ValueError('Unexpected extra full-frame sheet')
                    sheet_rows.append(dict(self.sheet(ROOT / 'review' / relpath, [1680, 48 + 212 * math.ceil(count / 5)]),
                                           frame_interval_inclusive=[index * 30, index * 30 + count - 1]))
                valid = m['frames'] == 141 and m['sha256'] == asset['sha256'] and len(sheet_rows) == 5 and all(x['dimensions_match'] for x in sheet_rows)
                full_frame_sheets.append({'asset': str(p.relative_to(ROOT)), 'all141_frames_covered_by_renderer2_sheet_structure': valid, 'sheets': sheet_rows})
                if not valid:
                    issues.append({'asset': raw_path, 'error': 'Full-frame sheet coverage/hash mismatch'})
            except Exception as exc:
                issues.append({'asset': raw_path, 'error': type(exc).__name__ + ': ' + str(exc)})
        html = []
        for path in (ROOT / 'START_HERE.html', ROOT / 'review/index.html'):
            if not path.exists():
                issues.append('Missing entry HTML: ' + str(path))
                continue
            result = html_check(path)
            html.append(result)
            if not result['all_local_references_exist']:
                issues.append({'html': result['file'], 'missing_targets': [r for r in result['references'] if r['local'] and (not r['exists'] or not r.get('anchor_exists', True))]})
        review_html = next((h for h in html if h['file'] == 'review/index.html'), None)
        if review_html is None or not expected_cases.issubset(set(review_html['ids'])):
            issues.append('Review HTML lacks an expected case anchor')
        chain_files = [
            'analysis/first_pair_integrity_review.json', 'analysis/renderer_adaptation_checks.json',
            'analysis/runtime_gpu_handoff/gpu0_to_gpu1_1791877135/handoff_summary.json',
            'analysis/cross_gpu_seed2_input_integrity.json',
            'analysis/runtime_interruption_05b1/diagnosis.json',
            'analysis/runtime_interruption_05b1/recovery_addendum.json',
            'analysis/runtime_interruption_05b1/recovery_audit_freshness_probe.json',
            'attempts/05b1_service_disappeared/original_active_job.json']
        chain = [{'file': name, 'exists': (ROOT / name).exists(),
                  'sha256': digest(ROOT / name) if (ROOT / name).exists() else None} for name in chain_files]
        if not all(x['exists'] for x in chain):
            issues.append({'missing_runtime_chain': [x['file'] for x in chain if not x['exists']]})
        recovery = read(ROOT / 'analysis/runtime_interruption_05b1/recovery_addendum.json')
        retry_history = read(ROOT / 'logs/05_real_megumi_v_b_s1_history.json')
        retry_id_matches = retry_history['prompt'][1] == recovery['new_prompt_id']
        if not retry_id_matches:
            issues.append('Successful05b1 history is not the recorded retry prompt_id')
        cross = read(ROOT / 'analysis/cross_gpu_seed2_input_integrity.json')
        cross_verified = cross.get('status') == 'complete_pair_independently_blob_verified'
        if not cross_verified:
            issues.append('Cross-GPU seed2 final blob proof is incomplete')
        all_archived = (archive['summary']['successful_formal_generations'] == archive['summary']['fully_archived_formal_runs'] == 12 and archive['summary']['valid_pairs'] == 6 and archive['primary_status'] == 'complete')
        if all_archived:
            entrance = (ROOT / 'START_HERE.html').read_text()
            match = re.search(r'已验证归档：\s*(\d+)\s*/\s*12.*?(\d+)\s*/\s*6', entrance, re.S)
            if match and tuple(map(int, match.groups())) != (12, 6):
                issues.append('START_HERE still displays stale formal/pair progress')
        eligible_complete = all_archived and len(formal) == 12 and len(comparisons) == 6 and len(full_frame_sheets) == 15 and not pending
        status = 'pass' if eligible_complete and not issues else 'needs_attention' if issues else 'in_progress'
        report = {'schema': 'h3-final-media-qa-v1', 'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'status': status, 'final_pass': status == 'pass', 'issues': issues, 'pending': pending,
            'scope': 'Local-only media, archive entry and runtime evidence-chain QA. No SSH, GPU, services, paused inventory lane, pickle or model payload access.',
            'archive_status': archive['status'], 'archive_summary': archive['summary'],
            'fixed_matrix': {'sealed': queue.get('sealed'), 'jobs': jobs, 'expected_count': 12, 'exact_match': set(jobs) == expected and len(jobs) == 12},
            'formal_videos_checked': formal, 'comparison_groups_checked': comparisons,
            'full_frame_sheet_assets_checked': full_frame_sheets, 'html_checks': html,
            'runtime_evidence_chain': chain, 'retry05b1_success_matches_recorded_prompt': retry_id_matches,
            'cross_gpu_seed2_independent_blob_check_complete': cross_verified,
            'excluded_from_formal_success_count': {'benchmarks': [b.get('run_id') for b in archive['benchmarks']],
                'attempt_roots': [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'attempts').iterdir()) if p.is_dir()],
                'counting_rule': 'Only the12 sealed formal run IDs, exact SaveVideo14 output filename and successful matching submitted history count; benchmark and all attempt paths remain excluded.'},
            'counts': {'formal_videos_checked': len(formal), 'comparison_groups_checked': len(comparisons),
                       'all_frame_assets_checked': len(full_frame_sheets), 'all_frame_sheet_files_checked': sum(len(x['sheets']) for x in full_frame_sheets)},
            'limits': ['Media duration checks use the video stream duration; container audio padding may differ.',
                       'All-frame coverage uses renderer2 numbering/layout, source/output hashes,141decoded-frame probes and valid5-page JPEG structure. First-pair integrity report previously replayed15pages byte-for-byte; no unnecessary replay of every scientific image is performed.',
                       'Quarter speed is141frames at6FPS, checked against the validated renderer2 setpts-only method; no interpolation method is introduced.',
                       'This does not judge motion preservation, identity quality or scientific validity.',
                       'Remote service/GPU cleanup is handled by the parent and is not asserted by this media-only subtask.']}
        save(CACHE_FILE, self.cache)
        save(REPORT, report)
        return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--watch', action='store_true')
    ap.add_argument('--max-seconds', type=int, default=5400)
    args = ap.parse_args()
    identity = subprocess.check_output(['ps', '-p', str(os.getpid()), '-o', 'pid=,uid=,lstart=,command='], text=True).strip()
    save(EVIDENCE / 'worker_identity.json', {'pid': os.getpid(), 'identity_ps': identity,
        'registered_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'watch': args.watch, 'deadline_seconds': args.max_seconds, 'cpu_only': True})
    checker = Check()
    end = time.monotonic() + min(args.max_seconds, 5400)
    previous = None
    while True:
        try:
            report = checker.run()
            signature = json.dumps([report['status'], report['counts'], report['issues']], sort_keys=True)
            if signature != previous:
                print(json.dumps({'status': report['status'], 'counts': report['counts'], 'issues': report['issues'], 'pending_count': len(report['pending'])}, ensure_ascii=False), flush=True)
                previous = signature
            if report['final_pass']:
                return 0
        except Exception as exc:
            save(EVIDENCE / 'latest_read_error.json', {'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'error': type(exc).__name__ + ': ' + str(exc)})
            print('READ_CHECK_ERROR', type(exc).__name__, str(exc), flush=True)
        if not args.watch:
            return 0
        if time.monotonic() >= end:
            save(EVIDENCE / 'watch_timeout.json', {'timed_out': True, 'max_seconds': args.max_seconds,
                'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'final_pass_claimed': False})
            return 2
        time.sleep(min(30, max(0, end - time.monotonic())))


if __name__ == '__main__':
    raise SystemExit(main())
