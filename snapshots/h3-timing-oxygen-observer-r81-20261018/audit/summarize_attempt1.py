"""Describe frozen observer rejection stages; no threshold changes or new score."""
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from contract import require, sha

output = ROOT / 'audit/consumer_attempt1'
records = {}
for representation in ('original', 'visible'):
    folder = ROOT / 'results/attempt1' / representation
    summary = json.loads((folder / 'SUMMARY.json').read_text())
    require(summary['status'] == 'complete', 'complete scan required')
    rows = []
    for item in summary['steps']:
        path = folder / item['full_evidence']
        require(sha(path) == item['full_evidence_sha256'], 'full evidence changed')
        with gzip.open(path, 'rt') as stream:
            result = json.load(stream)
        observation, decision = result['observation'], result['decision']
        measurement_states, flags, comparisons = Counter(), Counter(), Counter()
        baseline = Counter(r['baseline'] for r in observation['windows'])
        low_gain = 0
        for row in observation['windows']:
            for confidence, measurement in row['measurements'].items():
                measurement_states[confidence + ':' + measurement['status']] += 1
                for flag in measurement.get('flags', []):
                    flags[confidence + ':' + flag] += 1
            for confidence, comparison in row.get('comparison', {}).items():
                comparisons[confidence + ':' + comparison['status']] += 1
            if row.get('status') == 'measured' and row.get('min_gain', 0) <= .5:
                low_gain += 1
        rows.append(dict(index=item['index'], observer_status=observation['status'],
                         observation_reasons=observation.get('reasons', []), total_window_descriptor_rows=len(observation['windows']),
                         baseline_counts=dict(baseline), measurement_states=dict(measurement_states),
                         rejection_flags=dict(flags), common_support_states=dict(comparisons),
                         low_gain_rows=low_gain, candidate_groups=len(decision['groups']),
                         active=decision['active'], decision_reason=decision['reason'],
                         selected=decision['selected'], physical_intervals=decision['physical_intervals']))
    records[representation] = rows
    with (output / (representation + '_stages.csv')).open('w') as stream:
        fields = ['index', 'observer_status', 'total_window_descriptor_rows', 'unknown', 'aligned', 'delayed_candidate',
                  'advanced_candidate', 'low_gain_rows', 'candidate_groups', 'active', 'decision_reason', 'physical_intervals']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            values = {k: row[k] for k in fields if k in row}
            values.update({k: row['baseline_counts'].get(k, 0) for k in ('unknown', 'aligned', 'delayed_candidate', 'advanced_candidate')})
            values['physical_intervals'] = json.dumps(values['physical_intervals'])
            writer.writerow(values)

(output / 'REJECTION_STAGE_DIAGNOSIS.json').write_text(json.dumps({
    'schema': 'r81-descriptive-rejection-stages-v1', 'fixed_case_denominator': 1,
    'observations_per_representation': 20, 'measurements_are_overlapping_window_descriptor_rows_not_independent_samples': True,
    'stage_counts_are_diagnostic_not_new_metrics': True, 'records': records}, indent=2) + '\n')
print(json.dumps({name: {'ON_indices': [x['index'] for x in rows if x['active']],
                        'first_candidate': next((x['index'] for x in rows if x['candidate_groups']), None)}
                  for name, rows in records.items()}))
