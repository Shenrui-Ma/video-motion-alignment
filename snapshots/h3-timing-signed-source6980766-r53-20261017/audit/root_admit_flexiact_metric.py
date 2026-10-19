"""Admit one exact, waiting FlexiAct metric PID alongside the current R53 service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

R53 = Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
METRIC = Path('/data5/researcher/h3_runs/flexiact_official_metric_20261017')
CONTROL = Path('/data5/researcher/h3_runs/flexiact_native_scores_r49_20261017')
GPU = 'GPU-REDACTED'
RUNNER_SHA = '6583095b3037ef655f2667023b897c8931917f3d5a2451e7c72615b0cf1bb3f1'


def identity(pid):
    p = Path('/proc') / str(pid)
    return dict(uid=p.stat().st_uid,
                start_ticks=p.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19],
                cmdline_sha256=hashlib.sha256(p.joinpath('cmdline').read_bytes()).hexdigest())


def main(ready):
    ready = Path(ready).resolve()
    assert ready.is_relative_to(CONTROL) and ready.name == 'ready.json'
    record = json.loads(ready.read_text())
    assert record['gpu_uuid'] == GPU and record['CUDA_started'] is False
    assert record['target_sha256'] == RUNNER_SHA
    assert hashlib.sha256((METRIC/'run_tracks.py').read_bytes()).hexdigest() == RUNNER_SHA
    assert identity(record['pid']) == record['identity']
    assert record['identity']['uid'] == os.getuid() == 1016
    cmd = (Path('/proc')/str(record['pid'])/'cmdline').read_bytes()
    assert str(METRIC/'launch_tracking_gate.py').encode() in cmd
    assert identity(63582) == dict(uid=1016, start_ticks='2625625538',
        cmdline_sha256='044785b36f8bea04b6e64bcebbbbf67b6bfd08a76ccd6e28f8a5841fbaf996d4')
    assert not (ready.parent/'go.json').exists()
    raw = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
                                   '--format=csv,noheader,nounits'], text=True)
    own_cards = set()
    for line in raw.splitlines():
        gpu, pid = [v.strip() for v in line.split(',')]
        assert gpu != GPU, 'Selected metric GPU has active compute'
        p = Path('/proc')/pid
        if p.exists() and p.stat().st_uid == os.getuid():
            own_cards.add(gpu)
    assert len(own_cards | {GPU}) <= 2
    ap = R53/'configs/admission.json'
    before = json.loads(ap.read_text())
    after = json.loads(ap.read_text())
    permitted = []
    for row in after['permitted_compute_processes']:
        if (Path('/proc')/str(row['pid'])).exists():
            assert identity(row['pid']) == row['identity'], 'Stale reused peer PID'
            permitted.append(row)
    permitted.append(dict(pid=record['pid'], identity=record['identity']))
    after['permitted_compute_processes'] = permitted
    stamp = time.time_ns()
    audit = R53/'audit'/f'root_metric_peer_{stamp}.json'
    with audit.open('x') as f:
        json.dump(dict(ready=str(ready), ready_record=record, before=before, after=after), f, indent=2)
    tmp = ap.with_name(f'admission.{stamp}.tmp')
    tmp.write_text(json.dumps(after, indent=2)+'\n')
    os.replace(tmp, ap)
    assert identity(record['pid']) == record['identity']
    with (ready.parent/'go.json').open('x') as f:
        json.dump(record, f, indent=2)
    print(json.dumps(dict(admitted_pid=record['pid'], audit=str(audit), go=str(ready.parent/'go.json'))))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('ready')
    main(p.parse_args().ready)
