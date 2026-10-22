"""Isolate each target while reusing the byte-frozen physical evaluator.

The legacy evaluator accepts two targets and catches missing-torso errors around
both. Calling it with a single target in both slots isolates that target. Only
its first diagnostic slot is retained; the duplicate is never a second sample.
Common-support comparisons remain in the unchanged legacy paired result.
"""
import copy


def single_result(result):
    output = {key: copy.deepcopy(value) for key, value in result.items()
              if key not in ('confidence_results', 'paired_lag_summary')}
    output['confidence_results'] = {}
    for confidence, record in result['confidence_results'].items():
        output['confidence_results'][confidence] = {
            'status': record['status'],
            'rows': [{'window': row['window'], 'feature': row['feature'],
                      'diagnostic': row['diagnostics']['native']}
                     for row in record['rows']]}
    output['lag_summary'] = [
        dict(window=row['window'], feature=row['feature'], **row['methods']['native'])
        for row in result['paired_lag_summary']]
    return output


def independent_targets(evaluate, source, targets, *args):
    """No thresholds, sampling, confidence, numerical functions or input changes."""
    return {name: single_result(evaluate(source, target, target, *args))
            for name, target in targets.items()}
