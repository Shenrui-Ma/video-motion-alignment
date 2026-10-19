"""Copy small actual evidence over read-only SSH; no torch/CUDA or remote writes."""
from pathlib import Path
import base64, hashlib, json, subprocess, datetime

OUT = Path(__file__).resolve().parent
ROOTS = {
    'host41': ('H3_SERVER_B', '/data3/researcher/h3_runs', [
        'timing_ivebench_heldout_r64_20261018', 'timing_ivebench_remaining_r69_20261018']),
    'host9': ('H3_SERVER_A', '/data5/researcher/h3_runs', [
        'timing_ivebench_expanded_r73_20261018']),
}
REMOTE = r'''
from pathlib import Path
import base64, hashlib, json, sys, time
cfg=json.loads(sys.argv[1]); result={'capture_unix':time.time(),'files':{},'roots':{}}
def read(p, key):
    if not p.is_file(): return
    b=p.read_bytes()
    if len(b)>2500000: raise RuntimeError('unexpected large file '+str(p))
    result['files'][key]={'remote_path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'data_base64':base64.b64encode(b).decode()}
for name in cfg['names']:
    root=Path(cfg['base'])/name
    runtime=json.loads((root/'configs/runtime.json').read_text())
    result['roots'][name]={'runtime':runtime}
    patterns=['configs/graphs/*.json','configs/*contract*.json','configs/source_geometry.json','configs/input_hashes.json','configs/runtime_kernel_hashes.json','configs/cases.json','configs/queue.json','configs/runtime.json','logs/*_job.json','logs/*_history.json','logs/controller_state.json','audit/*_conditioning.json','audit/ACTUAL_INPUT_STREAM_CHECK.json','audit/router/*.json','analysis/postrun/**/PAIR_RUNTIME_GATE.json']
    seen=set()
    for pattern in patterns:
        for p in root.glob(pattern):
            if p in seen:continue
            seen.add(p);read(p,name+'/'+str(p.relative_to(root)))
    for sub in ['comfy_extras/nodes_minimax_h3.py','comfy/ldm/minimax/model.py','comfy/model_base.py','comfy/model_sampling.py','comfy/samplers.py']:
        read(Path(runtime['core'])/sub,'core/'+sub)
    for sub in ['extensions/H3EventAudit/__init__.py','extensions/H3PairAudit/__init__.py','extensions/H3TemporalRouter/core.py','extensions/H3TemporalRouter/layout.py']:
        read(root/sub,name+'/'+sub)
print(json.dumps(result))
'''

def main():
    manifest={'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hosts':{}}
    for host,(alias,base,names) in ROOTS.items():
        cmd=['ssh']
        if host=='host9': cmd+=['-J','H3_SERVER_B']
        cfg=json.dumps({'base':base,'names':names},separators=(',',':'))
        import shlex
        cmd+=['-o','BatchMode=yes','-o','ConnectTimeout=15',alias,'python3 - '+shlex.quote(cfg)]
        proc=subprocess.run(cmd,input=REMOTE,text=True,capture_output=True,check=True,timeout=60)
        data=json.loads(proc.stdout)
        for key,row in data['files'].items():
            raw=base64.b64decode(row.pop('data_base64'))
            assert hashlib.sha256(raw).hexdigest()==row['sha256']
            target=OUT/'actual'/host/key;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        manifest['hosts'][host]=data
    (OUT/'ACTUAL_EVIDENCE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print({h:len(v['files']) for h,v in manifest['hosts'].items()})

if __name__=='__main__':main()
