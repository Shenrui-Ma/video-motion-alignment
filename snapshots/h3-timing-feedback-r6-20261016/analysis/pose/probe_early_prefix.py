"""CPU-only prefix audit while sampling continues; no completed-run claim."""
from pathlib import Path
import json
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='1'

ROOT=Path('/data3/researcher/h3_runs/timing_feedback_r6_20261016')
BASE=Path('/data3/researcher/h3_runs/timing_target_path_r4_20261016')
RUN='r6_s05_feedback_retry1'
OLD_RUN='r4_s05_native_path_probe'


def sha(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    paths=[BASE/'audit/x0'/OLD_RUN,ROOT/'audit/x0'/RUN]
    if not all((p/'x0_step005.pt').is_file() and (p/'manifest.json').is_file() for p in paths):
        print(json.dumps({'status':'not_ready'}));return
    manifests=[json.loads((p/'manifest.json').read_text()) for p in paths]
    if not all(any(c.get('file')=='x0_step005.pt' for c in m['captures']) for m in manifests):
        print(json.dumps({'status':'capture_manifest_entry_pending'}));return
    import torch
    import hashlib
    torch.set_num_threads(1)
    file_hashes=[sha(p/'x0_step005.pt') for p in paths]
    values=[torch.load(p/'x0_step005.pt',map_location='cpu',weights_only=True) for p in paths]
    checks={'baseline_capture_complete':manifests[0]['status']=='complete',
            'run_ids':[m['run_id'] for m in manifests]==[OLD_RUN,RUN],
            'same_geometry':values[0]['metadata']['geometry']==values[1]['metadata']['geometry'],
            'index005':all(v['metadata']['step_zero_based']==5 for v in values)}
    tensors={}
    for key in ('video','audio'):
        raw_hashes=[hashlib.sha256(v[key].contiguous().view(torch.uint8).numpy().tobytes()).hexdigest() for v in values]
        match=[]
        for i,m in enumerate(manifests):
            entry=next(c for c in m['captures'] if c.get('file')=='x0_step005.pt')
            match.append(raw_hashes[i]==entry[key]['sha256']==values[i]['metadata'][key]['sha256'] and all(entry.get(k)==v for k,v in values[i]['metadata'].items()))
        tensors[key]={'bitwise_equal':torch.equal(values[0][key],values[1][key]),'actual_raw_sha256':raw_hashes,'capture_manifest_and_payload_match':all(match)}
        checks[key+'_exact']=tensors[key]['bitwise_equal'] and all(match) and raw_hashes[0]==raw_hashes[1]
    checks['snapshot_files_unchanged']=file_hashes==[sha(p/'x0_step005.pt') for p in paths]
    conditions=[json.loads((r/'audit'/(run+'_conditioning.json')).read_text()) for r,run in ((BASE,OLD_RUN),(ROOT,RUN))]
    noises=[json.loads((r/'audit'/(run+'_noise.json')).read_text()) for r,run in ((BASE,OLD_RUN),(ROOT,RUN))]
    for key in ('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout'):
        checks['actual_'+key]=conditions[0][key]==conditions[1][key]
    checks['pair_snapshot_actual']=conditions[0]['pair_snapshot']['actual']==conditions[1]['pair_snapshot']['actual']
    checks['noise_streams']=noises[0]['actual_noise_streams']==noises[1]['actual_noise_streams']
    checks['noise_signature']=noises[0]['signature']==noises[1]['signature']
    result={'status':'early_prefix_checked','passed':all(checks.values()),'checks':checks,'tensors':tensors,
            'file_sha256':file_hashes,'capture_status_at_read':[m['status'] for m in manifests],
            'scope':'Actual index5 video/audio and conditioning/noise only. New run is still in progress; final success, complete manifests, controller and final pose gates remain required.'}
    out=ROOT/'analysis/pose/replication/early_prefix_gate.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
