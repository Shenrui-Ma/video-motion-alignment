"""Run the unchanged local transaction through its sealed priority-only entry."""
import argparse
from pathlib import Path
import shlex
import sys

HERE = Path(__file__).resolve().parent
SIDE = HERE.parent.parent
sys.path.insert(0, str(SIDE))
import run_one


def rewrite(command, protocol):
    expected = protocol['root_remote'] + '/remote_one.py'
    if isinstance(command, list) and command and command[0] == 'ssh' and isinstance(command[-1], str):
        words = shlex.split(command[-1])
        if expected in words:
            words[words.index(expected)] = protocol['root_remote'] + '/admin/priority_v2/remote_entry.py'
            return command[:-1] + [shlex.join(words)]
    return command


def main():
    protocol = run_one.read(SIDE / 'PROTOCOL.json')
    original_run = run_one.subprocess.run
    def bridge(command, *args, **kwargs):
        return original_run(rewrite(command, protocol), *args, **kwargs)
    run_one.subprocess.run = bridge
    run_one.SSH[1:1] = ['-J', 'H3_SERVER_B']
    p = argparse.ArgumentParser()
    for name in ('source', 'method', 'metric-inputs', 'mapping'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    print(run_one.json.dumps(run_one.execute(a.source, a.method, a.metric_inputs, a.mapping), allow_nan=False))

if __name__ == '__main__': main()
