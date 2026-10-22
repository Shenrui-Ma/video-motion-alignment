"""Keep full pose payloads remote, verifying their exact SHA against the gate."""
from pathlib import Path
import hashlib
import json
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import consume_online as consumer
from common import bound, config, read, require, save, sha

source = ROOT / 'scripts/consume_online.py'
frozen = read(ROOT / 'FORMAL_CONSUMER_FREEZE.json')['files']
require(sha(source) == frozen['scripts/consume_online.py'], 'original collector changed')
original_compact = consumer.compact_remote
transfer_rows = []
original_fetch = consumer.fetch


def logged_fetch(path, destination, timeout=240):
    original_fetch(path, destination, timeout)
    transfer_rows.append({'remote_file': str(path), 'local_file': str(destination),
                          'payload_bytes': Path(destination).stat().st_size,
                          'sha256': sha(destination)})


def compact_and_verify(c):
    result = original_compact(c)
    code = r'''
import json, hashlib
from pathlib import Path
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
c=json.loads(Path(COMPACT).read_text())
gate_path=Path(PRODUCER)/'analysis/postrun/ONLINE_RUNTIME_GATE.json'
g=json.loads(gate_path.read_text());assert g['passed']
rows=[]
for m in c['counterfactual']['measurements']:
    i=m['physical_index'];response_path=Path(m['response_file'])
    assert sha(response_path)==m['response_sha256']
    r=json.loads(response_path.read_text());p=Path(r['pose']['file'])
    selection_path=p.parent/'adult_selection.json';s=json.loads(selection_path.read_text())
    raw=p.parent/'native.pose.json';expected=next(x for x in g['raw_filtered_pose_binding'] if x['index']==i)
    assert sha(p)==r['pose']['sha256']==s['filtered_pose_sha256']==expected['filtered_sha256']
    assert sha(raw)==s['raw_pose_sha256']==expected['raw_sha256']
    assert s['rejected_frames']==expected['rejected_frames']
    rows.append({'index':i,'raw':{'file':str(raw),'sha256':sha(raw),'bytes':raw.stat().st_size},
      'filtered':{'file':str(p),'sha256':sha(p),'bytes':p.stat().st_size},
      'selection_sha256':sha(selection_path),'response_sha256':sha(response_path),
      'rejected_frames':s['rejected_frames']})
assert [x['index'] for x in rows]==list(range(20))
print(json.dumps({'passed':True,'gate_sha256':sha(gate_path),'compact_sha256':sha(COMPACT),
 'full_pose_payloads_remain_remote':True,'rows':rows}))
'''
    code = 'COMPACT=' + repr(str(result)) + '\nPRODUCER=' + repr(c['producer_remote']) + '\n' + code
    raw = subprocess.check_output(['ssh', '-o', 'BatchMode=yes', c['host'],
        shlex.join(['env', 'CUDA_VISIBLE_DEVICES=', 'PYTHONDONTWRITEBYTECODE=1', c['remote_python'], '-c', code])], timeout=120)
    proof = json.loads(raw)
    target = ROOT / 'audit/REMOTE_POSE_HASH_VERIFIED.json'
    if target.exists():
        require(read(target) == proof, 'remote pose evidence changed')
    else:
        save(target, proof)
    consumer.remote_pose_proof = proof
    return result


# Only transfer selection changes: every raw/filtered identity check still runs.
text = source.read_text()
old = "for kind in ('decode','pose'):get(res[kind]['file'],folder+'/'+kind+'.json',res[kind]['sha256'])"
new = "for kind in ('decode',):get(res[kind]['file'],folder+'/'+kind+'.json',res[kind]['sha256'])"
require(text.count(old) == 1, 'decode/pose transfer call changed')
text = text.replace(old, new)
old = "get(filtered.parent/'native.pose.json',folder+'/raw.pose.json',selection['raw_pose_sha256']);"
new = "remote_row=remote_pose_proof['rows'][i];require(remote_row['raw']['sha256']==selection['raw_pose_sha256'] and remote_row['filtered']['sha256']==res['pose']['sha256'] and remote_row['selection_sha256']==sha(stage/folder/'adult_selection.json'),'remote pose identity differs');"
require(text.count(old) == 1, 'raw pose transfer call changed')
text = text.replace(old, new)
old = "'tensor_payloads_transferred':False,'GPU_started':False})"
new = "'remote_only_pose_evidence':bound(ROOT/'audit/REMOTE_POSE_HASH_VERIFIED.json'),'tensor_payloads_transferred':False,'GPU_started':False})"
require(text.count(old) == 1, 'collection receipt changed')
text = text.replace(old, new)
import ast
tree = ast.parse(text)
function = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'collect')
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), consumer.__dict__)
consumer.compact_remote = compact_and_verify
consumer.fetch = logged_fetch

if __name__ == '__main__':
    start = time.time()
    consumer.collect(config()['expected_attempt'])
    save(ROOT / 'audit/ACTUAL_INTAKE_TRANSFER.json', {
        'schema': 'r138-minimum-actual-transfer-v1', 'adapter': bound(Path(__file__)),
        'original_collector': bound(source), 'original_freeze': bound(ROOT / 'FORMAL_CONSUMER_FREEZE.json'),
        'files': transfer_rows, 'retrieved_file_payload_bytes': sum(x['payload_bytes'] for x in transfer_rows),
        'note': 'File payload only; not network-byte metering. SSH/protocol and metadata-read bytes are not included.',
        'pose_hash_evidence': bound(ROOT / 'audit/REMOTE_POSE_HASH_VERIFIED.json'),
        'started_unix': start, 'ended_unix': time.time(), 'GPU_started': False})
    print(json.dumps(consumer.render(), ensure_ascii=False))
