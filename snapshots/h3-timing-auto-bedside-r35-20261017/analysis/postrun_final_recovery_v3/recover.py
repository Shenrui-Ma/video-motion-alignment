"""Complete only the missing R35 final artifacts under pinned evidence."""
import argparse, hashlib, json, os, random, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'postrun'
sys.path.insert(0, str(OLD))
import remote_consume as rc
import evaluate as ev
from contract import read, require, save, sha, safe, output_file

def check_seals():
    p = read(HERE / 'PROTOCOL.json')
    require(p['authorized_by_root_message'] is True, 'recovery not authorized')
    for rel, digest in read(HERE / 'FREEZE.json')['files'].items():
        require(sha(HERE / rel) == digest, 'recovery source changed: ' + rel)
    require(sha(OLD / 'FREEZE.json') == p['old_freeze_sha256'], 'original freeze changed')
    require(sha(OLD / 'BINDING.json') == p['old_binding_sha256'], 'original binding changed')
    require(sha(HERE / 'PARTIAL_INVENTORY.json') == p['partial_inventory_sha256'], 'partial binding changed')
    rc.verify_consumer_seal()
    return p

def check_partial(dest, rows, exact=False):
    expected = {r['relative'] for r in rows}
    require(len(expected) == len(rows) == 32, 'partial inventory identity/count')
    for r in rows:
        f = safe(dest, r['relative'])
        require(f.is_file() and f.stat().st_size == r['bytes'] and sha(f) == r['sha256'], 'successful partial changed: ' + r['relative'])
    if exact:
        require({str(f.relative_to(dest)) for f in dest.rglob('*') if f.is_file()} == expected, 'unexpected partial output; explicit recovery required')

def blind_videos(videos, pair):
    require(sorted(pair) == ['auto', 'fixed_full'], 'unexpected blind arms')
    return {label: videos['AUTO' if name == 'auto' else name] for label, name in zip(('A', 'B'), pair)}

def pending(p):
    for root in p['online_priority_extra']:
        for d in (Path(root) / 'audit/observations').glob('step*'):
            if all((d / n).exists() for n in ('request.json', 'native.json')) and not any((d / n).exists() for n in ('pose_complete.json', 'response.json')):
                return True
    return False

