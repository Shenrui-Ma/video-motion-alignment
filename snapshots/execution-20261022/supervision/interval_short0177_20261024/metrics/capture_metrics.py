"""Read one isolated metric snapshot; preserve remote JSON bytes locally and exit."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REMOTE = r'''
import hashlib,json,pathlib,time
r=pathlib.Path('/data/research-user/h3_metrics_interval_short0177_20261024')
names=['RUN.json','EXIT.json','SUMMARY.json','PREFLIGHT.json','LAUNCH_RECEIPT.json','FFMPEG_PATH_RECEIPT.json','evaluation/heartbeat.json']
files={n:(r/n).read_text() for n in names if (r/n).is_file()}
for p in sorted((r/'evaluation/results').glob('*/*.json')):
    files[str(p.relative_to(r))]=p.read_text()
for p in sorted((r/'evaluation/states').glob('*.json')):
    files[str(p.relative_to(r))]=p.read_text()
rows=[]
for name,raw in files.items():
    if name.startswith('evaluation/results/'):
        x=json.loads(raw)
        if x.get('metric'):rows.append(x)
processes=[]
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
        if str(r/'code')+'/' in cmd and any(s in cmd for s in ['run_metrics.py','durable_metrics.py','metric_worker.py']):
            st=(p/'stat').read_text().split(') ',1)[1].split()
            processes.append(dict(pid=int(p.name),uid=p.stat().st_uid,start_ticks=st[19],state=st[0],cmd=cmd))
    except (OSError,UnicodeDecodeError):pass
counts={}
for x in rows:
    c=counts.setdefault(x['method'],{})
    c[x['status']]=c.get(x['status'],0)+1
status=dict(time=time.time(),boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
    numeric_done=sum(x['status']=='done' for x in rows),qa_not_applicable=sum(x['status']=='not_applicable' for x in rows),
    failed=[x for x in rows if x['status']=='failed'],by_method=counts,processes=processes,
    exit=json.loads(files['EXIT.json']) if 'EXIT.json' in files else None)
hashes={name:hashlib.sha256((r/name).read_bytes()).hexdigest() for name in files}
print(json.dumps(dict(status=status,files=files,sha256=hashes)))
'''


def main():
    result = subprocess.run(
        ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', 'H3_HOST_CONFIGURE_LOCALLY', 'python3 -'],
        input=REMOTE, text=True, capture_output=True, check=True, timeout=40)
    data = json.loads(result.stdout)
    for relative, raw in data['files'].items():
        if hashlib.sha256(raw.encode()).hexdigest() != data['sha256'][relative]:
            raise ValueError('Remote artifact changed during capture: ' + relative)
        path = HERE / ('raw/' + relative if relative.startswith('evaluation/') else relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(raw)
        temporary.replace(path)
    (HERE / 'PROGRESS.json').write_text(json.dumps(data['status'], indent=2))
    (HERE / 'CAPTURE_SHA256.json').write_text(json.dumps(data['sha256'], indent=2))
    compact = {key: value for key, value in data['status'].items() if key != 'processes'}
    compact['active'] = [{'pid': p['pid'], 'metric': p['cmd'].split('--metric ', 1)[1].split()[0]}
                         for p in data['status']['processes'] if '--metric ' in p['cmd']]
    print(json.dumps(compact, indent=2))


if __name__ == '__main__':
    main()
