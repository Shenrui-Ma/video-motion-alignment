"""Record completion of this lane's serial CPU consumers without touching GPU services."""
import datetime
import hashlib
import json
from pathlib import Path


ROOT = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
HOME = ROOT/'analysis/pose'
STATES = ['transfer', 'late', 'offset', 'phase_late', 'semantic', 'equal_budget']


def main():
    records = {}
    for name in STATES:
        path = HOME/f'{name}_cpu_consumer_state.json'
        state = json.loads(path.read_text())
        if name == 'transfer':
            inventories = {key: row['watcher_inventory'] for key, row in state['cases'].items()}
            expected = {key: set(row['requested']) for key, row in state['cases'].items()}
            returncodes = {key: row['returncode'] for key, row in state['cases'].items()}
            finished = state['status'] == 'consumers_finished_check_per_video_inventory'
        else:
            inventories = {name: state['watcher_inventory']}
            expected = {name: set(state.get('runs', [state.get('run')]))}
            returncodes = {name: state['returncode']}
            finished = state['status'] == 'finished_check_per_video_inventory'
        passed = finished and all(code == 0 for code in returncodes.values())
        passed = passed and all(wanted == set(inventories[key]['completed']) and
                                wanted == set(inventories[key]['requested_run_ids'])
                                for key, wanted in expected.items())
        records[name] = {'state_file': str(path), 'state_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'pid': state['pid'], 'status': state['status'], 'returncodes': returncodes,
                         'inventories': inventories, 'passed': passed}
    active = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            argv = [value.decode(errors='replace') for value in path.read_bytes().split(b'\0') if value]
        except OSError:
            continue
        if not argv or 'python' not in Path(argv[0]).name.lower():
            continue
        owned = any(value == str(ROOT/'scripts/pose_probe.py') or
                    (value.startswith(str(HOME)+'/') and Path(value).name.startswith(('watch_', 'consume_'))
                     and value.endswith('.py')) for value in argv[1:])
        if owned:
            active.append({'pid': int(path.parent.name), 'argv': argv})
    digest = hashlib.sha256((ROOT/'scripts/timing_metrics.py').read_bytes()).hexdigest()
    result = {'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'consumers': records, 'active_owned_watch_or_pose_processes': active,
              'frozen_metrics_sha256': digest,
              'metrics_unchanged': digest == 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e',
              'scope': 'CPU evaluation consumers only; parent separately verifies all GPU services/VRAM cleanup',
              'passed': all(row['passed'] for row in records.values()) and not active and
                        digest == 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'}
    (HOME/'CPU_FINAL_COMPLETION.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'passed': result['passed'], 'active': active,
                      'consumer_passed': {key: row['passed'] for key, row in records.items()}}))
    if not result['passed']:
        raise SystemExit('CPU lane still active or inventory incomplete; snapshot retained')


if __name__ == '__main__':
    main()
