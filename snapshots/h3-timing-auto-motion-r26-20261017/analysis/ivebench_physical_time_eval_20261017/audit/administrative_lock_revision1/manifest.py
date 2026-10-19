"""Keep the fixed five-by-two denominator; absent records remain pending."""
from pose90 import *
from run_pair import generated

def build():
    frozen();records=[]
    for case in P['cases']:
        for method in P['methods']:
            folder=HERE/'records'/f'{method}_{case["pair_id"]}'
            row={'pair_id':case['pair_id'],'method':method,'effective_frames':case['effective_frames'],'status':'pending'}
            if (folder/'COMPLETE.json').exists():
                _,receipt=generated(case['pair_id'],method)
                row.update(status='complete',pose_file=receipt['pose_file'],pose_sha256=receipt['pose_sha256'],receipt_file=str(folder/'COMPLETE.json'),receipt_sha256=sha(folder/'COMPLETE.json'))
            elif folder.exists():row.update(status='incomplete',reason='Retained partial extraction requires review')
            records.append(row)
    return {'schema':'h3-ivebench-generated-pose90-v1','protocol_sha256':sha(HERE/'PROTOCOL.json'),'freeze_sha256':sha(HERE/'FREEZE.json'),'fixed_pair_denominator':5,'records':records}
if __name__=='__main__':
    j=build();p=HERE/'MANIFEST.json';tmp=HERE/'MANIFEST.json.tmp';tmp.write_text(json.dumps(j,indent=2,allow_nan=False)+'\n');tmp.replace(p)
    print(json.dumps({'complete':sum(r['status']=='complete' for r in j['records']),'planned':10,'sha256':sha(p)}))
