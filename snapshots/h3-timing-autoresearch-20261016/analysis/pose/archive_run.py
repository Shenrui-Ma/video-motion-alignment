"""Copy an evaluated formal run using exact history output names; no prefix guesses."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess


def remote_json(host, path):
    command = ['ssh', host, 'cat '+shlex.quote(str(path))]
    return json.loads(subprocess.check_output(command, text=True))


def copy_file(host, remote, local):
    local.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['scp', f'{host}:{remote}', str(local)], check=True)
    return {'remote': str(remote), 'local': str(local),
            'sha256': hashlib.sha256(local.read_bytes()).hexdigest(),
            'bytes': local.stat().st_size}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id', required=True)
    p.add_argument('--host', default='H3_SERVER_A')
    p.add_argument('--remote-root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016')
    p.add_argument('--local-root', default='/Users/researcher/DevProjects/h3-timing-autoresearch-20261016')
    args = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_]+', args.run_id) or 'bench' in args.run_id.lower():
        raise ValueError('Expected a formal run ID')
    run = args.run_id
    remote, local = PurePosixPath(args.remote_root), Path(args.local_root)
    history = remote_json(args.host, remote/'logs'/f'{run}_history.json')
    if history['status']['status_str'] != 'success' or not history['status']['completed']:
        raise ValueError('Formal history is not successfully complete; retain failure, do not archive as success')
    graph = history['prompt'][2]
    router = [node for node in graph.values()
              if node['class_type'] in ('H3TemporalRouter', 'H3PhaseRoPE')]
    if len(router) != 1 or router[0]['inputs']['run_id'] != run:
        raise ValueError('History/run identity mismatch')
    audit_folder = 'phase_rope' if router[0]['class_type'] == 'H3PhaseRoPE' else 'router'
    files = [item for key, node in graph.items() if node['class_type'] == 'SaveVideo'
             for item in history['outputs'].get(key, {}).get('images', [])
             if item.get('type') == 'output' and item.get('filename', '').endswith('.mp4')]
    if len(files) != 1:
        raise ValueError('Expected one exact SaveVideo MP4')
    item = files[0]
    relative = PurePosixPath(item.get('subfolder', ''))/item['filename']
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Output path is outside formal output directory')
    stem = relative.stem
    pose_dir = remote/'analysis/pose/pilot'
    pose = remote_json(args.host, pose_dir/f'{stem}.pose.json')
    admission = remote_json(args.host, pose_dir/f'{run}.history_provenance.json')
    if admission['history_output'] != item:
        raise ValueError('Observer admitted a different MP4')
    expected = admission['expected_geometry_from_config']
    if any(admission[k] != expected[k] for k in ('width', 'height', 'frames', 'fps')):
        raise ValueError('Formal output failed geometry check')
    destination = local/'analysis/pose/pilot'
    provenance = destination/f'{run}_provenance'
    copies = []
    copies.append(copy_file(args.host, remote/'output'/relative, local/'outputs'/relative))
    if copies[0]['sha256'] != pose['video']['sha256']:
        raise ValueError('Downloaded MP4 hash differs from measured MP4')
    pairs = [(remote/'logs'/f'{run}_history.json', provenance/'history.json'),
             (remote/'configs'/f'{run}.json', provenance/'config.json'),
             (remote/'audit'/f'{run}_conditioning.json', provenance/'conditioning.json'),
             (remote/'audit'/f'{run}_noise.json', provenance/'noise.json'),
             (remote/'audit'/audit_folder/f'{run}.json', provenance/f'{audit_folder}_audit.json'),
             (pose_dir/f'{run}.history_provenance.json', destination/f'{run}.history_provenance.json'),
             (pose_dir/f'{stem}.pose.json', destination/f'{stem}.pose.json'),
             (pose_dir/f'{stem}.extract.log', destination/f'{stem}.extract.log')]
    for threshold in ('0.3', '0.5'):
        for suffix in (f'.threshold{threshold}.timing.json', f'.threshold{threshold}.timing.svg'):
            pairs.append((pose_dir/(stem+suffix), destination/(stem+suffix)))
    for frame in (55, 63, 86, 105):
        filename = f'{stem}.frame{frame:03d}.pose.jpg'
        pairs.append((pose_dir/filename, destination/filename))
    for src, dst in pairs:
        copies.append(copy_file(args.host, src, dst))
    manifest = {'run_id': run, 'prompt_id': admission['prompt_id'], 'history_success': True,
                'geometry': expected, 'measured_mp4_sha256': pose['video']['sha256'],
                'archive_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'copied_files': copies}
    (provenance/'archive_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'run': run, 'video': copies[0], 'manifest': str(provenance/'archive_manifest.json')}))


if __name__ == '__main__':
    main()
