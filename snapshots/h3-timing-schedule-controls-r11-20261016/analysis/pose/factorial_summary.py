"""Summarize the declared operational 2x2; do not tune or fill unknown lags."""
from pathlib import Path
import json
import datetime
import consumer_r11 as consumer

HERE=Path(__file__).resolve().parent
CELLS={'A_include7_end14':'full','B_include7_end19':'continuous',
       'C_skip7_end14':'skip7_short','D_skip7_end19':'feedback'}


def difference(a,b):
    return None if a is None or b is None else a-b


def main():
    summary=json.loads((HERE/'compact_summary.json').read_text())
    values={}
    for threshold in ('0.3','0.5'):
        lags={name:summary['runs'].get(label,{}).get('thresholds',{}).get(threshold,{}).get('primary_lag_frames') for name,label in CELLS.items()}
        a,b,c,d=[lags[k] for k in CELLS]
        short_skip=difference(c,a);long_skip=difference(d,b)
        include_extend=difference(b,a);skip_extend=difference(d,c)
        values[threshold]={'main_window_lags':lags,'signed_lag_contrasts_frames':{
            'skip_minus_include_at_end14_C_minus_A':short_skip,
            'skip_minus_include_at_end19_D_minus_B':long_skip,
            'extend14_to19_with7_B_minus_A':include_extend,
            'extend14_to19_without7_D_minus_C':skip_extend,
            'interaction_D_minus_C_minus_B_plus_A':difference(skip_extend,include_extend)},
            'null_means_unavailable_not_zero':True}
    controls={}
    for run in ('r11_s05_continuous6to19','r11_s05_skip7_6to14'):
        folder=HERE/'replication'/run
        controls[run]={name:json.loads((folder/name).read_text()).get('passed') if (folder/name).is_file() else None
            for name in ('preintervention_gate.json','schedule_shared_prefix_gate.json','operator_execution_gate.json','capture_inventory.json')}
    records=[]
    for f in sorted((HERE/'pairs').glob('*.json')):
        if f.name.startswith('compact_'):continue
        source=json.loads(f.read_text())
        for row in source.get('results',[]):
            if row['feature']=='arm_direction' or row['window']==[50,65] and row['feature'] in ('wrist_relative','body_xy'):
                records.append({'pair_file':f.name,'window':row['window'],'feature':row['feature'],
                    'common_valid_fraction':row['common_valid_fraction'],'status':row['status'],
                    'errors':{label:r['same_frame_error_on_common_support'] for label,r in row['runs'].items()}})
    consumer.save(HERE/'pairs/compact_pair_summary.json',records)
    quality = {}
    for label in ('continuous', 'skip7_short'):
        entry = summary['runs'].get(label)
        if entry is None:
            quality[label] = {'review_completed': False, 'status': 'output pending'}
            continue
        path = HERE/'pilot'/(entry['run_id']+'.quality_review.json')
        if not path.is_file():
            quality[label] = {'review_completed': False, 'status': 'fixed-frame review pending'}
            continue
        record = json.loads(path.read_text())
        assert record['video_sha256'] == entry['sha256']
        quality[label] = {'review_completed': True, 'quality_gate': record['quality_gate'],
                          'report': str(path)}
    report={'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status':'complete' if not summary['pending'] else 'partial_pending',
        'cells':CELLS,'thresholds':values,'integrity':controls,
        'actual_input_noise_pair':json.loads((HERE/'actual_input_noise_pair.json').read_text())['all_passed'],
        'scope':'Exploratory operational schedule2x2 on one known development failure. Two new fixed runs and two historical arms; R6 is a realized feedback trajectory, not a newly generated fixed-mask replay.',
        'limits':['Contrasts are descriptive, not statistical main-effect estimates across a population.',
                  'Including index7 and extending to19 change total dose and placement together; this is not a dose-independent mechanism isolation.',
                  'Do not compare error values from different common-support pairs as though supports were identical.',
                  'Unknown lag stays null. Independent support and fixed-frame quality are required.',
                  'Efficiency is recorded separately, not diagnosed.'],
        'quality_reviews': quality,
        'pending_quality_review': not all(row['review_completed'] for row in quality.values())}
    consumer.save(HERE/'factorial_summary.json',report)
    print(json.dumps({'status':report['status'],'thresholds':values}))


if __name__=='__main__':main()
