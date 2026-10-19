"""Root-owned deployment and live resource admission for the signed pilot."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import time

ROOT = Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
STAGE = Path('/data5/researcher/h3_runs/r53_root_stage')
GPU = 'GPU-REDACTED'
PEER_GPU = 'GPU-REDACTED'
PEER = Path('/data5/researcher/h3_runs/timing_flexiact_native_r49_20261017')
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    return json.loads(Path(p).read_text())

def write(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + '.root.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    os.replace(temp, p)

def identity(pid):
    p = Path('/proc') / str(pid)
    return dict(uid=p.stat().st_uid,
                start_ticks=(p/'stat').read_text().rsplit(')', 1)[1].split()[19],
                cmdline_sha256=sha(p/'cmdline'))

def processes():
    out = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory', '--format=csv,noheader,nounits'], text=True, timeout=20)
    rows = []
    for line in out.splitlines():
        pid, gpu, memory = [v.strip() for v in line.split(',')]
        p = Path('/proc') / pid
        rows.append(dict(pid=int(pid), gpu_uuid=gpu, used_memory_mib=memory, uid=p.stat().st_uid))
    return rows

def fresh_admission():
    rows = processes()
    assert not [r for r in rows if r['gpu_uuid'] == GPU], 'selected GPU occupied'
    own = [r for r in rows if r['uid'] == os.getuid()]
    expected = dict(uid=1016, start_ticks='2625167040', cmdline_sha256='95d6e7b29d8a8342315535cdb4cc44d2dccfed46fcdc228fb9802418843ed60b')
    for row in own:
        assert row['gpu_uuid'] == PEER_GPU and row['pid'] == 45686
        assert identity(row['pid']) == expected
    return rows, [dict(pid=r['pid'], identity=identity(r['pid'])) for r in own]

def verify_seal():
    assert sha(ROOT/'deploy_manifest.json') == '6576342c90a281bb59be584987a222b4dd3ad0affeb673ca8a21bf86915c5527'
    m = read(ROOT/'deploy_manifest.json')
    for name, entry in m['files'].items():
        p = ROOT/name
        assert p.stat().st_size == entry['bytes'] and sha(p) == entry['sha256'], name
    return len(m['files'])

def environment():
    return dict(os.environ, TMPDIR=str(ROOT/'temp'), TMP=str(ROOT/'temp'), TEMP=str(ROOT/'temp'),
                CUDA_VISIBLE_DEVICES=GPU, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps', PYTHONDONTWRITEBYTECODE='1')

def deploy():
    assert not ROOT.exists()
    bundle = STAGE/'runtime_bundle_v1.tar.gz'
    assert sha(bundle) == '0e772ddb345f85729fb6a00e51e056ab31189077da2ef6a3e183a0f35f740831'
    with tarfile.open(bundle) as tf:
        members = tf.getmembers()
        assert sum(m.isfile() for m in members) == 96
        for m in members:
            assert not m.name.startswith('/') and '..' not in Path(m.name).parts and (m.isfile() or m.isdir())
        ROOT.mkdir()
        tf.extractall(ROOT)
    count = verify_seal()
    (ROOT/'temp').mkdir(exist_ok=True)
    for name, digest in read(ROOT/'configs/input_hashes.json').items():
        src = Path('/data5/researcher/h3_runs/timing_new_dance_native_r47_20261017/inputs')/name
        assert sha(src) == digest
        (ROOT/'inputs').mkdir(exist_ok=True)
        shutil.copyfile(src, ROOT/'inputs'/name)
        assert sha(ROOT/'inputs'/name) == digest
    done = subprocess.run(['python3', str(ROOT/'scripts/preflight.py'), '--metadata-only'], env=environment(), capture_output=True, text=True)
    (ROOT/'audit/root_metadata_preflight.log').write_text(done.stdout + done.stderr)
    print(json.dumps(dict(files=count, preflight_exit=done.returncode)))
    if done.returncode: print(done.stdout + done.stderr)
    assert done.returncode == 0

def kernel():
    verify_seal()
    before, peer = fresh_admission()
    stamp = str(time.time_ns())
    log = ROOT/f'audit/root_kernel_{stamp}.log'
    record = dict(start_unix=time.time(), pre_compute=before, permitted_peer=peer)
    cmd = [PYTHON, '-u', str(ROOT/'scripts/gpu_dynamic_union_smoke.py'), '--root-admitted', '--output', str(ROOT/'audit/gpu_dynamic_union_gate.json')]
    with log.open('x') as stream:
        proc = subprocess.Popen(cmd, env=environment(), stdout=stream, stderr=subprocess.STDOUT)
        time.sleep(.1)
        record['owner'] = dict(pid=proc.pid, **identity(proc.pid))
        write(ROOT/f'audit/root_kernel_{stamp}.json', record)
        try:
            code = proc.wait(timeout=240)
        except subprocess.TimeoutExpired:
            assert dict(pid=proc.pid, **identity(proc.pid)) == record['owner']
            proc.terminate()
            try: code = proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                assert dict(pid=proc.pid, **identity(proc.pid)) == record['owner']
                proc.kill(); code = proc.wait(timeout=15)
            record['timed_out'] = True
    record.update(returncode=code, end_unix=time.time(), post_compute=processes())
    gate = ROOT/'audit/gpu_dynamic_union_gate.json'
    if gate.exists(): record.update(gate_sha256=sha(gate), gate_passed=read(gate)['passed'])
    write(ROOT/f'audit/root_kernel_{stamp}.json', record)
    print(json.dumps({k:record.get(k) for k in ['returncode','gate_passed','gate_sha256','timed_out']}), flush=True)
    assert code == 0 and record.get('gate_passed')
    assert not [r for r in record['post_compute'] if r['gpu_uuid'] == GPU]

def admit():
    verify_seal()
    rows, peer = fresh_admission()
    raw = subprocess.check_output(['nvidia-smi', '-i', GPU, '--query-gpu=uuid,memory.total,memory.used,memory.free', '--format=csv,noheader,nounits'], text=True, timeout=20).strip()
    parts = [s.strip() for s in raw.split(',')]
    assert parts[0] == GPU and int(parts[3]) > 70000
    with socket.socket() as s: s.bind(('127.0.0.1',8513))
    probe = ROOT/'audit/root_current_resource_probe.json'
    write(probe, dict(unix=time.time(), gpu=raw, compute=rows, permitted_peer=peer, port8513_free=True))
    old = read('/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017/audit/resource_admission.json')
    gatepath = ROOT/'audit/gpu_dynamic_union_gate.json'
    gate = read(gatepath)
    assert gate['passed'] and gate['NFE'] == 0
    actual = [c for c in gate['cases'] if c['actual_shape']][0]
    assert actual['comparisons']['full']['increment_peak_allocated_bytes'] <= old['routing_increment_bound_bytes']
    resource = dict(old, schema='r53-root-resource-admission-v1', root_approved=True, gpu_uuid=GPU,
        kernel_gate_sha256=sha(gatepath), protocol_sha256=sha(ROOT/'configs/protocol.json'),
        inheritance_sha256=sha(ROOT/'configs/r27_inheritance.json'),
        kernel_inheritance_sha256=sha(ROOT/'configs/kernel_inheritance.json'),
        total_memory_bytes=int(parts[1])*1024*1024, observed_unix=time.time(),
        actual_kernel_increment_bytes=actual['comparisons']['full']['increment_peak_allocated_bytes'])
    resource['evidence'] = list(old['evidence']) + [dict(file=str(probe),sha256=sha(probe)),dict(file=str(gatepath),sha256=sha(gatepath))]
    write(ROOT/'audit/resource_admission.json', resource)
    admission = read(ROOT/'configs/admission.json')
    admission.update(permitted_compute_processes=peer,root_live_review_required=False)
    write(ROOT/'configs/admission.json', admission)
    done = subprocess.run(['python3', str(ROOT/'scripts/preflight.py')], env=environment(), capture_output=True, text=True, timeout=120)
    (ROOT/'audit/root_full_preflight.log').write_text(done.stdout+done.stderr)
    print(json.dumps(dict(preflight_exit=done.returncode, resource_sha256=sha(ROOT/'audit/resource_admission.json'))))
    if done.returncode: print(done.stdout+done.stderr)
    assert done.returncode == 0

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['deploy','kernel','admit']);args=parser.parse_args()
    globals()[args.phase]()
