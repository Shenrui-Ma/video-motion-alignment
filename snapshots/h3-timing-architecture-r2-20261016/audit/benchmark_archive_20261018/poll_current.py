"""Read bounded progress snapshots from the currently admitted experiment hosts."""
import concurrent.futures
import json
import shlex
import subprocess


REMOTE = r'''
import json,re
from pathlib import Path
roots=ROOTS
for root in roots:
 p=Path(root); out={'run':p.name}
 f=p/'logs/controller_state.json'
 if f.is_file():
  d=json.loads(f.read_text());out.update(status=d.get('status'),current=d.get('current'),completed=len(d.get('completed',[])),unix=d.get('unix'))
 else:out['status']='not_started'
 f=p/'logs/comfyui.log'
 if f.is_file():
  tail=f.read_text(errors='replace')[-5000:]
  steps=re.findall(r'\d+%\|[^\r\n]+',tail)
  out['last_steps']=steps[-2:]
  out['log_tail']=tail[-250:] if not steps else ''
 print(json.dumps(out))
'''

HOSTS = [
    (['ssh', 'H3_SERVER_B'], [
        '/data3/researcher/h3_runs/timing_ivebench_remaining_r69_20261018',
        '/data3/researcher/h3_runs/timing_flexiact_prompt_pair_r72_20261018',
        '/data3/researcher/h3_runs/timing_flexiact_official_six_r74_20261018',
    ]),
    (['ssh', '-J', 'H3_SERVER_B', 'H3_SERVER_A'], [
        '/data5/researcher/h3_runs/timing_ivebench_expanded_r73_20261018',
        '/data5/researcher/h3_runs/timing_source51310_prompt_pair_r75_20261018',
    ]),
]


def poll(item):
    args, roots = item
    code = REMOTE.replace('ROOTS', repr(roots))
    result = subprocess.run(args + ['python3 -c ' + shlex.quote(code)],
                            capture_output=True, text=True, timeout=30)
    return {'host': args[-1], 'exit': result.returncode,
            'results': result.stdout.strip(),
            'error': result.stderr[-800:] if result.returncode else ''}


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for value in pool.map(poll, HOSTS):
            print(json.dumps(value, ensure_ascii=False))
