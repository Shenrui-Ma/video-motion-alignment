"""Verify saved transforms and physical-time ledgers without rescoring."""
import json
from pathlib import Path
import numpy as np
import diagnose as d

protocol=json.loads((d.HERE/'PROTOCOL.json').read_text())
summary=json.loads((d.HERE/'SUMMARY.json').read_text())
assert summary['protocol_sha256']==d.sha(d.HERE/'PROTOCOL.json')
assert summary['status']=='COMPLETE' and summary['actual_score_count']==30
assert summary['new_tracker_calls']==0 and summary['new_model_constructions']==0
assert summary['device']=='cpu' and summary['cuda_initialized'] is False
checks=[]
for row in protocol['sources']:
    report=json.loads(Path(row['report']).read_text())
    assert report['checkpoint_sha256']=='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
    assert report['selection_sha256']=='5d4f43a066dffa7227e062c5914734f1d406627d10c2c1c8cdf0388e25ad8fd9'
    assert report['tracker']=={'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60}
    tracks,vis=d.load_bound(row)
    for variant in protocol['fixed_variants']:
        stem=d.HERE/'results'/(row['pair_id']+'__'+variant)
        record=json.loads(stem.with_suffix('.json').read_text())
        assert d.sha(stem.with_suffix('.npz'))==record['transformed_npz_sha256']
        start=0 if variant=='self_full' else 8
        physical=np.arange(start,row['N'])
        lag=record['known_delay_frames']
        expected=0 if not variant.startswith('delay_') else int(variant[-1])
        assert lag==expected
        with np.load(stem.with_suffix('.npz'),allow_pickle=False) as arr:
            np.testing.assert_array_equal(arr['physical_frame_indices'],physical)
            np.testing.assert_array_equal(arr['source_original_indices'],physical)
            np.testing.assert_array_equal(arr['target_original_content_indices'],physical-lag)
            np.testing.assert_array_equal(arr['source_tracks'],tracks[:,physical])
            np.testing.assert_array_equal(arr['target_tracks'],tracks[:,physical-lag])
            np.testing.assert_array_equal(arr['source_visibility'],vis[:,physical])
            expected_vis=vis[:,physical-lag].copy()
            if variant=='visibility_gap_8':
                lo=(len(physical)-8)//2;expected_vis[:,lo:lo+8]=0
                assert record['gap']['physical_frame_indices_half_open']==[int(physical[lo]),int(physical[lo]+8)]
            np.testing.assert_array_equal(arr['target_visibility'],expected_vis)
        assert record['physical_frame_indices']==physical.tolist()
        assert record['source_original_indices']==physical.tolist()
        assert record['target_original_content_indices']==(physical-lag).tolist()
        np.testing.assert_array_equal(record['physical_time_seconds'],physical/24)
        np.testing.assert_array_equal(record['target_content_time_seconds'],(physical-lag)/24)
        assert 0<=record['motion_fidelity']<=1
        checks.append({'pair_id':row['pair_id'],'variant':variant,'passed':True})
d.write_json(d.HERE/'VERIFIED.json',{'passed':True,'checks':checks,'count':len(checks),
    'summary_sha256':d.sha(d.HERE/'SUMMARY.json'),'protocol_sha256':d.sha(d.HERE/'PROTOCOL.json'),
    'verification_script_sha256':d.sha(__file__),'new_metric_calls':0,'new_tracker_calls':0})
print('PASS: 30/30 physical ledgers, cache identity, saved coordinates/visibility and score bindings')
