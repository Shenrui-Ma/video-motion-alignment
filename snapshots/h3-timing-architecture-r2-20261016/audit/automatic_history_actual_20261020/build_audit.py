"""Read historical immutable files; emit compact controller history evidence."""
from pathlib import Path
import hashlib
import json

BASE = Path('/Users/researcher/DevProjects')
OUT = Path(__file__).parent
R27 = BASE / 'h3-timing-auto-controller-r27-20261017'
R35 = BASE / 'h3-timing-auto-bedside-r35-20261017'

def read(p):
    return json.loads(p.read_text())

def evidence(p):
    return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}

def extract(root, relative, run):
    folder = root / relative / run
    logpath = folder / 'audit/counterfactual' / (run + '.json')
    log = read(logpath)
    cf = log['counterfactual']
    summary = read(folder / 'final/FINAL_SUMMARY.json')
    complete = read(folder / 'CPU_COMPLETE.json')
    timeline = []
    for step, measurement in zip(cf['steps'], cf['measurements']):
        d = step['decision']
        assert step['physical_index'] == measurement['physical_index'] == d['index']
        timeline.append({
            'index': step['physical_index'], 'ON': d['chosen_full'],
            'selected_branch': step['selected_branch'], 'reason': d['reason'],
            'measurement_status': d['measurement_status'],
            'qualifying_representatives': [g['representative'] for g in d['groups']],
            'selected_representatives': d['selected'],
            'physical_intervals': d['physical_intervals'], 'latent_bins': d['latent_bins'],
            'nfe_indices': step['nfe_indices'],
            'request_sha256': d['request_sha256'], 'response_sha256': d['response_sha256'],
            'observer_wall_seconds': measurement['wall_seconds'],
        })
    assert [x['index'] for x in timeline] == list(range(20))
    assert [x['index'] for x in timeline if x['ON']] == summary['active_indices']
    video = folder / 'output' / Path(summary['video']).name
    assert evidence(video)['sha256'] == summary['video_sha256']
    return {
        'run_id': run, 'root': str(root),
        'evidence': {k: evidence(p) for k, p in {
            'actual_counterfactual': logpath, 'run_gate': folder / 'RUN_GATE.json',
            'runtime_gate': folder / 'RUNTIME_GATE.json', 'cpu_complete': folder / 'CPU_COMPLETE.json',
            'final_summary': folder / 'final/FINAL_SUMMARY.json', 'output_mp4': video,
            'protocol': root / 'configs/protocol.json',
        }.items()},
        'runtime_gate_passed': read(folder / 'RUN_GATE.json')['passed'],
        'cpu_complete_passed': complete['passed'],
        'observer_replay_indices': complete['observer_replay_indices'],
        'original_run_gate_note': 'RUN_GATE predates CPU postprocessing; replay completion is bound separately to CPU_COMPLETE.',
        'actual_NFE': cf['actual_model_nfe'], 'actual_updates': cf['actual_euler_updates'],
        'observations': len(cf['measurements']), 'ON_indices': summary['active_indices'],
        'efficiency': summary['efficiency'], 'timeline': timeline,
    }, cf

bad, badcf = extract(R27, 'analysis/postrun_recovery_v2/captured', 'r27_s05_bad1311_auto')
bed, bedcf = extract(R35, 'analysis/postrun/captured', 'r35_s07_seed2026101311_auto')

def rows(cf, step, window):
    found = []
    for row in cf['measurements'][step]['observer']['windows']:
        if row['window'] != window:
            continue
        found.append({k: row.get(k) for k in ('window', 'feature', 'baseline', 'status', 'min_gain')} | {
            'diagnostics': {c: {k: d.get(k) for k in ('status', 'flags', 'reliable_lag_frames', 'same_frame', 'best')}
                            for c, d in row['measurements'].items()}})
    # Drop per-frame curves from the compact evidence; exact raw log is hashed above.
    for row in found:
        for d in row['diagnostics'].values():
            for k in ('same_frame', 'best'):
                if d[k]:
                    d[k] = {q: d[k].get(q) for q in ('lag_frames', 'error', 'coverage', 'valid_frame_count')}
    return found

