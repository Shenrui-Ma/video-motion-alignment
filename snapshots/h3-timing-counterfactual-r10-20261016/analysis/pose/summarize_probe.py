"""Report passive same-state endpoint readouts after complete replay acceptance."""
from pathlib import Path
import json
import consumer_r10 as consumer

HERE=Path(__file__).resolve().parent
RUN='r10_s05_fixed_full_probe'


def main():
    gate=json.loads((HERE/'replication/complete_replay_gate.json').read_text())
    if not gate['passed']:raise ValueError('Do not interpret probe before complete exact replay acceptance')
    provenance=HERE/'pilot'/(RUN+'_provenance')
    audit=json.loads((provenance/'router_audit.json').read_text());c=audit['counterfactual']
    table=[]
    for index in range(20):
        branches={r['branch']:r for r in c['branches'] if r['physical_index']==index}
        row={'physical_index_zero_based':index,'chosen_branch':'full' if 6<=index<15 else 'native'}
        for branch in ['native','full']:
            r=branches.get(branch);obs=None if r is None else r.get('observation')
            row[branch]={'evaluated':r is not None,'observer_evaluated':obs is not None,
                'accepted':None if obs is None else obs['accepted'],
                'lag_frames':None if obs is None or not obs['accepted'] else obs['best']['lag_frames'],
                'nfe_index':None if r is None else r['nfe_index']}
        table.append(row)
    history=json.loads((provenance/'history.json').read_text())
    times={k:v['timestamp'] for k,v in history['status']['messages'] if 'timestamp' in v}
    parent=gate['parent_tensor_gate']
    report={'run_id':RUN,'full_replay_passed':True,'table':table,
        'NFE':29,'euler_updates':20,'callbacks':20,'routed_blocks':450,
        'whole_prompt_seconds':(times['execution_success']-times['execution_start'])/1000,
        'recorded_timing':{k:parent[k] for k in ['CPU_condition_copy_hash_seconds','CPU_archive_readout_seconds','synchronized_model_seconds']},
        'scope':'Internal frozen latent-reader lag on current same-state native/Full endpoint predictions. Not independent pose truth, not an online gate, not a new sample, and not proof of next-state persistence.',
        'parent_final_pose_inherited':str(HERE/'replication/inherited_final_pose.json'),
        'efficiency_policy':'Record measurements only; no speed-driven diagnosis or additional experiments.'}
    consumer.save(HERE/'probe_readout_table.json',report)
    lines=['# R10: paired native/Full endpoint readouts','',
        'The full replay gate passed: actual inputs/noise, all eight archived parent selected endpoints plus final video/audio tensors, and all141 decoded RGB frames/timebase agree with R3 Full. This adds diagnostic observations, not a new efficacy sample.','',
        'Indices are zero-based physical Euler steps. Values below are the frozen internal latent-reader lags, not independent pose estimates. A dash means that branch or readout was not evaluated; an unknown would be retained explicitly.','',
        '| Physical index | Native lag (frames) | Full lag (frames) | Chosen branch |','|---:|---:|---:|---|']
    def cell(x):
        if not x['observer_evaluated']:return '—'
        return str(x['lag_frames']) if x['accepted'] else 'unknown'
    for row in table:lines.append(f"| {row['physical_index_zero_based']} | {cell(row['native'])} | {cell(row['full'])} | {row['chosen_branch']} |")
    lines+=['', 'Native and Full at indices6–14 use the same current state, sigma, conditions and random seed. The sampler always takes Full there; the extra native probes do not update state. Outside that interval only native is evaluated. Endpoint differences do not establish persistent latent correction or justify stopping by themselves.', '',
            f"Recorded:29 model forwards,20 Euler updates,20 callbacks,450 routed blocks; whole prompt {report['whole_prompt_seconds']:.3f}s. Timing is recorded without a speed diagnosis.", '',
            'Final pose is inherited only through the exact141-frame replay gate. No DWPose rerun, threshold change, model change or automatic fallback experiment was performed.']
    (HERE/'R10_PAIRED_READOUT_REVIEW.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'readout_table_saved':True,'rows':len(table)}))


if __name__=='__main__':main()
