"""Read-only postrun aggregation; writes only this scope's report artifacts."""
import argparse,collections,json
from pathlib import Path
import prepare_once as io
import numpy as np
from run_once import validate_complete
from synthetic_v4 import cases,parent

def execute(args):
    here=io.HERE;summary=io.read(here/'results/SUMMARY.json')
    code=io.record(here/'CODE_FREEZE.json');protocol=io.record(here/'PROTOCOL_FREEZE.json')
    if summary['code_sha256']!=code['sha256'] or summary['protocol_sha256']!=protocol['sha256']:raise ValueError('Summary version mismatch')
    used=[io.record(here/'audit_results.py'),io.record(here/'results/SUMMARY.json'),code,protocol]
    for item in summary['files']:io.verify(item)
    stats={m:{'K_positive':0,'selected':0,'seconds':0.,'required':0,'required_pass':0,'safety_failures':[],
              'required_failures':[],'counts':collections.Counter()} for m in ('v3','v4')}
    rows=[];gate_groups=set();zero_rows=[];mask_power=[]
    for case in cases():
        marker=io.read(here/'results'/case['id']/'COMPLETE.json')
        result=validate_complete(marker,case,protocol['sha256'],code['sha256']);original=parent(case)
        row={'id':case['id'],'suite':case.get('suite','original31'),'original_expected':original['expected'],'methods':{}}
        for name,val in result['methods'].items():
            model=val['result'];a=val['assessment'];bucket=stats[name]
            bucket['K_positive']+=int(model['K']>0);bucket['selected']+=model['K'];bucket['seconds']+=model['seconds']
            verdict=a['direction_task'];bucket['required']+=int(verdict['required']);bucket['required_pass']+=int(verdict['required'] and verdict['pass'])
            if not a['online_safety']['pass']:bucket['safety_failures'].append(case['id'])
            if verdict['required'] and not verdict['pass']:bucket['required_failures'].append(case['id'])
            for part in model['parts'].values():bucket['counts'].update(part['counts'])
            row['methods'][name]={'K':model['K'],'selected':model['selected'],'assessment':a,'seconds':model['seconds']}
        if original['expected'] in ('zero','constant_rotation','uniform','periodic','fully_missing','local_zero'):
            zero_rows.append({'id':case['id'],'K':row['methods']['v4']['K']})
        if case.get('mask_task')=='positive':
            v3={x['part']:x['physical_fraction'] for x in row['methods']['v3']['assessment']['physical_coverage']}
            v4={x['part']:x['physical_fraction'] for x in row['methods']['v4']['assessment']['physical_coverage']}
            new_unsupported={};archive=next(Path(x['path']) for x in marker['files'] if x['path'].endswith('.npz'))
            with np.load(archive,allow_pickle=False) as arrays:
                for part in v4:
                    oldmask=arrays['v3__'+part+'__common_mask'].any(axis=1);new=np.zeros(141,bool)
                    for selected in row['methods']['v4']['selected']:
                        sign=1 if selected['direction']=='delay' else -1
                        if selected['part']==part and sign==np.sign(original['truth']):new[selected['start']:selected['end']+1]=True
                    t=np.arange(141);domain=(t+original['truth']>=0)&(t+original['truth']<141)
                    new_unsupported[part]=int((new&~oldmask&domain).sum())
            capable=(row['methods']['v4']['assessment']['direction_task']['pass'] and
                     all(v4[p] is not None and v3[p] is not None and v4[p]>v3[p] for p in v4) and
                     any(new_unsupported.values()))
            detail={'id':case['id'],'mask':case['mask'],'truth':original['truth'],'v3_coverage':v3,'v4_coverage':v4,
                    'new_correct_frames_outside_old49_support':new_unsupported,'coverage_gate':capable}
            mask_power.append(detail)
            if capable:gate_groups.add((case['mask'],int(np.sign(original['truth']))))
        rows.append(row)
    gates={'all_zero_controls_K0':all(r['K']==0 for r in zero_rows),
           'coverage_both_signs_each_mask':gate_groups=={('S',-1),('S',1),('B',-1),('B',1)},
           'minimum_four_mask_cases':sum(r['coverage_gate'] for r in mask_power)>=4,
           'online_safety_all55':not stats['v4']['safety_failures']}
    receipts=[io.read(p) for p in sorted((here/'audit').glob('case*.json'))]
    phases=[r['seconds'] for r in receipts if r['status']=='pass']
    report={'cases':len(rows),'methods':stats,'zero_controls':zero_rows,'mask_power':mask_power,'gates':gates,
            'case_phase_seconds':{'sum':sum(phases),'median':float(np.median(phases)),'min':min(phases),'max':max(phases)},
            'technical_failures':[r['attempt'] for r in receipts if r['status']=='failed'],
            'busy_attempts':[r['attempt'] for r in receipts if r['status']=='busy'],
            'artifact_files_verified':len(summary['files']),'artifact_bytes':sum(x['bytes'] for x in summary['files']),
            'rows':rows,'new_real_targets':0,'online_actuator_enabled':False,
            'gate_interpretation':'coverage comparison requires improvement in each limb; all per-limb numbers retained; scientific tests are development fixtures'}
    io.commit(here/'RESULT_STATISTICS.json',io.clean(report),[*used,*summary['files']])
    return {'statistics':io.record(here/'RESULT_STATISTICS.json'),'gates':gates,'files_verified':len(summary['files'])}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);args=parser.parse_args();args.phase='audit_results'
    raise SystemExit(io.locked(args,execute))