bad['stop_evidence'] = {
    'index': 5, 'previous_active_index': 4,
    'previous_window_at_active_step': rows(badcf, 4, [44, 59]),
    'previous_window_at_stop_step': rows(badcf, 5, [44, 59]),
    'interpretation': 'Selected left-arm window reports lag +4 at confidence .3; confidence .5 is UNKNOWN from detection coverage. No qualifying delayed representative survives the full scan. Stopping does not certify alignment.',
}
bed['stop_evidence'] = {
    'index': 11, 'previous_active_index': 10,
    'previous_window_at_active_step': rows(bedcf, 10, [60, 75]),
    'previous_window_at_stop_step': rows(bedcf, 11, [60, 75]),
    'interpretation': 'Selected right-arm window reports lags +16 and -2 at confidence .3/.5. Their 18-frame discrepancy fails the <=2-frame agreement condition. No qualifying delayed representative survives the full scan. Stopping does not certify alignment.',
}
bad['final_result'] = {
    'evaluation_window': [50, 65], 'positive_lag_means': 'edited motion later',
    'arm_direction_lag_conf03_conf05': {'native': [13, 13], 'fixed6_14': [1, 1], 'auto': [2, 2]},
    'wrist_lag_conf03_conf05': {'native': [13, 12], 'fixed6_14': [1, 1], 'auto': [2, 1]},
    'four_evaluation_windows': [[50, 65], [69, 81], [80, 92], [99, 111]],
    'arm_lag_conf03_four_windows': {'native': [13, 10, 8, 4], 'auto': [2, 0, 1, 0]},
    'visual_evidence_scope': 'Archived fixed frames 55/86/105 preserve gross room layout and gray-top male edit; hands are blurred. Exact identity and full-video temporal artifacts were not fully assessed.',
    'official_MF': None,
    'official_MF_status': 'No official MF/CoTracker artifact found in this producer tree or independent result reports; reported numbers are pose lag/error.',
    'independent_result': evidence(R27 / 'analysis/priority_final_outcome/PRIORITY_REVIEW.txt'),
    'quality_scope': 'known development source/seed; automatic-selected window 44-59 differs from predeclared evaluation window 50-65',
}
bed['final_result'] = {
    'evaluation_window': [54, 69], 'positive_lag_means': 'edited motion later',
    'arm_direction_lag_conf03': {'native': 15, 'fixed6_14': -1, 'auto': -1},
    'arm_direction_lag_conf05': {'native': None, 'fixed6_14': -1, 'auto': -1},
    'native_right_arm_lag_conf05': 15,
    'evaluation_windows': [[54, 69], [75, 88], [98, 111]],
    'arm_lag_conf03_windows': {'native': [15, None, -5], 'fixed6_14': [-1, -2, -4], 'auto': [-1, -3, -5]},
    'visual_evidence_scope': 'Archived blind fixed frames 60/63/81/105 preserve bedroom and gray-top/dark-trouser male edit in Auto and Fixed. Hands/forearms blurred; no clear pair quality preference. Exact identity/full flicker/ghosting not fully assessed.',
    'official_MF': None,
    'official_MF_status': 'No official MF/CoTracker artifact found in this producer tree or independent result reports; reported numbers are pose lag/error.',
    'independent_result': evidence(R35 / 'analysis/postrun/independent_review/FINAL_REVIEW.txt'),
    'compact_numeric_result': evidence(R35 / 'analysis/postrun/independent_review/COMPACT_RESULTS.json'),
    'quality_scope': 'related-choreography development source; later advances remain; thresholds inherited unchanged from R27',
}

files = ['scripts/automatic_window_policy.py', 'scripts/scan_current_pose.py', 'scripts/pairwise_gain.py',
         'scripts/timing_metrics.py', 'extensions/H3AutomaticWindowRouter/core.py',
         'extensions/H3AutomaticWindowRouter/selector.py', 'extensions/H3AutomaticWindowRouter/dynamic_support.py',
         'extensions/H3TemporalRouter/core.py']
code = []
for f in files:
    assert (R27 / f).read_bytes() == (R35 / f).read_bytes()
    code.append({'relative_path': f, 'R27': evidence(R27 / f), 'R35': evidence(R35 / f), 'byte_identical': True})

normal_folder = R27 / 'analysis/postrun_normal_final_v3/captured/r27_s05_normal1313_auto'
normal = read(normal_folder / 'final/FINAL_SUMMARY.json')
r55 = BASE / 'h3-timing-ivebench-auto-r55-20261017'
later = [evidence(p) | {'gate': read(p)} for p in sorted(r55.glob('analysis/postrun/completed_cases/*/CASE_RUNTIME_GATE.json'))]
r86 = BASE / 'h3-oxygen-online-metrics-r86-20261018/results/SUMMARY.json'
r50 = BASE / 'h3-timing-flexiact-auto-r50-retry-20261017/analysis/postrun/completed_cases/r50_source_chest_seed2026101701_auto/CASE_RUNTIME_GATE.json'

