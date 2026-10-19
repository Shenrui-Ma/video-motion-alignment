"""One55-suite phase per call. No real-target entry point."""
import prepare_once as io
import argparse,time,resource
import numpy as np
from bindings import V3
import profile_v4 as V4
import synthetic_v4 as synthetic
from assessment import assess
HERE=io.HERE

def execute(args):
    freeze=io.read(HERE/'CODE_FREEZE.json');protocol=io.read(HERE/'PROTOCOL_FREEZE.json')
    used=[io.record(HERE/'CODE_FREEZE.json'),io.record(HERE/'PROTOCOL_FREEZE.json'),*freeze['files'],*protocol['files'],*protocol['external_inputs']]
    for item in used:io.verify(item)
    if args.phase=='case':
        case=next(c for c in synthetic.cases() if c['id']==args.case_id)
        manifest=next(c for c in io.read(HERE/'CASE_MANIFEST.json')['cases'] if c['case']['id']==case['id'])
        source,target,truth,plateaus=synthetic.build(case)
        hashes={name:{k:io.array_record(a) for k,a in val.items()} for name,val in [('source',source),('target',target),('truth',truth)]}
        if manifest!={'case':case,'inputs':hashes,'plateaus':plateaus}:raise ValueError('Input manifest mismatch')
        root=HERE/'results'/case['id']
        if (root/'COMPLETE.json').exists():raise FileExistsError('Already complete')
        dest=root/args.attempt;dest.mkdir(parents=True,exist_ok=False)
        methods={};arrays={}
        for name,model in [('v3',V3),('v4',V4)]:
            result,evidence=model.analyze(source,target)
            if name=='v3' and case.get('suite')!='mask12':
                marker=HERE.parent/'phase_shape_profile_candidate_v3/results'/case['id']/'COMPLETE.json'
                prior=io.read(marker);io.verify(prior['result'])
                old=io.read(prior['result']['path'])
                if old['case']!=case or prior.get('case_id')!=case['id']:raise ValueError('Legacy case identity')
                left={k:v for k,v in io.clean(result).items() if k!='seconds'}
                right={k:v for k,v in old['methods']['v3']['result'].items() if k!='seconds'}
                if left!=right:raise ValueError('Legacy v3 scientific RESULT changed')
            methods[name]={'result':result,'assessment':assess(case,result,evidence,truth,plateaus,name)}
            arrays.update({name+'__'+k:v for k,v in evidence.items()})
        arrays.update({'truth__'+k:v for k,v in truth.items()})
        result_path=dest/'RESULT.json';archive=dest/'EVIDENCE.npz'
        io.write(result_path,io.clean({'case':case,'methods':methods,'plateaus':plateaus,'input_hashes':hashes,
            'protocol_sha256':io.record(HERE/'PROTOCOL_FREEZE.json')['sha256'],'peak_rss_bytes_macos':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
        with archive.open('xb') as f:np.savez_compressed(f,**arrays)
        output={'status':'complete','case_id':case['id'],'result':io.record(result_path),'files':[io.record(result_path),io.record(archive)]}
        io.commit(root/'COMPLETE.json',output,[*used,*output['files']])
    else:
        rows=[];records=[]
        for case in synthetic.cases():
            marker=HERE/'results'/case['id']/'COMPLETE.json';m=io.read(marker)
            if m.get('status')!='complete' or m.get('case_id')!=case['id'] or m['result'] not in m['files']:raise ValueError('Marker identity')
            for f in m['files']:io.verify(f)
            result=io.read(m['result']['path'])
            if result['case']!=case or result['protocol_sha256']!=io.record(HERE/'PROTOCOL_FREEZE.json')['sha256']:raise ValueError('Result identity')
            methods={name:{'K':val['result']['K'],'selected':val['result']['selected'],
                           'counts':{p:v['counts'] for p,v in val['result']['parts'].items()},
                           'seconds':val['result']['seconds'],'assessment':val['assessment']} for name,val in result['methods'].items()}
            rows.append({'case':case,'methods':methods,'result':m['result']});records.extend([io.record(marker),*m['files']])
        output={'status':'complete','rows':rows,'cases':len(rows),'files':records,
                'online_safety_pass':all(r['methods']['v4']['assessment']['online_safety']['pass'] for r in rows),
                'new_real_targets':0,'online_actuator':False}
        io.commit(HERE/'results/SUMMARY.json',output,[*used,*records])
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('case','finalize'));parser.add_argument('--case-id');parser.add_argument('--attempt',required=True)
    raise SystemExit(io.locked(parser.parse_args(),execute))
