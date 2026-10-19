"""Freeze the consumer after checking the sealed two-operator producer and old Native."""
import argparse,copy,shutil
from pathlib import Path
from common import ROOT,ARMS,read,save,sha,require,relative,verify_graphs


def bind(expected):
    require(not (ROOT/'CONSUMER_FREEZE.json').exists(),'preserve the established consumer freeze')
    cfg=copy.deepcopy(read(ROOT/'configs/contract.draft.json'));producer=Path(cfg['producer_local'])
    require(sha(producer/'deploy_manifest.json')==expected,'unexpected producer seal')
    seal=read(producer/'deploy_manifest.json')
    for rel,item in seal['files'].items():
        require(sha(producer/relative(rel))==item['sha256'],'producer changed after sealing: '+rel)
    for section in ('historical_media','historical_evidence'):
        for name,item in cfg[section].items():
            require(sha(item['file'])==item['sha256'],'historical binding changed: '+name)
    historical=read(producer/'design/HISTORICAL_NATIVE.json')
    require(historical['run_id']==cfg['native_run_id'] and
        historical['actual_gate_sha256']==cfg['historical_evidence']['R96_NATIVE_GATE']['sha256'] and
        historical['run']['video']['sha256']==cfg['historical_media']['native']['sha256'] and
        historical['same_host_strict_comparison'] is False,'existing Native differs')
    require(sha(producer/'design/HISTORICAL_NATIVE_GATE.json')==historical['actual_gate_sha256'],
            'existing Native actual gate differs')
    runtime=read(producer/'configs/runtime.json')
    require(runtime['remote_root']==cfg['producer_remote'] and runtime['host']==cfg['host'],
            'new producer runtime differs')
    graphs={a:read(producer/'configs/graphs'/(cfg['runs'][a]+'.json')) for a in ARMS}
    verify_graphs(graphs,cfg)
    cfg.update(schema='r115-four-role-consumer-v1',status='CPU_FROZEN_WAIT_ACTUAL_OUTPUT',
        producer_seal_sha256=expected,producer_runtime_sha256=sha(producer/'configs/runtime.json'),
        historical_native_sha256=sha(producer/'design/HISTORICAL_NATIVE.json'),
        historical_native_gate_sha256=sha(producer/'design/HISTORICAL_NATIVE_GATE.json'))
    files={'producer_deploy_manifest.json':producer/'deploy_manifest.json',
        'producer_runtime.json':producer/'configs/runtime.json',
        'producer_scientific_contract.json':producer/'configs/scientific_contract.json',
        'HISTORICAL_NATIVE.json':producer/'design/HISTORICAL_NATIVE.json',
        'HISTORICAL_NATIVE_GATE.json':producer/'design/HISTORICAL_NATIVE_GATE.json'}
    files.update({'graph_'+a+'.json':producer/'configs/graphs'/(cfg['runs'][a]+'.json') for a in ARMS})
    for name,source in files.items():
        dest=ROOT/'configs'/name;require(not dest.exists(),'existing partial binding requires inspection: '+name)
        shutil.copy2(source,dest)
    save(ROOT/'configs/contract.json',cfg)
    frozen={str(p.relative_to(ROOT)):sha(p) for folder in ('scripts','configs','tests')
        for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    diagnostic=ROOT/'audit/match_geometry_review'
    for name in ('diagnostic.py','test_diagnostic.py','DESIGN.json','SOURCE_PERSON_TRACK_SUBSET.json','frame0_track_ids.json'):
        p=diagnostic/name;frozen[str(p.relative_to(ROOT))]=sha(p)
    save(ROOT/'CONSUMER_FREEZE.json',{'schema':'r115-independent-consumer-freeze-v1','files':frozen})
    print({'consumer_freeze_sha256':sha(ROOT/'CONSUMER_FREEZE.json'),'producer_seal_sha256':expected,
           'files':len(frozen),'GPU_started':False})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-producer-seal',required=True);args=p.parse_args();bind(args.expected_producer_seal)
