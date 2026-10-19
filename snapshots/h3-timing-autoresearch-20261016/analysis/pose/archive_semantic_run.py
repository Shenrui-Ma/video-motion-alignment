"""Archive a formal semantic arm plus its special actual-encoding acceptance."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True, choices=[
        's05_semantic_b_p6_t6', 's05_semantic_c_p0_t6', 's05_semantic_d_p6_t0'])
    parser.add_argument('--host', default='H3_SERVER_A')
    args = parser.parse_args()
    local = Path('/Users/researcher/DevProjects/h3-timing-autoresearch-20261016')
    remote = PurePosixPath('/data5/researcher/h3_runs/timing_autoresearch_20261016_semantic0')
    helper = Path(__file__).with_name('archive_run.py')
    spec = importlib.util.spec_from_file_location('archive_helper', helper)
    archive = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(archive)
    subprocess.run([sys.executable, str(helper), '--host', args.host, '--run-id', args.run_id,
                    '--remote-root', str(remote), '--local-root', str(local)], check=True)
    destination = local/'analysis/pose/pilot'/f'{args.run_id}_provenance'
    admission = json.loads((destination.parent/f'{args.run_id}.history_provenance.json').read_text())
    condition_id = args.run_id+'_condition'
    paths = [f'audit/{condition_id}_conditioning.json', f'audit/{condition_id}_accepted.json',
             'audit/s05_semantic_a0_p0_t0_condition_zero_gate.json',
             'audit/s05_semantic_a0_p0_t0_condition_conditioning.json',
             'audit/semantic_freeze_manifest.json', 'scripts/check_encoded_acceptance.py',
             'baseline/05_sam_1312x736_shared_v3_conditioning.json',
             'baseline/s05_full_seed1_native_noise.json']
    copies = [archive.copy_file(args.host, remote/path, destination/'semantic'/path) for path in paths]
    accepted_file = destination/'semantic/audit'/f'{condition_id}_accepted.json'
    accepted = json.loads(accepted_file.read_text())
    condition_file = destination/'semantic/audit'/f'{condition_id}_conditioning.json'
    if not (accepted['passed'] and accepted['condition_run_id'] == condition_id and
            hashlib.sha256(accepted_file.read_bytes()).hexdigest() == admission['semantic_acceptance']['sha256'] and
            hashlib.sha256(condition_file.read_bytes()).hexdigest() == accepted['condition_sha256']):
        raise ValueError('Copied actual semantic acceptance differs from measured admission')
    manifest = {'run_id': args.run_id, 'actual_semantic_acceptance_verified': True,
                'claim_limit': 'per-arm actual acceptance and A0 evidence, not embedding equality across deliberately changed arms',
                'full_factorial_checker': 'scripts/check_encoded_acceptance.py must separately pass with require-all',
                'copied_files': copies}
    (destination/'semantic_archive_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'saved': str(destination/'semantic_archive_manifest.json')}))


if __name__ == '__main__':
    main()
