"""Check actual prepared inputs and noise for a completed paired experiment."""
import argparse
import json
from pathlib import Path


def inspect(root, baseline, intervention):
    root = Path(root)
    read = lambda folder, name: json.loads((root / folder / name).read_text())
    a, b = [read('audit', n + '_conditioning.json') for n in (baseline, intervention)]
    na, nb = [read('audit', n + '_noise.json') for n in (baseline, intervention)]
    checks = {key: a[key] == b[key] for key in (
        'prompt', 'input_video', 'native_vae_calls', 'qwen_presentation',
        'conditioning_embedding', 'token_tags', 'target_latent_shapes', 'packed_layout')}
    checks['actual_noise_streams'] = na['actual_noise_streams'] == nb['actual_noise_streams']
    checks['noise_signature'] = na['signature'] == nb['signature']
    graph_a, graph_b = [read('configs', n + '.json') for n in (baseline, intervention)]
    for node in ('1', '2', '3', '4', '41', '5', '8', '9', '11', '12', '13', '21', '22', '23', '24'):
        checks['fixed_graph_node_' + node] = graph_a.get(node) == graph_b.get(node)
    histories = {}
    for name in (baseline, intervention):
        history = read('logs', name + '_history.json')
        histories[name] = history['status']
        checks[name + '_completed_successfully'] = bool(history['status'].get('completed')) and history['status']['status_str'] == 'success'
    result = {'baseline': baseline, 'intervention': intervention, 'checks': checks,
              'passed': all(checks.values()), 'histories': histories,
              'scope': 'Prepared inputs/noise and fixed graph nodes only; efficacy and attention backend dispatch are separate checks.'}
    out = root / 'audit' / (baseline + '__' + intervention + '_pair_check.json')
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('baseline')
    parser.add_argument('intervention')
    args = parser.parse_args()
    result = inspect(args.root, args.baseline, args.intervention)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)
