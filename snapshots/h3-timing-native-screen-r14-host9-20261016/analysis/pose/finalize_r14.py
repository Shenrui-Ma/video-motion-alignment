"""Sequential completion after the sole intake/pose consumer; no GPU work."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
import consumer_r14 as c

HERE = Path(__file__).resolve().parent
RUN = 'r14_s05_seed1313_native_host9'
REMOTE = Path('/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016')
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'
OLD = Path(c.OLD_ROOT)
SHARED = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def check_conditions(prov):
    parents = {
        'R12_seed1311': Path('/Users/researcher/DevProjects/h3-timing-native-observer-r12-20261016/analysis/pose/pilot/r12_s05_native_observer_provenance'),
        'R3_seed1311': Path('/Users/researcher/DevProjects/h3-timing-spatial-r3-20261016/analysis/pose/pilot/r3_s05_native_provenance'),
        'old_seed1312': Path('/Users/researcher/DevProjects/h3-timing-autoresearch-20261016/analysis/pose/pilot/s05_full_seed2_native_x0_provenance'),
    }
    cond = json.loads((prov / 'conditioning.json').read_text())
    noise = json.loads((prov / 'noise.json').read_text())
    graph = json.loads((prov / 'config.json').read_text())
    rows = {}
    for label, p in parents.items():
        old = json.loads((p / 'conditioning.json').read_text())
        on = json.loads((p / 'noise.json').read_text())
        og = json.loads((p / 'config.json').read_text())
        fields = ['prompt', 'input_video', 'native_vae_calls', 'qwen_presentation',
                  'tokenization_before_vision_expansion', 'conditioning_embedding', 'token_tags',
                  'target_latent_shapes', 'packed_layout']
        checks = {key: cond[key] == old[key] for key in fields}
        checks['pair_actual_clean_conditions'] = cond['pair_snapshot']['actual'] == old['pair_snapshot']['actual']
        expected = dict(on['signature'], seed=2026101313)
        checks['noise_signature_only_registered_seed_diff'] = noise['signature'] == expected
        checks['actual_noise_is_distinct'] = all(x['sha256'] != y['sha256'] for x, y in zip(noise['actual_noise_streams'], on['actual_noise_streams']))
        checks['graph_seed'] = graph['6']['inputs']['noise_seed'] == 2026101313
        checks['same_models_geometry_sampler'] = all(graph[k] == og[k] for k in ('1','2','3','4','41','8','9','13','21','22'))
        rows[label] = {'passed': all(checks.values()), 'checks': checks,
                       'parent_provenance': str(p), 'parent_seed': on['signature']['seed'],
                       'new_seed': noise['signature']['seed'],
                       'file_hashes': {k: c.digest(p/k) for k in ('conditioning.json','noise.json','config.json')}}
    result = {'passed': all(r['passed'] for r in rows.values()), 'rows': rows,
              'augmentation': 'New seed also enters pinned native reference augmentation. Actual clean refs and seed are audited; no archived post-augmentation tensor, so do not claim this changes initial noise alone.',
              'no_final_or_prefix_bitwise_expectation': True}
    c.save(HERE/'actual_condition_seed_gate.json', result)
    assert result['passed'], 'Actual conditioning/seed boundary mismatch; retain result and stop causal interpretation.'


def summarize(prov):
    manifest = json.loads((prov/'archive_manifest.json').read_text())
    stem = Path(manifest['relative_video']).stem
    thresholds = {}
    for t in ('0.3','0.5'):
        data = json.loads((HERE/'pilot'/f'{stem}.threshold{t}.timing.json').read_text())
        rows = []
        for d in data['diagnostics']:
            if d['feature'] not in ('arm_direction','wrist_relative','body_xy','left_arm_direction','right_arm_direction'): continue
            rows.append({k:d.get(k) for k in ('feature','window','reliable_lag_frames','status','flags')} |
                        {'same_frame': d.get('same_frame'), 'best': d.get('best')})
        thresholds[t] = rows
    primary = {t:{feature:next(r for r in rows if r['window']==[50,65] and r['feature']==feature)
                  for feature in ('arm_direction','wrist_relative')} for t,rows in thresholds.items()}
    lags = [primary[t][f]['reliable_lag_frames'] for t in ('0.3','0.5') for f in ('arm_direction','wrist_relative')]
    normal = all(x is not None and abs(x)<=2 for x in lags)
    classification = 'main_window_naturally_near_zero' if normal else 'unknown_cannot_establish_normal' if any(x is None for x in lags) else 'not_naturally_near_zero'
    operator = json.loads((HERE/'replication/complete_integrity_gate.json').read_text())
    pose = json.loads((HERE/'pilot'/f'{stem}.pose.json').read_text())
    history = json.loads((prov/'history.json').read_text())
    timestamps = {name:body['timestamp'] for name,body in history['status']['messages'] if name in ('execution_start','execution_success')}
    result = {'run_id':RUN, 'video_sha256':manifest['video_sha256'], 'raw':str(HERE/'raw'/manifest['relative_video']),
              'seed':2026101313, 'primary_lags_direction_wrist_by_threshold':{
                  t:{f:primary[t][f]['reliable_lag_frames'] for f in primary[t]} for t in primary},
              'main_window_normal':normal, 'classification':classification, 'thresholds':thresholds,
              'detector_statistics':pose['statistics'], 'operator_and_capture_gate':operator['passed'],
              'internal_observations':operator['observations'], 'actual_NFE':operator['actual_NFE'],
              'observer_seconds_total':operator['observer_seconds_total'],
              'observer_compute_seconds':operator['observer_compute_seconds'],
              'whole_history_seconds':(timestamps['execution_success']-timestamps['execution_start'])/1000,
              'quality_gate':'pending fixed55/86/105 inspection; timing normal is not full edit success',
              'scope':'One preselected new seed on known source05/Sam. Not a blind independent scene or natural failure-rate estimate. Final normal does not imply early checkpoint normal.'}
    c.save(HERE/'compact_summary.json',result)
    print(json.dumps({k:result[k] for k in ('run_id','main_window_normal','classification','primary_lags_direction_wrist_by_threshold','actual_NFE')}),flush=True)


def main():
    with (HERE/'finalizer.lock').open('a') as own:
        fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # This waits for the existing consumer instead of starting a second one.
        with (HERE/'coordinator.lock').open('a') as coordinator:
            fcntl.flock(coordinator,fcntl.LOCK_EX)
        prov=HERE/'pilot'/(RUN+'_provenance')
        assert (prov/'archive_manifest.json').is_file(), 'Intake/pose incomplete; inspect retained consumer failure.'
        with SHARED.open('a') as heavy:
            fcntl.flock(heavy,fcntl.LOCK_EX)
            check_conditions(prov)
            c.shell('H3_SERVER_A',['mkdir','-p',str(REMOTE/'analysis/pose/replication')])
            subprocess.run(['scp',*c.jump_options('H3_SERVER_A'),'-q',str(HERE/'verify_r14_remote.py'),
                            'H3_SERVER_A:'+str(REMOTE/'analysis/pose/verify_r14_remote.py')],check=True)
            print(c.shell('H3_SERVER_A',['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=4','MKL_NUM_THREADS=4',
                    PYTHON,str(REMOTE/'analysis/pose/verify_r14_remote.py')]),flush=True)
            c.copy_from('H3_SERVER_A',REMOTE/'analysis/pose/replication/complete_integrity_gate.json',HERE/'replication/complete_integrity_gate.json')
            c.copy_from('H3_SERVER_A',REMOTE/'audit/x0'/RUN/'manifest.json',HERE/'replication/capture_manifest.json')
            manifest=json.loads((prov/'archive_manifest.json').read_text())
            pose=REMOTE/'analysis/pose/pilot'/(Path(manifest['relative_video']).stem+'.pose.json')
            commands=[];outs=[]
            for t in ('0.3','0.5'):
                out=REMOTE/'analysis/pose/pairs'/f'single_seed1313_threshold{t}.json';outs.append(out)
                command=[PYTHON,str(OLD/'analysis/pose/compare_runs.py'),'--source',c.SOURCE_POSE,
                         '--run','seed1313='+str(pose),'--confidence',t,'--output',str(out)]
                for w in ['50:65','69:81','80:92','99:111','0:140','0:46','47:67','68:140','112:140']:command+=['--window',w]
                commands.append(command)
            remote_code='''import fcntl,hashlib,json,os,subprocess,sys
from pathlib import Path
with Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX)
 for name,hash_ in json.loads(sys.argv[1]).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==hash_
 os.environ['CUDA_VISIBLE_DEVICES']=''
 for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='4'
 for cmd in json.loads(sys.argv[2]):subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
'''
            expected={str(OLD/'analysis/pose/compare_runs.py'):'1e725cd5063ae9e9e770f94c54c91dfa5d0473e951e92dfcebaa56619c844b33',
                      str(OLD/'scripts/timing_metrics.py'):c.FROZEN['scripts/timing_metrics.py'],
                      c.SOURCE_POSE:c.FROZEN['analysis/pose/old_sam/05_real_megumi_v.pose.json'],
                      str(pose):c.digest(HERE/'pilot'/pose.name)}
            c.shell('H3_SERVER_A',['python3','-c',remote_code,json.dumps(expected),json.dumps(commands)])
            for out in outs:c.copy_from('H3_SERVER_A',out,HERE/'pairs'/out.name)
            summarize(prov)
            c.save(HERE/'finalizer_state.json',{'status':'metrics_integrity_complete','quality_pending':True,
                       'completed_unix':time.time(),'no_gpu':True})


if __name__=='__main__':
    try:main()
    except Exception as error:
        c.save(HERE/'finalizer_failure.json',{'error':repr(error),'epoch':time.time(),'retained':True})
        raise
