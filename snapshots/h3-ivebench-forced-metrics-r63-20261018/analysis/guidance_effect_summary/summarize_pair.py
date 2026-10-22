"""Read existing router/job JSON; summarize sampled attention changes using stdlib."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def bound(path):
    path = Path(path)
    return {'file': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('attention statistic must be a finite number')
    return float(value)


def summarize(router, job=None):
    counts = router['routed_by_forward']
    if any(type(n) is not int or n < 0 for n in counts):
        raise ValueError('invalid routed call count')
    active = [i for i, n in enumerate(counts) if n > 0]
    actual = router['completed_forward_calls']
    if sum(counts) != router['routed_calls']:
        raise ValueError('routed aggregate and per-forward counts differ')
    rows = {}
    for row in router.get('forward_summaries', []):
        index = row['forward_index']
        if index in rows or type(index) is not int or not 0 <= index < len(counts):
            raise ValueError('duplicate or invalid forward summary')
        if row['routed_blocks'] != counts[index]:
            raise ValueError('forward summary routing count differs')
        rows[index] = row
    steps = []
    for index in active:
        row = rows.get(index, {})
        mass = row.get('sampled_ref_mass_mean')
        correction = row.get('sampled_correction_ratio_mean')
        steps.append({'zero_based_step': index, 'routed_attention_calls': counts[index],
                      'sampled_ref_mass_mean': None if mass is None else finite_number(mass),
                      'sampled_correction_ratio_mean': None if correction is None else finite_number(correction),
                      'sampled_finite': row.get('sampled_finite'),
                      'sampled_layer_count': len(row.get('layer_stats', []))})
    covered = [row for row in steps if row['sampled_ref_mass_mean'] is not None and
               row['sampled_correction_ratio_mean'] is not None]
    def aggregate(key):
        values = [row[key] for row in covered]
        return {'mean_of_active_step_means': sum(values)/len(values), 'min_step_mean': min(values),
                'max_step_mean': max(values)} if values else None
    changed = True if any(row['sampled_correction_ratio_mean'] > 0 for row in covered) else (
        False if len(covered) == len(active) else None)
    if not active:
        changed = False
    efficiency = {'completed_NFE': actual, 'expected_NFE': router.get('expected_sampling_steps'),
                  'is_20_NFE': actual == 20, 'job_wall_seconds': None,
                  'job_wall_seconds_per_NFE_including_loading': None}
    if job is not None:
        if job.get('name') != router['run_id']:
            raise ValueError('job belongs to a different router run')
        wall = finite_number(job['observed_unix']) - finite_number(job['submitted_unix'])
        if wall < 0:
            raise ValueError('negative job wall time')
        efficiency.update(job_status=job.get('status'), job_wall_seconds=wall,
                          job_wall_seconds_per_NFE_including_loading=wall/actual if actual else None)
    return {'run_id': router['run_id'], 'mode': router.get('mode'), 'alpha': router.get('alpha'),
            'actual_completed_forward_calls': actual,
            'counts_cover_completed_forwards': len(counts) == actual and len(rows) == actual,
            'intervention_executed': router['routed_calls'] > 0,
            'sampled_attention_output_changed': changed,
            'routed_attention_calls': router['routed_calls'], 'active_zero_based_steps': active,
            'matches_nine_steps_6_through_14': active == list(range(6,15)),
            'stats_covered_active_steps': len(covered), 'active_step_count': len(active),
            'sampled_stats_marked_finite': all(row['sampled_finite'] is True for row in covered) if covered else None,
            'sampled_ref_mass': aggregate('sampled_ref_mass_mean'),
            'sampled_correction_ratio': aggregate('sampled_correction_ratio_mean'),
            'per_active_step': steps, 'efficiency': efficiency,
            'producer_metric_scope': router.get('metric_scope'),
            'action_quality_assessment': '由实际视频与独立动作评测提供'}


def main():
    parser = argparse.ArgumentParser()
    for method in ['native', 'forced']:
        parser.add_argument('--'+method+'-router', type=Path, required=True)
        parser.add_argument('--'+method+'-job', type=Path)
    parser.add_argument('--pair-gate', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = {'schema': 'h3-sampled-attention-effect-summary-v1',
              'scope': '读取现有JSON；统计采样attention变化及实际执行次数。动作质量由视频和独立评测提供。',
              'definitions': {
                'ref_mass': '每层从至多8个heads×128个query采样，计算query对整个参考视频key组的原softmax质量，再按层平均。',
                'correction_ratio': '每层从至多8个heads×128个query×16个channels采样：RMS(O_after−O_before)/max(RMS(O_before),1e−8)，再按层平均。',
                'active_step_aggregate': '等权平均记录到的active step层均值；保留每步原始值和覆盖数量。',
                'efficiency': 'NFE取实际completed_forward_calls；job墙钟包含模型加载、编码、采样、解码与轮询延迟。'},
              'runs': {}}
    for method in ['native', 'forced']:
        router = getattr(args, method+'_router'); job = getattr(args, method+'_job')
        result['runs'][method] = summarize(read(router), read(job) if job else None)
        result['runs'][method]['router_file'] = bound(router)
        if job:
            result['runs'][method]['job_file'] = bound(job)
    if args.pair_gate:
        gate = read(args.pair_gate)
        result['pair_runtime_gate'] = dict(bound(args.pair_gate), passed=gate.get('passed'),
                                           schema=gate.get('schema'))
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            stream.write(text)
    print(text)


if __name__ == '__main__':
    main()
