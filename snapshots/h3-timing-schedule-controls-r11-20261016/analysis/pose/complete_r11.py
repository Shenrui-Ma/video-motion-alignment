"""Postprocess already measured R11 outputs with frozen comparisons."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import consumer_r11 as consumer

HERE=Path(__file__).resolve().parent
R2=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose')
R6=Path('/Users/researcher/DevProjects/h3-timing-feedback-r6-20261016/analysis/pose')
REMOTE=Path('/data5/researcher/h3_runs/timing_schedule_controls_r11_20261016/analysis/pose')
REMOTE_R2=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose')
REMOTE_R6=Path('/data5/researcher/h3_runs/timing_feedback_r6_20261016/analysis/pose')
OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
RUNS={'continuous':'r11_s05_continuous6to19','skip7_short':'r11_s05_skip7_6to14'}
PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
WINDOWS=['50:65','69:81','80:92','99:111','0:140','0:46','47:67','68:140','112:140']


def main():
    roots={'native':R2,'full':R2,'feedback':R6}
    roots.update({k:HERE for k,v in RUNS.items() if (HERE/'pilot'/(v+'_provenance/archive_manifest.json')).is_file()})
    runs={'native':'r2_s05_native','full':'r2_s05_full_6to14','feedback':'r6_s05_feedback_retry1'}
    runs.update({k:v for k,v in RUNS.items() if k in roots})
    provenance={k:roots[k]/'pilot'/(r+'_provenance') for k,r in runs.items()}
    manifests={k:json.loads((v/'archive_manifest.json').read_text()) for k,v in provenance.items()}
    conditions={k:json.loads((v/'conditioning.json').read_text()) for k,v in provenance.items()}
    noise={k:json.loads((v/'noise.json').read_text()) for k,v in provenance.items()}
    actual={};hashes={}
    for label in runs:
        m=manifests[label]
        assert consumer.digest(roots[label]/'raw'/m['relative_video'])==m['video_sha256']
        c=conditions[label];n=noise[label];b=conditions['full'];bn=noise['full']
        checks={key:c[key]==b[key] for key in ['prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout']}
        checks.update(pair_snapshot_actual=c['pair_snapshot']['actual']==b['pair_snapshot']['actual'],actual_noise_streams=n['actual_noise_streams']==bn['actual_noise_streams'],noise_signature=n['signature']==bn['signature'])
        actual[label]={'checks':checks,'passed':all(checks.values())}
        hashes[label]={f:consumer.digest(provenance[label]/f) for f in ['conditioning.json','noise.json','config.json','history.json']}
    consumer.save(HERE/'actual_input_noise_pair.json',{'baseline':'r2_s05_full_6to14','rows':actual,'all_passed':all(x['passed'] for x in actual.values()),'provenance_sha256':hashes,'scope':'Actual inputs and noise; operator integrity remains a separate gate.'})
    for label,run in RUNS.items():
        if label in roots:subprocess.run([sys.executable,str(HERE/'check_feedback_audit.py'),'--run-id',run],check=True)
    remote_roots={'native':REMOTE_R2,'full':REMOTE_R2,'feedback':REMOTE_R6,**{k:REMOTE for k in RUNS}}
    poses={label:remote_roots[label]/'pilot'/(Path(manifests[label]['relative_video']).stem+'.pose.json') for label in runs}
    expected={str(remote):consumer.digest(roots[label]/'pilot'/remote.name) for label,remote in poses.items()}
    expected[str(OLD/'scripts/timing_metrics.py')]=consumer.FROZEN['scripts/timing_metrics.py']
    expected[str(OLD/'analysis/pose/old_sam/05_real_megumi_v.pose.json')]=consumer.FROZEN['analysis/pose/old_sam/05_real_megumi_v.pose.json']
    expected[str(OLD/'analysis/pose/compare_runs.py')]='1e725cd5063ae9e9e770f94c54c91dfa5d0473e951e92dfcebaa56619c844b33'
    commands=[];outputs=[]
    pairs=[('all_available',list(runs))]+[(base+'_'+label,[base,label]) for base in ['full','feedback'] for label in RUNS if label in roots]
    if all(k in roots for k in RUNS):
        pairs.append(('continuous_skip7_short',list(RUNS)))
        pairs.append(('factorial_four',['full','feedback','continuous','skip7_short']))
    for pair,labels in pairs:
        for threshold in ('0.3','0.5'):
            output=REMOTE/'pairs'/f'{pair}_threshold{threshold}.json';outputs.append(output)
            command=[PYTHON,str(OLD/'analysis/pose/compare_runs.py'),'--source',consumer.SOURCE_POSE,'--confidence',threshold,'--output',str(output)]
            for label in labels:command+=['--run',label+'='+str(poses[label])]
            for window in WINDOWS:command+=['--window',window]
            commands.append(command)
    code='''import fcntl,hashlib,json,os,subprocess,sys
from pathlib import Path
expected=json.loads(sys.argv[1]);commands=json.loads(sys.argv[2]);lock=Path(sys.argv[3])
with lock.open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for path,wanted in expected.items():
  if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=wanted:raise ValueError('Frozen source or pose mismatch: '+path)
 os.environ['CUDA_VISIBLE_DEVICES']=''
 for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='4'
 for command in commands:
  result=subprocess.run(command,capture_output=True,text=True,check=True)
  output=Path(command[command.index('--output')+1]);output.with_suffix('.stdout.jsonl').write_text(result.stdout)
 print(json.dumps({'completed_comparisons':len(commands),'no_gpu':True}))
'''
    print(consumer.shell('H3_SERVER_A',['python3','-c',code,json.dumps(expected),json.dumps(commands),'/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock']),flush=True)
    for output in outputs:consumer.copy_from('H3_SERVER_A',output,HERE/'pairs'/output.name)
    subprocess.run([sys.executable,str(HERE/'summarize_r11.py')],check=True)
    subprocess.run([sys.executable,str(HERE/'factorial_summary.py')],check=True)
    consumer.save(HERE/'postprocess_state.json',{'status':'metrics_and_pairing_complete','quality_review':'pending fixed55/86/105 visual review','all_outputs_retained':True,'no_gpu':True})


if __name__=='__main__':main()
