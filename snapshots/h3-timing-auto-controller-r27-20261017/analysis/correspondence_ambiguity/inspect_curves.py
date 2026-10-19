"""Descriptive inspection of frozen lag curves; never drives inference."""
import collections
import fcntl
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def action(lag):
    return 'delay' if lag > 2 else 'advance' if lag < -2 else 'within_tolerance'


def inspect(measurement):
    flags = set(measurement.get('flags', []))
    qualified = [r for r in measurement['curve']
                 if r['error'] is not None and r['coverage'] >= .8
                 and r['valid_frame_count'] >= 8]
    if not qualified:
        return {'sole_ambiguity': False, 'reason': 'no_qualified_lags'}
    best = min(r['error'] for r in qualified)
    near = [r['lag_frames'] for r in qualified
            if (r['error'] - best) / max(best, 1e-8) < .05]
    return {'sole_ambiguity': flags == {'flat_or_multiple_matching_phases'},
            'flags': sorted(flags), 'status': measurement['status'],
            'lags': near, 'actions': sorted({action(d) for d in near}),
            'original_reliable_lag': measurement['reliable_lag_frames']}


def main():
    protocol = json.loads((HERE / 'PROTOCOL.json').read_text())
    lockpath = '/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock'
    with open(lockpath, 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('CPU_LOCK_BUSY')
            return
        paths = sorted(Path(protocol['input_root']).glob('step*/observer.json'))
        assert len(paths) == 20
        records, hashes, indices = [], {}, []
        for path in paths:
            raw = path.read_bytes()
            hashes[str(path)] = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            assert data['status'] == 'measured' and len(data['windows']) == 186
            indices.append(data['physical_index'])
            for row in data['windows']:
                measured = {c: inspect(row['measurements'][c])
                            for c in protocol['confidence_thresholds']}
                eligible = all(m['sole_ambiguity'] for m in measured.values())
                classes = set().union(*(set(m.get('actions', [])) for m in measured.values()))
                records.append({'denoising_index': data['physical_index'],
                                'window': row['window'], 'feature': row['feature'],
                                'original_status': row['status'], 'measurements': measured,
                                'both_sole_ambiguity': eligible,
                                'both_delay_only': eligible and classes == {'delay'}})
        assert sorted(indices) == list(range(20))
        summaries = []
        for index in range(20):
            rows = [r for r in records if r['denoising_index'] == index]
            summaries.append({'denoising_index': index, 'rows': len(rows),
                              'statuses': dict(collections.Counter(r['original_status'] for r in rows)),
                              'both_sole_ambiguity': sum(r['both_sole_ambiguity'] for r in rows),
                              'both_delay_only': sum(r['both_delay_only'] for r in rows)})
        result = {'scope': 'one development trajectory, correlated windows',
                  'protocol_sha256': hashlib.sha256((HERE / 'PROTOCOL.json').read_bytes()).hexdigest(),
                  'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'input_sha256': hashes, 'summaries': summaries, 'records': records}
        (HERE / 'RESULT.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        compact = {'summary': summaries,
                   'both_sole_ambiguity_total': sum(r['both_sole_ambiguity'] for r in records),
                   'both_delay_only_total': sum(r['both_delay_only'] for r in records)}
        (HERE / 'SUMMARY.json').write_text(json.dumps(compact, indent=2) + '\n')
        print(json.dumps(compact))


if __name__ == '__main__':
    main()
