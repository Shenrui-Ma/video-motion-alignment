"""One55-suite phase per call. No real-target entry point."""
import prepare_once as io
import argparse,time,resource
import numpy as np
from bindings import V3
import profile_v4 as V4
import synthetic_v4 as synthetic
from assessment import assess
HERE=io.HERE

def validate_complete(marker,case,protocol_sha,code_sha):
    """A marker commits exactly one RESULT and one EVIDENCE for this version/case."""
    if marker.get('status')!='complete' or marker.get('case_id')!=case['id']:raise ValueError('Marker identity')
    if marker.get('protocol_sha256')!=protocol_sha or marker.get('code_sha256')!=code_sha:raise ValueError('Marker version identity')
    files=marker.get('files')
    if not isinstance(files,list) or len(files)!=2 or marker.get('result') not in files:raise ValueError('Two-file inventory required')
    paths=[io.Path(f['path']) for f in files]
    if {q.name for q in paths}!={'RESULT.json','EVIDENCE.npz'} or len({str(q.parent) for q in paths})!=1:raise ValueError('RESULT/EVIDENCE inventory mismatch')
    if io.Path(marker['result']['path']).name!='RESULT.json':raise ValueError('RESULT record mismatch')
    for f in files:io.verify(f)
    result=io.read(marker['result']['path'])
    if result['case']!=case or result.get('protocol_sha256')!=protocol_sha or result.get('code_sha256')!=code_sha:raise ValueError('Result case/version identity')
    return result

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
            'protocol_sha256':io.record(HERE/'PROTOCOL_FREEZE.json')['sha256'],
            'code_sha256':io.record(HERE/'CODE_FREEZE.json')['sha256'],
            'peak_rss_bytes_macos':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
        with archive.open('xb') as f:np.savez_compressed(f,**arrays)
        output={'status':'complete','case_id':case['id'],'result':io.record(result_path),
                'protocol_sha256':io.record(HERE/'PROTOCOL_FREEZE.json')['sha256'],
                'code_sha256':io.record(HERE/'CODE_FREEZE.json')['sha256'],
                'files':[io.record(result_path),io.record(archive)]}
        io.commit(root/'COMPLETE.json',output,[*used,*output['files']])
    else:
        rows=[];records=[]
        for case in synthetic.cases():
            marker=HERE/'results'/case['id']/'COMPLETE.json';m=io.read(marker)
            result=validate_complete(m,case,io.record(HERE/'PROTOCOL_FREEZE.json')['sha256'],io.record(HERE/'CODE_FREEZE.json')['sha256'])
            methods={name:{'K':val['result']['K'],'selected':val['result']['selected'],
                           'counts':{p:v['counts'] for p,v in val['result']['parts'].items()},
                           'seconds':val['result']['seconds'],'assessment':val['assessment']} for name,val in result['methods'].items()}
            rows.append({'case':case,'methods':methods,'result':m['result']});records.extend([io.record(marker),*m['files']])
        output={'status':'complete','rows':rows,'cases':len(rows),'files':records,
                'protocol_sha256':io.record(HERE/'PROTOCOL_FREEZE.json')['sha256'],
                'code_sha256':io.record(HERE/'CODE_FREEZE.json')['sha256'],
                'online_safety_pass':all(r['methods']['v4']['assessment']['online_safety']['pass'] for r in rows),
                'new_real_targets':0,'online_actuator':False}
        io.commit(HERE/'results/SUMMARY.json',output,[*used,*records])
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('case','finalize'));parser.add_argument('--case-id');parser.add_argument('--attempt',required=True)
    raise SystemExit(io.locked(parser.parse_args(),execute))
