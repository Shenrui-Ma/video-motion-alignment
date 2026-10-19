"""Read a root-owned guide/skip decision and preserve its exact Native binding."""
from common import *
from remote import read_paths

def validate_decision(value, source, gate, gate_sha):
    p=info(source)
    require(value.get('schema')=='r117-root-native-decision-v1' and value.get('root_reviewed') is True,'actual root decision missing')
    require(value.get('choice') in ('guide','skip') and bool(str(value.get('reason','')).strip()),'actual choice/reason missing')
    binding=value['binding'];r=gate['runs']['native']
    require(binding['source_id']==source and binding['native_run']==p['run_id'],'decision source/run differs')
    require(binding['native_gate_sha256']==gate_sha and binding['runtime_profile_sha256']==config()['producer_runtime_sha256'],'decision gate/runtime differs')
    require(binding['service_owner']==gate['service_owner'] and binding['video_sha256']==r['video']['sha256'],'decision actual Native differs')
    return value

def collect(source):
    validate_static();gate=verify_intake(source);gate_sha=sha(ROOT/'incoming'/source/'NATIVE_RUNTIME_GATE.json')
    path=Path(config()['producer_remote'])/'audit/decisions'/f'{source}.json'
    value=read_paths([str(path)],missing_ok=True)[str(path)]
    if value is None:return {'status':'PENDING_DECISION','source_id':source}
    validate_decision(value['value'],source,gate,gate_sha)
    dest=ROOT/'audit/root_decisions'/source/'ROOT_DECISION.json'
    receipt={'source_id':source,'remote':str(path),'remote_sha256':value['sha256'],'decision':value['value'],
        'native_collection':bound(ROOT/'incoming'/source/'COLLECTION.json'),'GPU_started':False}
    if dest.exists():require(read(dest)==receipt,'recorded root decision changed')
    else:save(dest,receipt)
    return bound(dest)

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--source',choices=SOURCES,required=True);args=a.parse_args()
    print(json.dumps(collect(args.source)))
