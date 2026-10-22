"""CPU extract small, hash-bound records; full observer scans remain on server."""
import argparse,hashlib,json
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def compact(path,expected_sha=None):
    digest=sha(path)
    if expected_sha is not None:assert digest==expected_sha,'source audit changed'
    a=json.loads(Path(path).read_text());c=a['counterfactual']
    selected=next(s['decision']['selected'][0] for s in c['steps'] if s['decision']['active'])
    out={k:a[k] for k in ('status','completed_forward_calls','completed_calls','routed_calls','calls_by_forward')}
    out['counterfactual']={k:v for k,v in c.items() if k!='measurements'}
    measurements=[];remote_hashes={}
    for m in c['measurements']:
        if m.get('status')!='complete':continue
        response_path=Path(m['response_file']);request_path=Path(m['request_file'])
        assert sha(response_path)==m['response_sha256'] and sha(request_path)==m['request_sha256']
        response=json.loads(response_path.read_text())
        for key in ('decode','pose','observer'):
            record=response[key];assert sha(record['file'])==record['sha256']
            remote_hashes[record['file']]=record['sha256']
        observer=m['observer'];row=[r for r in observer['windows'] if r['window']==selected['window'] and r['feature']==selected['feature']]
        assert len(row)==1
        reduced={k:v for k,v in m.items() if k!='observer'}
        reduced['observer']={k:v for k,v in observer.items() if k!='windows'}
        reduced['observer']['windows']=row
        reduced['observer']['compact_fixed_first_ON_window_only']=True
        reduced['observer']['full_remote_record']=response['observer']
        measurements.append(reduced)
    out['counterfactual']['measurements']=measurements
    out['compact_receipt']={'schema':'r138-compact-actual-audit-v1','original_file':str(path),'original_sha256':digest,'original_bytes':Path(path).stat().st_size,'extractor_sha256':sha(__file__),'measurements_complete':len(measurements),'full_observer_records_kept_remote':True,'verified_remote_json_sha256':remote_hashes,'first_ON_fixed_window':selected['window'],'first_ON_fixed_feature':selected['feature'],'tensor_payloads_transferred':False}
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--expected-sha');args=p.parse_args()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(compact(args.input,args.expected_sha),ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'file':str(out),'sha256':sha(out),'bytes':out.stat().st_size}))
