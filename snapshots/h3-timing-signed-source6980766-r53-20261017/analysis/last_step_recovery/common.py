"""Bindings for a separately labelled recovery of the failed R53 final observation."""
import hashlib,importlib.util,json,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
PRODUCER=HERE.parents[1]
REMOTE=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
ARCHIVE=PRODUCER/'analysis/postrun/captured_failure/step019_admission'
RUN='r53_source_6980766_seed2026101701_auto'
INVENTORY_SHA='a0884cbc2530262f934c9019af274a332cc695ef462f5de0ef1294be6903ed98'
REQUEST_REL='audit/observations/step019_dbf9511bd1fa4c5981ad63ad39be7647/request.json'
REQUEST_SHA='347387e1ef278f0b3d52b75fb8abd6410f79243bfc671e4e7651e99156c701d2'
ENDPOINT_REL='audit/counterfactual/'+RUN+'_snapshots/step019_native.pt'
ENDPOINT_SHA='04d27487829c6a619f16603dae9ff925fb765a58344c08245995e93229d6b19e'
AUDIT_REL='audit/counterfactual/'+RUN+'.json'
AUDIT_SHA='49af71c55954a0b14d800692ec2bfc7e79704d4a210f80114b90aa2749605afd'
PRODUCER_MANIFEST_SHA='6576342c90a281bb59be584987a222b4dd3ad0affeb673ca8a21bf86915c5527'
X19_SHA='a69a93a41a129fbbdc987801d8d8b394498675706811592b7666f7ad33592cb9'
REPLAY_SHA='5e62f0921811aaafa4dca112c193ff7d2673915ac221008c78ae3f0ad27d6a1e'
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def read(path):return json.loads(Path(path).read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def write_new(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    return sha(path)
def relative_original(path):
    return Path(path).relative_to(REMOTE).as_posix()
def inventory():
    path=ARCHIVE/'FILE_INVENTORY.json';require(sha(path)==INVENTORY_SHA,'failure inventory changed');return read(path)
def archived(rel,items=None):
    items=items or inventory();require(rel in items,'path outside actual failure inventory')
    path=ARCHIVE/rel;require(sha(path)==items[rel]['sha256'],'failure archive bytes changed: '+rel);return path

def frozen_runtime():
    path=PRODUCER/'deploy_manifest.json';require(sha(path)==PRODUCER_MANIFEST_SHA,'frozen R53 manifest differs')
    manifest=read(path)
    for rel,row in manifest['files'].items():require(sha(PRODUCER/rel)==row['sha256'],'frozen producer changed:'+rel)
    sys.path.insert(0,str(PRODUCER/'scripts'))
    from observer_import import t
    t.bindings(external=False)
    return t

def original_request(check_endpoint=True):
    items=inventory();path=archived(REQUEST_REL,items);require(sha(path)==REQUEST_SHA,'wrong failed request')
    request=read(path)
    require(request['run_id']==RUN and request['physical_index']==19 and request['branch']=='native' and request['nfe_index']==31,'wrong recovery endpoint')
    require(request['endpoint_file_sha256']==ENDPOINT_SHA and relative_original(request['endpoint_file'])==ENDPOINT_REL,'endpoint binding differs')
    require(request['sigma_next']==0 and len(request['full_grid'])==21 and request['sigma']==request['full_grid'][19],'final grid differs')
    if check_endpoint:
        archived(ENDPOINT_REL,items)
        require(sha(request['endpoint_file'])==ENDPOINT_SHA,'original endpoint no longer matches archived copy')
    return request

def load_live():
    frozen_runtime()
    path=PRODUCER/'scripts/decode_live_child.py'
    spec=importlib.util.spec_from_file_location('r53_frozen_live_decoder_recovery',path)
    live=importlib.util.module_from_spec(spec);spec.loader.exec_module(live)
    return live

def assert_peers(uuid,registry,processes,lookup,uid):
    require(uuid.startswith('GPU-'),'exact recovery GPU UUID required')
    require(registry['schema']=='r53-recovery-root-admission-v1' and registry['root_approved'] is True and registry['gpu_uuid']==uuid,'root recovery admission differs')
    allowed={r['identity']['pid']:r for r in registry['permitted_peers']}
    owned=set()
    for row in processes:
        require(row['gpu_uuid']!=uuid,'recovery GPU has active compute')
        identity=lookup(row['pid'])
        if identity and identity['uid']==uid:
            require(row['pid'] in allowed and allowed[row['pid']]['identity']==identity and allowed[row['pid']]['gpu_uuid']==row['gpu_uuid'],'unregistered or reused own peer')
            owned.add(row['gpu_uuid'])
    require(len(owned|{uuid})<=2,'recovery exceeds two owned GPUs')
    return sorted(owned|{uuid})
