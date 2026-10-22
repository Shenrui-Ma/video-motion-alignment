"""One CPU pass over actual completed pairs; all GPU trackers remain root-owned."""
import json
import os
import time
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import *
from collect_pair import collect
from prepare_pair import prepare
from score_one import score

def replace_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)

def pass_once():
    verify_runtime()
    producer=Path(read(ROOT/'configs/paths.json')['producer_remote41'])
    report={'schema':'r69-cpu-consumer-progress-v1','created_unix':time.time(),'rows':[],'gpu_started':False,'fixed_denominator':5,'prior_0210':'retained'}
    for source in PAIRS:
        row={'source':source,'gate':'PENDING','prepared':False,'scores':{}}
        receipt=producer/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json'
        if not receipt.is_file():
            histories=[producer/'logs'/f'r69_{source}_seed2026101701_{m}_history.json' for m in METHODS]
            row['producer_gate_needed']=all(p.is_file() and read(p).get('status',{}).get('completed') is True for p in histories)
            report['rows'].append(row);continue
        with cpu_lock():
            if not (ROOT/'incoming'/source/'COLLECTION.json').exists():collect(producer,source)
            row['gate']='PASSED'
            if not (ROOT/'prepared'/source/'READY.json').exists():prepare(source,'ffmpeg','ffprobe')
            row['prepared']=True
        row['root_tracking_needed']=[]
        for method in ('source',)+METHODS:
            if not (ROOT/'tracks'/method/source/'attempt1/R69_BINDING.json').exists():row['root_tracking_needed'].append(method)
        for method in METHODS:
            result=ROOT/'results'/source/f'{method}_source1_target1.json'
            if not result.exists() and not any(m in row['root_tracking_needed'] for m in ('source',method)):
                with cpu_lock():score(source,method)
            row['scores'][method]=read(result)['motion_fidelity'] if result.exists() else None
        report['rows'].append(row)
    report['all_four_prepared']=all(x['prepared'] for x in report['rows'])
    report['all_four_scored']=all(all(x.get('scores',{}).get(m) is not None for m in METHODS) for x in report['rows'])
    replace_json(ROOT/'audit/PROGRESS.json',report)
    return report

if __name__=='__main__':
    try:
        result=pass_once();print(json.dumps(result))
    except BlockingIOError:
        raise SystemExit(75)
    except Exception as error:
        replace_json(ROOT/'audit/CONSUMER_FAILURE.json',{'unix':time.time(),'error_type':type(error).__name__,'error':str(error)})
        raise
