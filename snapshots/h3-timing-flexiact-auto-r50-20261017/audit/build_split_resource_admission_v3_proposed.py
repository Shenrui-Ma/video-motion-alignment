"""Root-only certificate after actual GPU0 decoder proof; no CUDA or service launch."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
R=Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017')
MAIN='GPU-REDACTED';DECODER='GPU-REDACTED'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root-approved',action='store_true');args=parser.parse_args()
    if not args.root_approved:raise RuntimeError('root resource review required')
    destination=R/'audit/resource_admission_v3.json'
    if destination.exists():raise FileExistsError(destination)
    manifest=read(R/'deploy_manifest.json')
    for rel,row in manifest['files'].items():assert sha(R/rel)==row['sha256'],rel
    profile=R/'configs/engineering_v2/allocator_profile_158.json';p=read(profile)
    assert p['passed'] and p['no_empty_cache_called'] and p['no_simultaneous_oracle_output']
    c=p['cases'][0];route=max(c['native_to_full_reserved_increment_bytes'],c['native_to_full_nvml_retained_increment_bytes'])+512*1024**2
    resource=Path('/data5/researcher/h3_runs/timing_flexiact_native_r49_20261017/logs/resources.jsonl')
    assert sha(resource)=='6a6e432ac096a1af0f3ee40c3c8016eecc577f597b3ad7b97cf822e8317fc9b9'
    native=max(int(json.loads(line)['sample'].split(',')[1]) for line in resource.read_text().splitlines() if line.strip())*1024**2
    kp=R/'configs/engineering_v2/previous_kernel_gate.json';dp=R/'audit/known_endpoint_158_split_v3_gate.json';d=read(dp)
    assert d['passed'] and all(d['checks'].values()) and d['GPU_admission']['uuid']==DECODER
    device={}
    for uuid in (MAIN,DECODER):
        text=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,memory.total,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()
        fields=[x.strip() for x in text.split(',')];assert fields[0]==uuid and len(fields)==5
        assert int(fields[2])<=1024 and int(fields[3])>=45000 and int(fields[4])==0
        assert not subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()
        device[uuid]={'csv':text,'total_bytes':int(fields[1])*1024**2}
    record={'schema':'r50-root-two-GPU-resource-admission-v3','root_approved':True,'observed_unix':time.time(),'main_gpu_uuid':MAIN,'decoder_gpu_uuid':DECODER,'protocol_sha256':sha(R/'configs/protocol.json'),'engineering_revision_sha256':sha(R/'configs/engineering_revision_v3.json'),'kernel_gate_sha256':sha(kp),'decoder_gate_sha256':sha(dp),'main_native_peak_sampled_bytes':native,'routing_increment_bound_bytes':route,'main_margin_bytes':1024**3,'main_total_memory_bytes':device[MAIN]['total_bytes'],'main_estimated_peak_bytes':native+route+1024**3,'decoder_peak_reserved_bytes':d['decode']['max_memory_reserved_bytes'],'decoder_total_memory_bytes':device[DECODER]['total_bytes'],'required_free_before_decoder_mib':45000,'scope':'GPU3 main model; GPU0 isolated full158 decoder; maximum2 owned GPUs','devices':device,'evidence':[{'file':str(f),'sha256':sha(f)} for f in (profile,resource,kp,dp,Path(__file__))],'interpretation':'Sampled Native occupancy plus actual largest-layout retained increment and explicit margins is an engineering capacity estimate; runtime dedicated decoder idle/ownership checks remain mandatory.'}
    assert record['main_estimated_peak_bytes']<=record['main_total_memory_bytes']
    with destination.open('x') as handle:handle.write(json.dumps(record,indent=2)+'\n')
    import sys
    sys.path.insert(0,str(R/'scripts'))
    import prelaunch_gates
    print(json.dumps({'resource_sha256':sha(destination),'gates':prelaunch_gates.check(R)}))
if __name__=='__main__':main()
