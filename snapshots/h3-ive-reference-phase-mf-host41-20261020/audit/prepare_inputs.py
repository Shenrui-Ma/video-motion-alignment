"""Bind new actual media; reuse the already verified official MF runtime unchanged."""
from pathlib import Path
import hashlib, json, os, subprocess, sys, time

B = Path('/Users/researcher/DevProjects')
R = Path(__file__).resolve().parents[1]
BASE = B / 'h3-ive-bird-aligned-mf-host41-20261020'
R126 = B / 'h3-ive-handkerchief-full-context-metrics-r126-20261020'
R131 = B / 'h3-ive-prompt-envelope-metrics-r123-20261020/variants/short0177_full_context'
R132 = B / 'h3-ive-reference-origin-metrics-r132-20261020'
sys.path.insert(0, str(BASE / 'runtime/ive/metric_runtime'))
from ive_mf_adapter import frame_hashes, media_info, validate_time_view

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def bound(p): return {'file': str(p), 'sha256': sha(p)}
def save(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
def link(p, q):
    q.parent.mkdir(parents=True, exist_ok=True)
    if not q.exists(): os.link(p, q)
    assert sha(p) == sha(q)
def check(b):
    p = Path(b['file']); assert sha(p) == b['sha256']; return p

def target(case, role, raw, n, inventory_id, mp, gate, gate_role):
    g = read(gate)
    exploratory = role == 'reference_origin'
    if exploratory:
        assert mp == R132/'prepared_exploratory/MF_INPUTS.json'
        m=read(mp)
        assert m['input_pairing']=='historical_cross_host_pixel_mismatch' and m['exploratory'] is True
        assert m['strict_gate_pass'] is False and m['paired_input_exact'] is False
        assert g['producer_seal_sha256']=='88ea3c9b4f874c6d97558bdeb8bd2d932351f69fe5217b3dbe4a131e655d1209'
        assert sha(gate)=='c2dd56cf370904f5a0f1aa9fecd772b4b8a6eb944ebaf6788ebea6c6dd6abc26'
        assert g['passed'] is False and [k for k,v in g['checks'].items() if v is not True]==['original_input_pixels_tokens_positions_equal_R122']
        release=read(check(m['actual_release']))
        assert release['passed'] and release['process_absent'] and release['CUDA_allocation_absent']
        assert read(check(m['collection']))['media_integrity_passed']
    else:
        assert g['passed'] and all(g['checks'].values())
    full = check(raw); assert g['runs'][gate_role]['video']['sha256'] == raw['sha256']
    folder = case / role; link(full, folder / 'full.mp4')
    score = folder / 'score.mp4'; crop = f'crop=1280:720:16:8,trim=end_frame={n},setsar=1'
    if not score.exists():
        subprocess.run(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '2', '-i', str(full),
            '-an', '-vf', crop, '-vsync', '0', '-c:v', 'libx264', '-qp', '0', '-preset', 'fast',
            '-pix_fmt', 'yuv420p', '-threads', '2', str(score)], check=True)
    hashes = frame_hashes(score, '/opt/homebrew/bin/ffmpeg')
    assert hashes == frame_hashes(full, '/opt/homebrew/bin/ffmpeg', crop)
    validate_time_view(media_info(score, '/opt/homebrew/bin/ffprobe'), n)
    return dict(role=role, full_file=role+'/full.mp4', full_sha256=raw['sha256'],
        score_file=role+'/score.mp4', score_sha256=sha(score), score_frame_md5=hashes,
        inventory_bindings=[{'id': inventory_id, 'field': role}], actual_consumer_input=bound(mp),
        actual_runtime_gate=bound(gate), evaluation_indices=list(range(n)),
        input_pairing='historical_cross_host_pixel_mismatch' if exploratory else 'actual_paired_gate',
        strict_gate_pass=not exploratory, exploratory=exploratory)

def cached_source(case, cache_manifest, report, tracks, current_source, n):
    old = check(cache_manifest); m = read(old)
    assert m['source_full_sha256'] == current_source['sha256'] == sha(check(current_source))
    assert m['valid_frames'] == n and m['evaluation_fps'] == 24 and m['crop_xywh'] == [16,8,1280,720]
    for name in ('source_full.mp4', 'source_score.mp4'): link(old.parent/name, case/name)
    rp = check(report); tr = check(tracks); v = read(rp)
    assert v['passed'] and v['effective_frame_count'] == n
    assert v['official_commit'] == '2dcf8900ee65197f43854c76f61c66a32bb8dbfc'
    assert v['checkpoint_sha256'] == 'da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
    assert v['tracks_sha256'] == sha(tr) and v['decoded_frame_md5'] == m['source_frame_md5']
    assert v['source_score_sha256'] == m['source_score_sha256'] and v['source_prepared_sha256'] == m['source_full_sha256']
    assert v['selection_sha256'] == m['selection_sha256']
    link(rp, case/'tracks/source/REPORT.json'); link(tr, case/'tracks/source/tracks.npz')
    assert frame_hashes(case/'source_score.mp4', '/opt/homebrew/bin/ffmpeg') == m['source_frame_md5']
    result = {k:m[k] for k in ('schema','benchmark','canonical_id','valid_frames','evaluation_frames',
        'evaluation_fps','crop_xywh','source_full_sha256','source_score_sha256','source_frame_md5','selection_sha256')}
    result['source_cache'] = {'report_sha256': sha(rp), 'tracks_sha256': sha(tr)}
    return result

