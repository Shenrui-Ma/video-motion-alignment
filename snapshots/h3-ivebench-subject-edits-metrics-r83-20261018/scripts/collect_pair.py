"""Collect verified actual output evidence transactionally; large tensor files stay at producer."""
import argparse,os,shutil,tempfile
from common import *

def validate_gate(gate,source):
    e=entry(source)['input_protocol'];count,total=e['effective_frame_count'],e['h3_frame_count']
    require(gate.get('schema')=='r83-paired-runtime-gate-v1' and gate.get('passed') is True and gate.get('source_id')==source and gate.get('prompt_version')=='P1-local-v1','actual R83 gate differs')
    checks=gate.get('checks',{})
    require(checks and all(v is True for v in checks.values()),'actual gate contains unsuccessful check')
    for key in ('producer_seal','actual_runtime_device','actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal'):
        require(checks.get(key) is True,'missing actual check: '+key)
    require(set(gate['runs'])==set(METHODS),'two methods required')
    for method,run in gate['runs'].items():
        require(run['run_id']==run_id(source,method) and run['valid_frames']==count and run['NFE']==run['Euler_updates']==20 and run['routed_blocks']==(0 if method=='native' else 450),'actual run/count/route differs')
        p=run['video']['properties']
        require((p['width'],p['height'],int(p['nb_read_frames']),p['avg_frame_rate'])==(1312,736,total,'24/1') and run['evaluation_crop_xywh']==[16,8,1280,720],'actual geometry differs')
    return gate

def validate_intake(out,source):
    collection=read(out/'COLLECTION.json')
    require(collection['source']==source and collection['fixed_denominator']==7,'intake source differs')
    for name,digest in collection['files'].items():
        require(Path(name).name==name and sha(out/name)==digest,'intake evidence changed: '+name)
    return validate_gate(read(out/'PAIR_RUNTIME_GATE.json'),source)

def collect(producer,source):
    producer=Path(producer).resolve();receipt=producer/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json'
    gate=validate_gate(read(receipt),source)
    require(sha(producer/'deploy_manifest.json')==sha(ROOT/'configs/PRODUCER_SEAL.json'),'producer seal differs from frozen consumer binding')
    out=ROOT/'incoming'/source
    if out.exists():
        validate_intake(out,source);require(sha(out/'PAIR_RUNTIME_GATE.json')==sha(receipt),'existing intake bound to different actual gate');return out
    out.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+source+'.',dir=out.parent))
    try:
        shutil.copy2(receipt,stage/'PAIR_RUNTIME_GATE.json')
        for method in METHODS:
            run=gate['runs'][method];video=Path(run['video']['file'])
            require(video.resolve().is_relative_to(producer/'output') and not video.is_symlink() and sha(video)==run['video']['sha256'],'video outside producer or changed')
            shutil.copy2(video,stage/(method+'.mp4'))
            for kind,folder,key in [('history','logs','history_sha256'),('job','logs','job_sha256'),('router','audit/router','router_file_sha256')]:
                name=run['run_id']+('.json' if kind=='router' else '_'+kind+'.json');path=producer/folder/name
                require(sha(path)==run[key],'actual evidence changed: '+kind);shutil.copy2(path,stage/(method+'_'+kind+'.json'))
            graph=producer/'configs/graphs'/(run['run_id']+'.json');shutil.copy2(graph,stage/(method+'_graph.json'))
        save(stage/'COLLECTION.json',{'schema':'r83-portable-actual-pair-v1','source':source,'fixed_denominator':7,'producer':str(producer),'receipt':bound(receipt),'files':{p.name:sha(p) for p in stage.iterdir() if p.is_file()}})
        validate_intake(stage,source);os.rename(stage,out)
    except BaseException:
        # Uncommitted evidence remains available in its unique staging directory.
        raise
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',choices=PAIRS,required=True);p.add_argument('--producer-root',type=Path,required=True);a=p.parse_args();verify_runtime();print(collect(a.producer_root,a.source))
