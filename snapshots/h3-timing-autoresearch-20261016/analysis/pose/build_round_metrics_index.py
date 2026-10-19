"""Index exact admitted run metrics without changing or re-estimating endpoints."""
import datetime
import json
from pathlib import Path


RUNS = {
    's05_seed1_native': ('05', 'resolution-control native'),
    's05_seed1_mass': ('05', 'resolution-control routing'),
    's05_full_seed1_native_x0': ('05', 'discovery native'),
    's05_full_seed1_phase_zero_x0': ('05', 'exact-replay control'),
    's05_full_seed1_mass_x0': ('05', 'all-step same-bin mass route'),
    's05_full_seed1_hard_x0': ('05', 'all-step hard baseline'),
    's05_full_seed1_mass_late11_x0': ('05', 'late mass'),
    's05_full_seed1_mass_late6_x0': ('05', 'earlier-start mass'),
    's05_full_seed1_hard_late11_x0': ('05', 'late hard'),
    's05_full_seed1_phase_plus12_x0': ('05', 'relative coordinate +12'),
    's05_full_seed1_phase_minus12_x0': ('05', 'relative coordinate -12'),
    's05_full_seed1_offset4_x0': ('05', 'wrong reference bin +4'),
    's05_full_seed1_offsetm4_x0': ('05', 'wrong reference bin -4'),
    's05_full_seed1_phase_minus12_late11_x0': ('05', 'late relative coordinate -12'),
    's05_full_seed1_mass_6to14_x0': ('05', 'equal-nine-call mass6..14'),
    's05_full_seed2_native_x0': ('05', 'second seed native'),
    's05_full_seed2_mass_x0': ('05', 'second seed mass'),
    's07_full_seed1_native_x0': ('07', 'related recording native'),
    's07_full_seed1_mass_x0': ('07', 'related recording mass'),
    's05_semantic_b_p6_t6': ('05', 'semantic factorial B'),
    's05_semantic_c_p0_t6': ('05', 'semantic factorial C'),
    's05_semantic_d_p6_t0': ('05', 'semantic factorial D'),
}


def main():
    home = Path(__file__).resolve().parent
    report = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'Index only; per-run lag support differs and must not replace common-support comparisons. Replays/resolution changes are not independent cases.',
              'runs': {}}
    for run_id, (case, role) in RUNS.items():
        admission_file = home/'pilot'/f'{run_id}.history_provenance.json'
        record = {'case': case, 'role': role, 'status': 'not_archived_or_pending'}
        if admission_file.is_file():
            admission = json.loads(admission_file.read_text())
            stem = Path(admission['history_output']['filename']).stem
            record.update(status='admitted', prompt_id=admission['prompt_id'],
                          video=admission['history_output']['filename'],
                          measured_geometry={name: admission[name] for name in ('width', 'height', 'frames', 'fps')},
                          expected_geometry_from_config=admission.get('expected_geometry_from_config'),
                          config_sha256=admission.get('config_sha256'), thresholds={})
            for threshold in (.3, .5):
                path = home/'pilot'/f'{stem}.threshold{threshold}.timing.json'
                if not path.is_file():
                    record['thresholds'][str(threshold)] = {'status': 'not_archived_or_measurement_failure'}
                    continue
                measured = json.loads(path.read_text())
                record['mp4_sha256'] = measured['edited']['sha256']
                record['thresholds'][str(threshold)] = [{
                    'window': row['window'], 'feature': row['feature'],
                    'reliable_lag_frames': row.get('reliable_lag_frames'), 'status': row['status'],
                    'flags': row.get('flags', []), 'same_frame_error': row.get('same_frame', {}).get('error'),
                    'same_frame_coverage': row.get('same_frame', {}).get('coverage'),
                    'best_error': row.get('best', {}).get('error'), 'best_coverage': row.get('best', {}).get('coverage')}
                    for row in measured['diagnostics']]
        report['runs'][run_id] = record
    destination = home/'round_metrics_index.json'
    destination.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'saved': str(destination), 'admitted': sum(row['status']=='admitted' for row in report['runs'].values()), 'listed': len(RUNS)}))


if __name__ == '__main__':
    main()
