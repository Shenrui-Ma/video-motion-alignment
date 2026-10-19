"""Administrative local download policy. Remote numerical consumers stay frozen."""
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import traceback

HOME = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOME))
import consume as base
from contract import read, require, safe, save, sha


def original_selected(name):
    if name.endswith('.pt') or name.startswith(('inputs/', 'input/', 'configs/parents/')):
        return False
    return (name.startswith('output/') or name.startswith('logs/') or
            name == 'deploy_manifest.json' or
            name in ('configs/protocol.json', 'configs/scientific_contract.json') or
            name.startswith('configs/graphs/') or
            (name.startswith('audit/x0/') and name.endswith('/manifest.json')))


def derived_selected(name):
    if name.endswith('.pt') or Path(name).name == 'source_score.mp4':
        return False
    return name.endswith(('.json', '.log')) or Path(name).name in ('edited49_8fps.mp4', 'edited_score.mp4')


def transfer(remote_relative, destination, names, receipt_dir):
    for name in names:
        safe(destination, name)
    listing = receipt_dir / ('files_' + str(time.time_ns()) + '.list')
    listing.write_text('\n'.join(sorted(names)) + '\n')
    command = ['rsync', '-a', '--files-from=' + str(listing), '-e', shlex.join(base.SSH),
               base.HOST + ':' + base.REMOTE + '/' + remote_relative + '/', str(destination) + '/']
    subprocess.run(command, check=True, timeout=600)


def sizes(remote_relative, names):
    script = ('from pathlib import Path; import json; root=Path(' + repr(base.REMOTE + '/' + remote_relative) + '); '
              'names=' + repr(sorted(names)) + '; print(json.dumps({n:(root/n).stat().st_size for n in names}))')
    result = subprocess.run(base.SSH + [base.HOST, shlex.join(['python3', '-c', script])],
                            text=True, capture_output=True, check=True, timeout=60)
    return json.loads(result.stdout)


def known_local_references():
    result = {}
    for path in (HOME / 'download_receipts').rglob('MINIMAL_DOWNLOAD.json'):
        record = read(path)
        for row in record['selected_files'] + record['local_references']:
            local = Path(row['local_file'])
            if local.is_file() and sha(local) == row['sha256']:
                result[row['sha256']] = str(local)
    return result


