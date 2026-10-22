"""Independent result-file and policy replay verification; no pose extraction."""
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
import diagnose as d

HERE=Path(__file__).resolve().parent


def run():
    protocol=d.verified()
    counters={'sensitivity_cells':0,'negative_pairs':0,'existing_trajectory_steps':0,
              'policy_updates_exact':0,'artifact_hashes':0,'occlusion_poses_exact':0}
    policies={v:d.module('r60_verify_'+v,HERE/'frozen'/v/'scripts/automatic_window_policy.py') for v in ('r55','r50')}
    layouts={v:d.module('r60_layout_'+v,HERE/'frozen'/v/'layout.py') for v in ('r55','r50')}
    summaries={}
    paths = sorted((HERE/'results').glob('*/SUMMARY.json')) + sorted((HERE/'appendix_r50_full20/results').glob('*/SUMMARY.json'))
    for path in paths:
        artifact_root = HERE/'appendix_r50_full20' if 'appendix_r50_full20' in path.parts else HERE
        result=d.read(path);name=path.parent.name
        if name.startswith('replay_'):
            version=result['version'];policy=policies[version]
            exported=d.read(result['export']);assert d.sha(result['export'])==result['export_sha256']
            c=exported['case'];g=SimpleNamespace(valid_frames=c['valid_frame_count'],latent_bins=((c['geometry']['frames']-5)//17)*5+2)
            original,candidate=policy.Policy(.5),policy.Policy(.5)
            firstp,firste=None,None
            for row in result['records']:
                artifact=artifact_root/row['artifact']['path'];assert d.sha(artifact)==row['artifact']['sha256'];counters['artifact_hashes']+=1
                with gzip.open(artifact,'rt') as f:raw=json.load(f)
                i=row['index']
                for label,p in [('original',original),('candidate',candidate)]:
                    decision=p.update(i,raw[label]['windows'])
                    if raw[label]['status']=='unknown_visibility':decision['reason']='unknown_visibility'
                    assert decision==row[label+'_decision']==raw[label+'_decision']
                    assert d.execution_signature(decision,g,layouts[version])==row[label+'_execution']==raw[label+'_execution']
                    counters['policy_updates_exact']+=1
                old=exported['rows'][i]
                if old['original_decision_committed']:
                    assert all(old['original_decision'][k]==v for k,v in row['original_decision'].items())
                    assert old['original_decision']['measurement_status']==raw['original']['status']
                if firstp is None and d.proposal_signature(row['original_decision'])!=d.proposal_signature(row['candidate_decision']):firstp=i
                if firste is None and row['original_execution']!=row['candidate_execution']:firste=i
                assert row['causal_input_before_step']==(firste is None or i<=firste)
                counters['existing_trajectory_steps']+=1
            assert firstp==result['first_proposal_divergence'] and firste==result['first_execution_divergence']
        else:
            policy=policies['r55']
            for row in result['records']:
                assert d.sha(row['source_pose'])==row['source_sha256']
                assert d.sha(row['target_pose'])==row['target_sha256']
                artifact=artifact_root/row['artifact']['path'];assert d.sha(artifact)==row['artifact']['sha256'];counters['artifact_hashes']+=1
                with gzip.open(artifact,'rt') as f:raw=json.load(f)
                p=policy.Policy(.5)
                decisions=[p.update(i,raw['observation']['windows']) for i in (0,1)]
                assert decisions==raw['decisions'];counters['policy_updates_exact']+=2
                assert decisions[1]['active']==row['possible_ON_after_identical_repeat']
                if name.startswith('occlusion_'):
                    base=d.OLD/'r55_original'/f"{row['source_id']}__shift_{row['truth_lag']}.pose.json"
                    assert d.sha(base)==row['original_target_sha256']
                    assert d.hide(d.read(base),d.MASKS[row['mask']])==d.read(row['target_pose'])
                    counters['occlusion_poses_exact']+=1
                counters['negative_pairs' if name.startswith('cross_case_') else 'sensitivity_cells']+=1
        summaries[str(path.relative_to(HERE))]=d.sha(path)
    assert counters['sensitivity_cells']==90 and counters['negative_pairs']==20
    assert counters['existing_trajectory_steps']==114
    record={'status':'PASS','counts':counters,'summary_sha256':summaries,
            'main_protocol_sha256':d.sha(HERE/'PROTOCOL.json'),
            'negative_protocol_sha256':d.sha(HERE/'NEGATIVE_PROTOCOL.json'),
            'negative_baseline_protocol_sha256':d.sha(HERE/'NEGATIVE_BASELINE_PROTOCOL.json'),
            'full20_protocol_sha256':d.sha(HERE/'appendix_r50_full20/PROTOCOL.json'),
            'script_sha256':d.sha(__file__),'GPU_calls':0,'new_pose_calls':0}
    d.write(HERE/'VERIFIED_ALL.json',record)
    print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':run()
