"""Frozen pose pairing against same-host native/Full; no changed thresholds."""
import json
from pathlib import Path
import consumer_r12 as consumer

HERE=Path(__file__).resolve().parent
R3=Path('/Users/researcher/DevProjects/h3-timing-spatial-r3-20261016/analysis/pose')
REMOTE=Path('/data5/researcher/h3_runs/timing_native_observer_r12_20261016/analysis/pose')
REMOTE_R3=Path('/data5/researcher/h3_runs/timing_spatial_r3_20261016/analysis/pose')
OLD=Path(consumer.OLD_ROOT)
RUNS={'native':'r3_s05_native','full':'r3_s05_full_6to14','native_observer':'r12_s05_native_observer'}


def main():
    assert json.loads((HERE/'replication/complete_integrity_gate.json').read_text())['passed']
    expected={str(OLD/p):h for p,h in consumer.FROZEN.items()}
    expected[str(OLD/'analysis/pose/compare_runs.py')]='1e725cd5063ae9e9e770f94c54c91dfa5d0473e951e92dfcebaa56619c844b33'
    poses={};summary={}
    for label,run in RUNS.items():
        root=HERE if label=='native_observer' else R3
        remote=REMOTE if label=='native_observer' else REMOTE_R3
        prov=root/'pilot'/(run+'_provenance');m=json.loads((prov/'archive_manifest.json').read_text())
        stem=Path(m['relative_video']).stem;pose=root/'pilot'/(stem+'.pose.json')
        assert consumer.digest(root/'raw'/m['relative_video'])==m['video_sha256']
        poses[label]=remote/'pilot'/pose.name;expected[str(poses[label])]=consumer.digest(pose)
        thresholds={}
        for t in ('0.3','0.5'):
            d=json.loads((root/'pilot'/f'{stem}.threshold{t}.timing.json').read_text())
            rows=[row for row in d['diagnostics'] if row['feature']=='arm_direction']
            thresholds[t]={'primary_lag_frames':next(row['reliable_lag_frames'] for row in rows if row['window']==[50,65]),
                'windows':[{k:row.get(k) for k in ['window','reliable_lag_frames','status','flags']} for row in rows]}
        summary[label]={'run_id':run,'video_sha256':m['video_sha256'],'thresholds':thresholds,
            'quality_gate':'pending fixed-frame review' if label=='native_observer' else 'see inherited R3 fixed-frame review; not newly reviewed'}
    outputs=[];commands=[]
    for pair,labels in [('all_three',list(RUNS)),('native_observer_vs_native',['native','native_observer']),('native_observer_vs_full',['full','native_observer'])]:
        for t in ('0.3','0.5'):
            output=REMOTE/'pairs'/f'{pair}_threshold{t}.json';outputs.append(output)
            command=['/home/researcher/miniconda3/envs/comfyui/bin/python',str(OLD/'analysis/pose/compare_runs.py'),
                '--source',consumer.SOURCE_POSE,'--confidence',t,'--output',str(output)]
            for label in labels:command+=['--run',label+'='+str(poses[label])]
            for window in consumer.WINDOWS+['0:140','0:46','47:67','68:140','112:140']:command+=['--window',window]
            commands.append(command)
    code='''import fcntl,hashlib,json,os,subprocess,sys
from pathlib import Path
expected=json.loads(sys.argv[1]);commands=json.loads(sys.argv[2])
with open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for path,sha in expected.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,'Frozen source or pose mismatch: '+path
 os.environ['CUDA_VISIBLE_DEVICES']=''
 for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='4'
 for command in commands:subprocess.run(command,capture_output=True,text=True,check=True)
 print(json.dumps({'comparisons_complete':len(commands),'GPU_started':False}))
'''
    print(consumer.shell('H3_SERVER_A',['python3','-c',code,json.dumps(expected),json.dumps(commands)]),flush=True)
    for output in outputs:consumer.copy_from('H3_SERVER_A',output,HERE/'pairs'/output.name)
    g=json.loads((HERE/'replication/complete_integrity_gate.json').read_text())['official_result']
    prov=HERE/'pilot'/'r12_s05_native_observer_provenance'
    history=json.loads((prov/'history.json').read_text())
    times={key:row['timestamp'] for key,row in history['status']['messages'] if 'timestamp' in row}
    audit=json.loads((prov/'router_audit.json').read_text())['counterfactual']
    rows=[]
    for step in audit['steps']:
        branches=[branch for branch in audit['branches'] if branch['physical_index']==step['physical_index']]
        observation={}
        for branch in branches:
            item=branch.get('observation')
            observation[branch['branch']]={'measured':item is not None,
                'accepted':None if item is None else item['accepted'],
                'lag_frames':None if item is None or not item['accepted'] else item['best']['lag_frames']}
        rows.append({'physical_index_zero_based':step['physical_index'],'chosen_branch':step['selected_branch'],
            'decision':step['decision'],'internal_readouts':observation})
    consumer.save(HERE/'controller_decision_table.json',{'run_id':'r12_s05_native_observer','rows':rows,
        'scope':'Frozen internal reader on current native endpoint; Full observations are passive. Not independent pose or an untouched native trajectory.'})
    compact={'scope':'One selected development failure; R12 changes native-vs-chosen observation and actuation latency jointly. Internal decisions are not independent motion truth.',
        'runs':summary,'integrity_passed':True,'actual_full_indices':g['actual_full_indices'],
        'NFE':g['NFE'],'euler_updates':g['euler_updates'],'callbacks':g['callbacks'],
        'timing_record_only':{k:g[k] for k in ['CPU_condition_copy_hash_seconds','CPU_archive_readout_seconds','synchronized_model_seconds']},
        'whole_prompt_seconds':(times['execution_success']-times['execution_start'])/1000,
        'cost_component_scope':'CPU archive/readout cost combines recording and observation; it is not pure observer time. No speed diagnosis.',
        'unknown_retained':True,'fixed_frame_quality_pending':True}
    consumer.save(HERE/'compact_summary.json',compact)
    print(json.dumps({'lags':{label:{t:d['primary_lag_frames'] for t,d in x['thresholds'].items()} for label,x in summary.items()},'active':g['actual_full_indices']}),flush=True)


if __name__=='__main__':main()