def main():
    assert not (R/'SEAL.json').exists()
    # Wait for actual output bindings; never create placeholders as scored results.
    required = [R126/'prepared/long_0059/paired/MF_INPUTS.json', R132/'prepared_exploratory/MF_INPUTS.json']
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        save(R/'audit/PENDING.json', {'status':'WAITING_FOR_ACTUAL_MEDIA', 'missing':missing, 'GPU_started':False})
        print(json.dumps({'status':'WAITING_FOR_ACTUAL_MEDIA','missing':missing})); return
    for p in (BASE/'scripts').glob('*.py'): link(p, R/'scripts'/p.name)
    if not (R/'runtime').exists(): (R/'runtime').symlink_to(BASE/'runtime', target_is_directory=True)
    for name in ['EXISTING_SERVICES.json','ive_NUMERIC.json']: link(BASE/'configs'/name,R/'configs'/name)
    for name in ['final_release.py','verify_inputs.py','collect.py']: link(BASE/'audit'/name,R/'audit'/name)
    runtime = read(BASE/'configs/RUNTIME.json')
    runtime.update(remote_root='/data4/researcher/h3_runs/ive_reference_phase_mf_20261020',
        peer_roots=['/data4/researcher/h3_runs/timing_ive_reference_origin_r132_20261020'])
    save(R/'configs/RUNTIME.json',runtime)
    inputs = {}; jobs = []
    # R131 was independently pixel/PTS prepared after actual Native completion.
    src = R131/'audit/mf_cpu_prepared/short_0177'; case = R/'cases/short_0177'
    old = read(src/'INPUTS.json'); assert old['valid_frames']==60 and old['source_cache'] is None
    for p in src.rglob('*'):
        if p.is_file(): link(p,case/p.relative_to(src))
    inputs['short_0177']=bound(case/'INPUTS.json')
    jobs += [{'case':'short_0177','role':'source'},{'case':'short_0177','role':'native'}]
    # R126 keeps the exact old source track and original selection binding.
    mp=required[0]; m=read(mp); case=R/'cases/long_0059'; cache=read(R126/'audit/SOURCE_CACHE_READY.json')
    assert cache['passed'] and m['valid_frames']==144 and m['evaluation_indices']==list(range(144))
    manifest=cached_source(case,cache['prior_source_inputs'],cache['source_track_report'],cache['source_tracks'],m['raw_videos']['source'],144)
    gate=R126/'incoming_pairs/long_0059/PAIR_RUNTIME_GATE.json'
    manifest['targets']=[target(case,role,m['raw_videos'][original],144,'r126_long_0059_full_context',mp,gate,original)
        for original,role in [('native','native'),('forced','guided')]]
    manifest['source_cache_domain_proof']=bound(R126/'audit/SOURCE_CACHE_READY.json')
    save(case/'INPUTS.json',manifest); inputs['long_0059']=bound(case/'INPUTS.json')
    jobs += [{'case':'long_0059','role':role}for role in ('native','guided')]
    for p in [mp,gate,R126/'incoming_pairs/long_0059/COLLECTION.json']:link(p,R/'configs/long_0059'/p.name)
    # R132 is a new reference_origin score, not a renaming of R129 aligned.
    mp=required[1]; m=read(mp); case=R/'cases/long_0039'; cache=read(R132/'audit/MF_CACHE_READY.json')
    assert cache['passed'] and m['valid_frames']==106 and m['evaluation_indices']==list(range(106))
    manifest=cached_source(case,cache['original_input_manifest'],cache['records']['source']['report'],cache['records']['source']['tracks'],m['full_videos']['source'],106)
    gate=R132/'incoming_exploratory/REFERENCE_ORIGIN_RUNTIME_GATE.json'
    manifest['targets']=[target(case,'reference_origin',m['full_videos']['reference_origin'],106,'r132_long_0039_reference_origin',mp,gate,'reference_origin')]
    manifest['historical_comparison_scores']={role:cache['records'][role]['score_record']for role in ('native','fixed')}
    manifest['source_cache_domain_proof']=bound(R132/'audit/MF_CACHE_READY.json')
    save(case/'INPUTS.json',manifest);inputs['long_0039']=bound(case/'INPUTS.json');jobs.append({'case':'long_0039','role':'reference_origin'})
    for p in [mp,gate,R132/'incoming_exploratory/COLLECTION.json',R132/'incoming_exploratory/ROOT_EXIT_RECEIPT.json',R132/'audit/full106_exploratory_review/REVIEW.json']:link(p,R/'configs/long_0039'/p.name)
    diagnosis=B/'h3-timing-ive-reference-origin-r132-20261020/audit/input_pixel_difference_cpu/SUMMARY.json'
    if diagnosis.exists():link(diagnosis,R/'configs/long_0039/INPUT_PIXEL_DIFFERENCE_SUMMARY.json')
    save(R/'configs/PLAN.json',dict(groups=list(inputs),jobs=jobs,unique_targets=4,source_cache_count=2,status='ACTUAL_FOUR_TARGETS_READY'))
    save(R/'audit/INPUTS_READY.json',dict(passed=True,inputs=inputs,generated_targets=4,serial_trackers=5,
        numerical_scripts_byte_identical=True,GPU_started=False,base_seal=bound(BASE/'SEAL.json'),created_unix=time.time()))
    print(json.dumps({'passed':True,'inputs':inputs,'trackers':5}))

if __name__=='__main__':main()