def recover():
    started = time.monotonic()
    p = check_seals()
    if pending(p):
        raise BlockingIOError('R40 online observer has priority')
    with rc.locked():
        if pending(p):
            raise BlockingIOError('R40 online observer has priority')
        run = p['run']; arc, owner = rc.checked_archive(run, full=True)
        rc.verify_producer_sources(rc.ROOT, rc.P['producer_manifest_sha256'], all_files=True)
        require(not (arc / 'CPU_COMPLETE.json').exists(), 'already complete: do not duplicate recovery')
        require(not (HERE / 'RECOVERY_FAILED.json').exists(), 'uncertain recovery requires review')
        for i in range(20):
            rc.validate_replay(read(arc / 'observer_replay' / f'{i:03d}.json'), rc.replay_binding(arc, rc.ROOT, run, i))
        dest = arc / 'final'; rows = read(HERE / 'PARTIAL_INVENTORY.json')['files']
        require(read(HERE / 'PARTIAL_INVENTORY.json')['root'] == str(dest), 'partial root differs')
        check_partial(dest, rows, exact=True)
        case = rc.case_for(run)
        for path, digest in rc.P['frozen_external'].items():
            require(sha(path) == digest, 'frozen external dependency changed')
        source = arc / 'configs/source.pose.json'
        require(sha(source) == rc.P['source_pose_sha256'], 'source pose changed')
        video = output_file(arc, read(arc / 'logs' / f'{run}_history.json'), run)
        source_video = arc / 'input' / read(arc / 'configs' / f'{run}.json')['22']['inputs']['file']
        require(sha(source_video) == read(source)['video']['sha256'], 'source video binding')
        pose = dest / 'pose' / (video.stem + '.pose.json')
        require(read(pose)['video']['sha256'] == sha(video), 'successful pose video binding')
        videos = {'SOURCE': source_video}; parents = []
        for name in case['comparators']:
            parent = rc.P['parents'][name]; pp = OLD / parent['pose']
            require(sha(pp) == parent['pose_sha256'] and sha(parent['video']) == parent['video_sha256'] and read(pp)['video']['sha256'] == parent['video_sha256'], 'parent binding')
            parents.append(read(pp)['provenance']); videos[name] = Path(parent['video'])
        videos['AUTO'] = video
        provenance = ev.check_provenance(read(source)['provenance'], read(pose)['provenance'], parents, sha(source_video))
        fixed = read(dest / 'FIXED_WINDOWS.json')
        require(fixed['windows'] == case['windows'] and set(fixed['results']) == {'native', 'fixed_full', 'auto'}, 'fixed result identities')
        scans = read(dest / 'WHOLE_SCAN_SUMMARY.json')['results']
        require(set(scans) == {'native', 'fixed_full', 'auto'}, 'scan identities')
        common = {}
        for label in ('native__fixed_full__auto', 'fixed_full__auto'):
            common[label] = {}
            for c in rc.P['thresholds']:
                record = read(dest / f'COMMON_{label}_{c}.json')
                common[label][str(c)] = {'status': record['status'], 'rows': len(record['rows'])}
        pair = ['fixed_full', 'auto']; random.Random(rc.P['blind_media_seed']).shuffle(pair)
        ev.media_and_pixels(blind_videos(videos, pair), dest / 'blind_media', rc.P['fixed_visual_frames'], rc.P['fixed_clip_inclusive'])
        save(dest / 'BLIND_KEY.json', {'seed': rc.P['blind_media_seed'], 'mapping': dict(zip(('A', 'B'), pair)), 'scope': 'read only after blind visual judgement'})
        pixels = read(dest / 'media/PIXELS_AND_MEDIA.json'); ledger = read(arc / 'DECISION_LEDGER.json')
        off = not ledger['active_indices']; equal = pixels['RGB_frame_sha256']['AUTO'] == pixels['RGB_frame_sha256'][case['comparators'][0]]
        if off:
            require(equal, 'original all-OFF RGB gate failed')
        audit = read(arc / 'audit/counterfactual' / f'{run}.json')['counterfactual']
        job = read(arc / 'logs' / f'{run}_job.json'); capture = read(arc / 'audit/x0' / run / 'manifest.json')
        efficiency = {'job_wall_seconds': job['observed_unix'] - job['submitted_unix'], 'actual_NFE': ledger['NFE'], 'actual_Euler_updates': 20, 'current_Native_observations': 20, 'Full_branches': len(ledger['active_indices']), 'observer_wall_seconds': sum(x['wall_seconds'] for x in audit['measurements']), 'branch_model_seconds_synchronized': sum(x['model_seconds_synchronized'] for x in audit['branches']), 'branch_condition_copy_hash_seconds': sum(x['condition_copy_hash_seconds'] for x in audit['branches']), 'chosen20_capture_seconds': sum(x['capture_seconds'] for x in capture['captures']), 'interpretation': 'recorded scopes can overlap; not an efficiency optimization study or a sum-total decomposition'}
        save(dest / 'EFFICIENCY.json', efficiency)
        summary = {'video': str(video), 'video_sha256': sha(video), 'pose': str(pose), 'pose_sha256': sha(pose), 'source_pose_sha256': sha(source), 'pose_provenance': provenance, 'fixed_windows_scope': case['window_scope'], 'whole_scan': scans, 'common_support': common, 'NFE': ledger['NFE'], 'active_indices': ledger['active_indices'], 'ON_episodes': ledger['ON_episodes_inclusive'], 'restart_count': ledger['restart_count'], 'normal_any_intervention': case['seed'] == 2026101313 and not off, 'all_OFF_141RGB_equal': equal if off else None, 'all_OFF_final_AV': 'independently checked by verify_single' if off else 'N/A after first intervention', 'CPU_seconds': None, 'CPU_seconds_scope': 'original total final phase failed before timing commit; successful pose log retained; no pose/metric recomputation', 'recovery_seconds': time.monotonic() - started, 'efficiency': efficiency, 'manual_quality_review': 'pending fixed frames/fullvideo inspection; pose alone not identity/shape success', 'scope': 'development cases, no generalization or architecture novelty claim', 'recovery': {'protocol_sha256': sha(HERE / 'PROTOCOL.json'), 'freeze_sha256': sha(HERE / 'FREEZE.json'), 'partial_inventory_sha256': sha(HERE / 'PARTIAL_INVENTORY.json'), 'original_failure_retained': True, 'successful_partial_files_reused': 32, 'pose_or_metric_recomputed': False, 'repair': 'blind auto dictionary lookup uses AUTO'}}
        save(dest / 'FINAL_SUMMARY.json', summary)
        check_partial(dest, rows)
        rc.verify_source_archive(rc.ROOT, arc, owner, run)
        rc.verify_producer_sources(rc.ROOT, rc.P['producer_manifest_sha256'], all_files=True)
        check_seals()
        summary.update(passed=True, run_id=run, owner=owner, no_GPU=True, cleanup_claim=False, observer_replay_indices=list(range(20)))
        summary['derived_outputs'] = sorted(str(f.relative_to(arc)) for f in dest.rglob('*') if f.is_file())
        save(arc / 'CPU_COMPLETE.json', summary)
        original = read(arc / 'FILE_INVENTORY.json')
        generated = {str(f.relative_to(arc)): sha(f) for f in arc.rglob('*') if f.is_file() and str(f.relative_to(arc)) not in original and f.name not in ('DERIVED_FILES.json', 'ADMIN_RELEASE_ACCEPTANCE.json')}
        save(arc / 'DERIVED_FILES.json', generated)
        rc.validate_complete_inventory(arc)
        receipt = {'completion_sha256': sha(arc / 'CPU_COMPLETE.json'), 'derived_inventory_sha256': sha(arc / 'DERIVED_FILES.json'), 'original_inventory_sha256': sha(arc / 'FILE_INVENTORY.json')}
        save(OLD / 'final_receipts' / f'{run}.json', receipt)
        save(HERE / 'RECOVERY_COMPLETE.json', receipt | {'recovery_seconds': time.monotonic() - started, 'no_pose_or_metric_recomputation': True, 'partial_files_retained': 32})
        return receipt

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--execute', action='store_true'); args = parser.parse_args()
    if not args.execute:
        print('Prepared only; explicit --execute required.'); raise SystemExit(0)
    try:
        print(json.dumps({'status': 'complete', 'receipt': recover()}))
    except BlockingIOError:
        print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY'); raise SystemExit(75)
    except Exception as exc:
        save(HERE / 'RECOVERY_FAILED.json', {'error': repr(exc), 'automatic_retry': False, 'time': time.time()}); raise
