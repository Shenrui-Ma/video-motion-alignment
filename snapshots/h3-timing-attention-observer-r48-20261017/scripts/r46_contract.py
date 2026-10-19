"""Fixed two-state queue and byte-bound graph; no encoder inputs."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ORDER = ['r48_bad_index4', 'r48_normal_index4']


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def require(ok, message):
    if not ok:raise ValueError(message)


def identity_schema(value, *, external=False):
    require(isinstance(value, dict) and type(value.get('uid')) is int and
            type(value.get('start_ticks')) is str and value['start_ticks'].isdigit(), 'identity start_ticks must be decimal string')
    key='cmdline_sha256' if external else 'cmdline'
    require(isinstance(value.get(key),str) and bool(value[key]), 'identity command missing')
    if external:require(len(value[key])==64 and all(c in '0123456789abcdef' for c in value[key]), 'identity command SHA')
    return value


def registry(root=ROOT):
    root=Path(root); queue=read(root/'configs/queue.json'); bindings=read(root/'configs/job_bindings.json')
    require(queue.get('jobs') == ORDER and type(queue.get('finalize')) is bool and set(bindings)==set(ORDER), 'fixed two-job queue changed')
    return bindings, ORDER.copy()


def validate_job(name, root=ROOT):
    root=Path(root);bindings,_=registry(root);require(name in bindings,'unknown state job')
    row=bindings[name]; path=root/'configs/graphs'/f'{name}.json'
    require(sha(path)==row['graph_sha256'],'submitted graph bytes changed')
    graph=read(path)
    require(set(graph)=={'1','41','60'} and graph['60']['class_type']=='H3AttentionStateProbe' and
            graph['60']['inputs']=={'model':['41',0],'state_id':row['label']},'report-only graph changed')
    require(graph['1']=={'class_type':'UNETLoader','inputs':{'unet_name':'minimax_h3_ref2va_pruned_int8_convrot.safetensors','weight_dtype':'default'}} and
            graph['41']=={'class_type':'MiniMaxH3SigmaShift','inputs':{'model':['1',0],'shift_video':12.0,'shift_audio':3.0}},'model/shift graph changed')
    protocol=root/'configs/SCIENCE_PROTOCOL.json';sources=root/'configs/sources.json'
    require(row['protocol_sha256']==sha(protocol) and row['sources_sha256']==sha(sources),'state protocol binding changed')
    return row


def prepare_loader_inputs(name,root=ROOT):
    # Actual Source.load verifies every archived tensor immediately before use.
    return validate_job(name,root)
