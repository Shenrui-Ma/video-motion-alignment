"""CPU-only provenance gate and unchanged-method freeze for existing seed2."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import datetime,hashlib,importlib.util,json,shutil
import torch
HERE=Path(__file__).resolve().parent
BASE=HERE.parent
R2=BASE.parents[1]
OLD=R2.parent/'h3-timing-autoresearch-20261016'
CROSS=BASE/'cross_identity'
STEMS=('x0_step005','x0_step010','x0_step015','x0_step019','sampler_final')
FIELDS=('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion',
        'conditioning_embedding','token_tags','target_latent_shapes','packed_layout')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def import_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def scientific(x):
    if isinstance(x,dict):return {k:scientific(v) for k,v in x.items() if k!='tensor_file'}
    if isinstance(x,list):return [scientific(v) for v in x]
    return x


def main():
    torch.set_num_threads(1)
    helper=import_file('frozen_bind',CROSS/'freeze_inputs.py')
    prior=json.loads((CROSS/'PROTOCOL.json').read_text())
    hashes=json.loads((HERE/'remote_file_hashes.json').read_text())
    provenance=HERE/'provenance';provenance.mkdir(exist_ok=True)
    input_audit={};conditions={};noises={};runs={};captures={}
    for mode in ('native','mass'):
        directory=HERE/'inputs'/mode
        for name,info in hashes[mode].items():
            if sha(directory/name)!=info['sha256']:raise RuntimeError('Remote/local file mismatch: '+mode+'/'+name)
        manifest=json.loads((directory/'manifest.json').read_text())
        if manifest['status']!='complete' or manifest['callback_count']!=20 or manifest['seed']!=2026101312:
            raise RuntimeError('Capture not complete or wrong seed')
        if manifest['capture_steps_zero_based']!=[5,10,15,19]:raise RuntimeError('Wrong capture steps')
        captures[mode]=manifest
        audit=OLD/'analysis/transfer_runtime_evidence/audit'
        condition=audit/f's05_full_seed2_{mode}_x0_conditioning.json'
        noise=audit/f's05_full_seed2_{mode}_x0_noise.json'
        for path in (condition,noise):
            shutil.copy2(path,provenance/path.name)
            input_audit[path.name]={'source_path':str(path),'sha256':sha(path)}
        conditions[mode]=json.loads(condition.read_text());noises[mode]=json.loads(noise.read_text())
        indexed={v['file']:v for v in manifest['captures']}
        indexed[manifest['final_sampler_result']['file']]=manifest['final_sampler_result']
        for stem in STEMS:
            path=directory/(stem+'.pt');item=helper.bind(path,True)
            data=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
            if item['metadata']['seed']!=2026101312:raise RuntimeError('Snapshot seed mismatch')
            record=indexed[path.name]
            for name in ('video','audio'):
                actual=helper.tensor_info(data[name])
                if any(record[name][k]!=v for k,v in actual.items()):raise RuntimeError('Capture manifest raw tensor mismatch')
            item['capture_manifest']={'path':str(directory/'manifest.json'),'sha256':sha(directory/'manifest.json')}
            item['remote_file']=hashes[mode][path.name]
            runs[mode+'/'+stem]=item
    baseline_path=OLD/'audit/s05_full_seed1_native_x0_conditioning.json'
    baseline=json.loads(baseline_path.read_text())
    checks={}
    for field in FIELDS:
        checks[field+'_native_equals_mass']=scientific(conditions['native'][field])==scientific(conditions['mass'][field])
        checks[field+'_equals_seed1']=scientific(conditions['native'][field])==scientific(baseline[field])
    checks['native_mass_noise_streams_equal']=noises['native']['actual_noise_streams']==noises['mass']['actual_noise_streams']
    checks['native_mass_capture_packed_noise_equal']=captures['native']['noise']==captures['mass']['noise']
    checks['seed_is_2026101312']=all(n['signature']['seed']==2026101312 for n in noises.values())
    for field in ('geometry','target_latent_shapes','sigmas_video','sampler','audio_scale','video_latent_scale_factor','normalization_stage'):
        checks['capture_'+field+'_equal']=captures['native'][field]==captures['mass'][field]
    reference=helper.bind(R2/'analysis/latent_observer/reference_video_vae.pt',False)
    checks['actual_reference_raw_tensor_matches']=all(all(c['native_vae_calls'][1]['latent'][k]==v for k,v in reference['tensor'].items()) for c in conditions.values())
    if not all(checks.values()):raise RuntimeError(checks)
    input_gate=dict(checks=checks,all_pass=True,audit_sources=input_audit,
                    baseline_source={'path':str(baseline_path),'sha256':sha(baseline_path)},
                    excluded_metadata='Only tensor_file location removed; raw hashes, geometry, timestamps/tags/layout compared.',
                    CPU_only=True,CUDA_initialized=torch.cuda.is_initialized())
    (HERE/'INPUT_GATE.json').write_text(json.dumps(input_gate,indent=2)+'\n')
    protocol={k:prior[k] for k in ('methods','method_source','method_source_sha256','reject_rules','time_geometry','lag_search_frames','sign','interpolation','score','normalization','regions','pose_comparison')}
    protocol.update(schema='h3-seed2-phase-observer-necessity-v1',frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_protocol_sha256=sha(CROSS/'PROTOCOL.json'),input_gate_sha256=sha(HERE/'INPUT_GATE.json'),
        loader_path=str(CROSS/'evaluate_cross.py'),loader_sha256=sha(CROSS/'evaluate_cross.py'),
        status='Exploratory held-seed application on same source/identity, selected after earlier method results; not blind heldout footage.',
        sources={'05':dict(reference=reference,runs=runs,windows_inclusive=prior['sources']['05']['windows_inclusive'],
                           regions=prior['sources']['05']['regions'],roi_provenance=prior['sources']['05']['roi_provenance'])},
        limitations=['Both seed2 videos already have background quality failure; phase agreement does not imply valid edit or acceptable video.',
                     'No independent intermediate-x0 pose reports found locally or in both original producer pose/x0 directories; early truth stays unknown.',
                     'Final independent pose read only after latent scoring; no method/ROI/threshold selection.',
                     'step019 and sampler_final are related endpoint snapshots, not new samples.',
                     'Phase centering can remove real periodic motion; gap5 averages17physical frames.',
                     'No GPU, new encoding, decoder or pose call; all raw input files are reused.'])
    with (HERE/'PROTOCOL.json').open('x') as f:json.dump(protocol,f,indent=2);f.write('\n')
    print('INPUT_GATE PASS',len(checks),'checks; protocol SHA',sha(HERE/'PROTOCOL.json'))


if __name__=='__main__':main()