result = {
    'schema': 'historical-actual-automatic-control-audit-v1', 'created_date': '2026-10-20',
    'operation': 'CPU read-only audit of existing code/logs/videos; no new inference or scientific changes',
    'implementation_identical_R27_R35': code,
    'method': {
        'trained_components': 'H3 and frozen pose estimator; no additional training',
        'runtime_flow': 'For each Euler index 0..19: current-state Native prediction -> decode predicted clean video -> CPU pose scan -> policy -> optional guided forward at the same state -> one Euler update.',
        'manual_action_window': False, 'per_case_manual_start_detection_step': False,
        'fixed_global_detection_schedule': list(range(20)), 'earliest_possible_ON_index': 1,
        'scan': {'lengths_frames': [16, 32], 'stride_frames': 4, 'last_complete_window_included': True,
                 'descriptors': ['both-arm unit directions', 'left-arm unit directions', 'right-arm unit directions'],
                 'confidence_cuts': [.3, .5], 'lag_search_frames': [-24, 24], 'fps': 24},
        'lag_cost_formula': 'C_c(W,l)=sum_f,j w_fj ||d_source(f,j)-d_pred(f+l,j)||_2 / sum_f,j w_fj, with minimum source/pred joint confidence on finite support',
        'lag_validity': {'coverage_min': .8, 'valid_frames_min': 8, 'boundary_lag_rejected': True,
                         'runner_up_separation_frames': 4, 'relative_runner_up_gap_min': .05,
                         'relative_improvement_vs_same_frame_for_nonzero_lag_min': .05,
                         'shifted_unit_direction_residual_max': .5,
                         'two_confidence_lag_difference_max_frames': 2, 'delay_min_strict_frames': 2},
        'gain_formula': 'g=min_(c in {.3,.5}, e in {-2,-1,0,1,2}) (C_c(W,e)-C_c(W,l_c))/max(C_c(W,e),1e-8), each comparison evaluated on its common valid support',
        'gain_min_strict': .5,
        'group_selection': 'Merge overlapping eligible intervals; choose each component representative maximizing min_(c,e)(C_null-C_proposal). Ties: shorter window, earlier start, feature name.',
        'persistence': 'Current representative shares an arm with the immediately preceding representative and intersection_length/min(lengths)>=.5.',
        'number_of_windows': 'Number of disjoint qualifying persistent groups; no fixed quota.',
        'stop_rule': 'Recompute every step; no persistent qualifying delay -> Native. No separate stop threshold or minimum duration. Empty/UNKNOWN scans clear previous representatives.',
        'UNKNOWN': 'Skip feedback this step, clear prior candidate evidence; subsequent ON again needs consecutive evidence. Technical execution errors abort.',
        'threshold_origin': 'Frozen exploratory engineering constants; no learned or statistically calibrated threshold is evidenced.',
        'attention_formula': 'O_prime(q)=O(q)+g_window(q)*alpha*m_ref(q)*(O_ref_same_time(q)-O_ref_all_time(q)); alpha=1',
        'attention_scope': 'All 50 DiT blocks; selected video-time bins, all spatial query rows; original reference mass retained, same-time reference subset normalized within subset; no body-part spatial mask.',
        'NFE': '20 + number of ON steps; 20 Euler updates',
    },
    'runs': {'R27_bad': bad, 'R35_bedside': bed},
    'normal_seed_control_R27': {
        'summary': evidence(normal_folder / 'final/FINAL_SUMMARY.json'), 'NFE': normal['NFE'],
        'ON_indices': normal['active_indices'], 'all_OFF_final_AV': normal['all_OFF_final_AV'],
        'all_OFF_141RGB_equal': normal['all_OFF_141RGB_equal'],
    },
    'later_versions': {
        'R50': {'completed_chest_gate': evidence(r50), 'gate': read(r50),
                'summary': 'Only chest completed: 20 observations, zero ON. Failed crouch had ON indices7..13 and no final MP4. Planned five is not five completed.',
                'retry2_state': evidence(BASE / 'h3-timing-flexiact-auto-r50-retry2-20261017/audit/recovery/COMPLETE.json')},
        'R55': {'case_gates': later, 'summary': 'Five completed IVE cases, each20 observations and zero ON; extends policy to delay/advance but retains global torso validity requirement.'},
        'R86': {'state': evidence(r86), 'summary': read(r86), 'difference': 'Visible upper/lower-arm descriptors remove mandatory hip visibility; case-specific adult bbox selector retained. Candidate implementation; generation/GPU validation pending in actual record.'},
        'fixed6_14_current': 'Current R121 directly applies the same mass-preserving time-reference operator on steps6..14 in the existing forward; no online observer and20NFE.',
    },
}
(OUT / 'EVIDENCE.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
print(json.dumps({'output': evidence(OUT / 'EVIDENCE.json'), 'runs': {k: {'ON': v['ON_indices'], 'NFE': v['actual_NFE']} for k,v in result['runs'].items()}}, ensure_ascii=False))