def download(remote_relative):
    dest = HOME / remote_relative
    dest.mkdir(parents=True, exist_ok=True)
    receipts = HOME / 'download_receipts' / remote_relative
    receipts.mkdir(parents=True, exist_ok=True)
    partial = remote_relative.startswith('completed_cases/')
    anchors = {'FILE_INVENTORY.json'}
    if partial:
        anchors |= {'DERIVED_FILES.json', 'CASE_READY.json', 'CASE_RUNTIME_GATE.json'}
    else:
        anchors |= {'RUN_GATE.json', 'RUNTIME_GATE.json'}
        # Full-batch derived output exists after finalize, and is optional at archive.
        script = 'from pathlib import Path; print(int(Path(' + repr(base.REMOTE + '/' + remote_relative + '/DERIVED_FILES.json') + ').exists()))'
        response = subprocess.run(base.SSH + [base.HOST, shlex.join(['python3', '-c', script])],
                                  capture_output=True, text=True, check=True, timeout=60)
        if response.stdout.strip() == '1':
            anchors |= {'DERIVED_FILES.json', 'CPU_COMPLETE.json'}
    transfer(remote_relative, dest, anchors, receipts)
    inventory = read(dest / 'FILE_INVENTORY.json')
    derived = read(dest / 'DERIVED_FILES.json') if (dest / 'DERIVED_FILES.json').exists() else {}
    gate = read(dest / ('CASE_READY.json' if partial else 'RUN_GATE.json'))
    require(gate['file_inventory_sha256'] == sha(dest / 'FILE_INVENTORY.json'), 'archive inventory anchor differs')
    runtime_name = 'CASE_RUNTIME_GATE.json' if partial else 'RUNTIME_GATE.json'
    require(gate['runtime_gate_sha256'] == sha(dest / runtime_name), 'runtime proof anchor differs')
    expected = {name: row['sha256'] for name, row in inventory.items() if original_selected(name)}
    expected.update({name: digest for name, digest in derived.items() if derived_selected(name)})
    cache = known_local_references()
    references, needed = [], {}
    for name, digest in expected.items():
        existing = safe(dest, name)
        if existing.is_file():
            require(sha(existing) == digest, 'existing local file changed: ' + name)
        elif digest in cache:
            references.append({'remote_file': base.REMOTE + '/' + remote_relative + '/' + name,
                               'relative_file': name, 'local_file': cache[digest], 'sha256': digest})
        else:
            needed[name] = digest
    counts = sizes(remote_relative, needed)
    total = sum(counts.values())
    plan = {'remote_relative': remote_relative, 'new_bytes': total,
            'files': [{'relative_file': name, 'bytes': counts[name], 'sha256': digest} for name, digest in needed.items()]}
    save(receipts / 'DOWNLOAD_PLAN.json', plan)
    require(total <= 1024**3, 'new download exceeds1GiB: inspect DOWNLOAD_PLAN.json with root')
    require(shutil.disk_usage(HOME).free >= total + 1024**3, 'preserve1GiB local free space; remote consumption complete')
    if needed:
        transfer(remote_relative, dest, needed, receipts)
    selected = []
    for name, digest in expected.items():
        path = safe(dest, name)
        if path.is_file():
            require(sha(path) == digest, 'download SHA differs: ' + name)
            selected.append({'remote_file': base.REMOTE + '/' + remote_relative + '/' + name,
                             'relative_file': name, 'local_file': str(path), 'sha256': digest, 'bytes': path.stat().st_size})
    represented = {r['relative_file'] for r in selected + references}
    require(represented == set(expected), 'selected download/reference coverage differs')
    remaining = [{'remote_file': base.REMOTE + '/' + remote_relative + '/' + name,
                  'relative_file': name, **row} for name, row in inventory.items() if name not in represented]
    remaining += [{'remote_file': base.REMOTE + '/' + remote_relative + '/' + name,
                   'relative_file': name, 'sha256': digest} for name, digest in derived.items() if name not in represented]
    record = {'schema': 'h3-minimal-local-download-v1', 'remote_archive': base.REMOTE + '/' + remote_relative,
              'remote_inventory_sha256': sha(dest / 'FILE_INVENTORY.json'),
              'remote_derived_manifest_sha256': sha(dest / 'DERIVED_FILES.json') if derived else None,
              'remote_complete_evidence': str(dest / ('CASE_READY.json' if partial else 'RUN_GATE.json')),
              'selected_files': selected, 'local_references': references, 'remote_retained_files': remaining,
              'new_bytes': total, 'original_PT_downloaded': False,
              'remote_numerical_consumer_unchanged': True, 'administrative_code_sha256': sha(__file__)}
    save(receipts / 'MINIMAL_DOWNLOAD.json', record)
    return gate


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run')
    p.add_argument('--batch', action='store_true')
    a = p.parse_args()
    require(a.run and not a.batch, 'retry2 accepts an explicit remaining-case release')
    try:
        if a.run:
            import run_incremental_case as entry
            entry.download = lambda run: download('completed_cases/' + run)
            result = entry.execute(a.run)
            save(HOME / 'audit' / ('INCREMENTAL_LATEST_' + a.run + '.json'), result)
        else:
            import one_phase
            base.download = lambda: download('captured/batch')
            result = one_phase.execute_one()
            save(HOME / 'LAST_ONE_PHASE.json', result)
    except Exception as error:
        failure = HOME / 'audit' / ('MINIMAL_DOWNLOAD_FAILURE_' + (a.run or 'batch') + '.json')
        save(failure, {'time': time.time(), 'error': repr(error), 'traceback': traceback.format_exc(),
                       'automatic_retry': False, 'inspect_remote_phase_before_retry': True})
        raise
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()
