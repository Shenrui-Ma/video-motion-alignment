"""Bind the independently checked producer package after its final deployment seal."""
import copy
import shutil
from pathlib import Path
from common import ROOT,ARMS,read,save,sha,require,verify_graphs


def bind():
    require(not (ROOT/'CONSUMER_FREEZE.json').exists(),'preserve the established consumer freeze')
    cfg=copy.deepcopy(read(ROOT/'configs/contract.draft.json'));producer=ROOT.parent/Path(cfg['producer_local']).name
    seal=read(producer/'deploy_manifest.json')
    for rel,item in seal['files'].items():
        require(sha(producer/rel)==item['sha256'],'producer changed after sealing: '+rel)
    require(sha(producer/'CPU_PREPARATION_SEAL.json')==cfg['producer_cpu_seal']['sha256'],'CPU scientific package differs')
    for section in ('historical_media','historical_evidence'):
        for name,item in cfg[section].items():
            require(sha(item['file'])==item['sha256'],'historical binding changed: '+name)
    fixed=read(producer/'design/R107_FIXED_BINDING.json')
    require(fixed['gate_sha256']==cfg['historical_evidence']['R107_GATE']['sha256'] and
            fixed['video_sha256']==cfg['historical_media']['fixed']['sha256'] and
            fixed['graph_sha256']==cfg['historical_evidence']['R107_GRAPH']['sha256'],'historical R107 differs')
    old=read(ROOT.parent/'h3-ive-long0174-guidance-metrics-r107-20261019/configs/contract.json')
    runtime=read(producer/'configs/runtime.json')
    require(runtime['remote_root']==cfg['producer_remote'],'producer remote root differs')
    cfg.update(schema='r112-five-role-consumer-v1',status='CPU_FROZEN_WAIT_ACTUAL_OUTPUT',
        producer_seal_sha256=sha(producer/'deploy_manifest.json'),producer_runtime_sha256=sha(producer/'configs/runtime.json'),
        fixed_binding=fixed,fixed_producer_remote=old['producer_remote'])
    graphs={a:read(producer/'configs/graphs'/(cfg['runs'][a]+'.json')) for a in ARMS}
    verify_graphs(graphs,read(producer/'design/R107_GRAPH.json'),cfg)
    files={'producer_deploy_manifest.json':producer/'deploy_manifest.json','producer_runtime.json':producer/'configs/runtime.json',
           'R107_GRAPH.json':producer/'design/R107_GRAPH.json','R107_FIXED_BINDING.json':producer/'design/R107_FIXED_BINDING.json'}
    files.update({'graph_'+a+'.json':producer/'configs/graphs'/(cfg['runs'][a]+'.json') for a in ARMS})
    for name,source in files.items():
        dest=ROOT/'configs'/name;require(not dest.exists(),'existing partial bind needs inspection: '+name);shutil.copy2(source,dest)
    save(ROOT/'configs/contract.json',cfg)
    frozen={str(p.relative_to(ROOT)):sha(p) for folder in ('scripts','configs','tests')
            for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    save(ROOT/'CONSUMER_FREEZE.json',{'schema':'r112-independent-consumer-freeze-v1','files':frozen})
    print({'consumer_freeze_sha256':sha(ROOT/'CONSUMER_FREEZE.json'),'producer_seal_sha256':cfg['producer_seal_sha256'],
           'files':len(frozen),'GPU_started':False})

if __name__=='__main__':
    bind()
