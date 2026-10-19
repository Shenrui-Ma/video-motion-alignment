"""Collect a compact read-only remote snapshot into this consumer's audit."""
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
protocol = json.loads((HERE.parent / 'PROTOCOL.json').read_text())
ssh = ['ssh']
if protocol['root_remote'].startswith('/data5/'):
    ssh += ['-J', 'H3_SERVER_B']
    host = 'H3_SERVER_A'
else:
    host = protocol['consumer']['host']
ssh += ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', host]
result = subprocess.run(ssh + ['python3 - ' + protocol['root_remote']],
                        input=(HERE / 'progress_snapshot.py').read_text(),
                        text=True, capture_output=True, timeout=90)
if result.returncode:
    (HERE / 'PROGRESS_QUERY_FAILURE.log').write_text(result.stdout + '\nSTDERR\n' + result.stderr)
    result.check_returncode()
snapshot = json.loads(result.stdout)
path = HERE / 'PROGRESS_LATEST.json'
temporary = path.with_suffix('.tmp')
temporary.write_text(json.dumps(snapshot, indent=2) + '\n')
temporary.replace(path)
print(json.dumps({'controller': snapshot['controller'], 'cases': [
    {key: row.get(key) for key in ('run_id', 'status', 'completed_steps', 'ON_indices',
                                   'observation_status', 'observation_unknown_reasons',
                                   'decision_reasons', 'decoder_retries')}
    | {'responses': len(row['responses'])} for row in snapshot['cases']],
    'failed_requests': snapshot['failed_requests']}))
