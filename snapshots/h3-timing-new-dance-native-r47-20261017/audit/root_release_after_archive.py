from pathlib import Path
import json, hashlib, time, urllib.request

r = Path('/data5/researcher/h3_runs/timing_new_dance_native_r47_20261017')
runs = ['r47_source_10264579_seed2026101701_native', 'r47_source_6980766_seed2026101701_native']

def read(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, data):
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    tmp.replace(p)

owner = read(r / 'processes/service.json')
assert owner['pid'] == 56389 and owner['identity']['uid'] == 1016
assert owner['identity']['start_ticks'] == '2624807484'
proc = Path('/proc') / str(owner['pid'])
assert proc.stat().st_uid == 1016
assert proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19] == '2624807484'
assert sha(proc / 'cmdline') == '9ccb71006bccce215b60d0c10d9041d32d61012b41d7f22f5a63f37f49185472'
arc = r / 'analysis/postrun/captured/batch'
gp = arc / 'RUN_GATE.json'
gate = read(gp)
receipt = read(r / 'analysis/postrun/archive_receipts/batch.json')
assert gate['passed'] is True and gate['run_id'] == 'batch' and gate['owner'] == owner
assert gate['runs'] == runs and receipt['owner'] == owner
assert receipt['run_gate_sha256'] == sha(gp)
assert receipt['inventory_sha256'] == sha(arc / 'FILE_INVENTORY.json')
with urllib.request.urlopen('http://127.0.0.1:8509/queue', timeout=10) as response:
    q = json.load(response)
assert not q['queue_running'] and not q['queue_pending']
controller = read(r / 'logs/controller_state.json')
assert controller['status'] == 'resident_hold' and controller['completed'] == runs
qp = r / 'configs/queue.json'
queue = read(qp)
assert queue['finalize'] is False
save(r / 'audit/root_release_request.json', {
    'pid': owner['pid'], 'owner': owner['identity'], 'gate_file': str(gp),
    'gate_sha256': sha(gp), 'unix': time.time(), 'empty_queue_verified': True,
})
queue['finalize'] = True
save(qp, queue)
print(json.dumps({'release_requested': True, 'pid': owner['pid'], 'gate_sha256': sha(gp)}))
