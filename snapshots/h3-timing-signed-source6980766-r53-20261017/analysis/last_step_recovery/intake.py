"""Read the 700 MB failure audit once; freeze compact, exact prior19 controller context."""
import argparse,json,os,sys,time
from pathlib import Path
import common as c

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=c.HERE/'CONTEXT.json');a=p.parse_args()
    c.require(a.output.resolve().is_relative_to(c.HERE),'context outside recovery directory')
    c.require(not a.output.exists(),'context already exists')
    os.environ['CUDA_VISIBLE_DEVICES']='';t=c.frozen_runtime();items=c.inventory()
    audit_path=c.archived(c.AUDIT_REL,items);c.require(c.sha(audit_path)==c.AUDIT_SHA,'wrong failure audit')
    audit=c.read(audit_path);cf=audit['counterfactual'];c.require(audit['status']!='complete','original failure cannot be relabelled success')
    measurements={x['physical_index']:x for x in cf['measurements'] if x.get('status')=='complete'}
    steps={x['physical_index']:x for x in cf['steps']}
    c.require(sorted(measurements)==list(range(19)) and sorted(steps)==list(range(19)),'prior completed prefix differs')
    sys.path.insert(0,str(c.PRODUCER/'extensions'))
    from H3AutomaticWindowRouter.selector import Controller
    policy=Controller();rows=[]
    for index in range(19):
        m=measurements[index];req_rel=c.relative_original(m['request_file']);res_rel=c.relative_original(m['response_file'])
        req_path=c.archived(req_rel,items);res_path=c.archived(res_rel,items)
        c.require(c.sha(req_path)==m['request_sha256'] and c.sha(res_path)==m['response_sha256'],'prior measurement binding differs')
        request,response=c.read(req_path),c.read(res_path);t.validate_response(response,request,m['request_sha256'])
        obs_rel=c.relative_original(response['observer']['file']);obs_path=c.archived(obs_rel,items)
        c.require(c.sha(obs_path)==response['observer']['sha256'] and c.read(obs_path)==m['observer'],'prior observer differs')
        actual=policy.select(index,m);expected=steps[index]['decision']
        c.require(all(expected[k]==v for k,v in actual.items()),'prior controller replay differs at '+str(index))
        rows.append({'index':index,'request_relative':req_rel,'request_sha256':m['request_sha256'],'response_relative':res_rel,'response_sha256':m['response_sha256'],'observer_relative':obs_rel,'observer_sha256':response['observer']['sha256'],'expected_decision':actual})
    request=c.original_request();native=[v for v in cf['branches'] if v['physical_index']==19 and v['branch']=='native']
    c.require(len(native)==1 and native[0]['file_sha256']==c.ENDPOINT_SHA and native[0]['normalized_stream_signatures']==request['normalized_stream_signatures'],'final Native branch differs')
    proof_path=c.PRODUCER/'analysis/postrun/audit/cpu_x14_replay/REPORT.json'
    c.require(c.sha(proof_path)==c.REPLAY_SHA,'x19 replay proof changed');proof=c.read(proof_path)
    c.require(proof['status']=='exact_cpu_replay' and len(proof['rows'])==5 and all(v['exact_equal'] and v['actual']==v['expected'] for v in proof['rows']),'x14-to-x19 reconstruction not exact')
    c.require(proof['output']['sha256']==c.X19_SHA and c.sha(proof['output']['file'])==c.X19_SHA,'reconstructed x19 bytes differ')
    c.require(proof['rows'][-1]['expected']==native[0]['same_input'],'x19 proof not bound to final Native input')
    result={'schema':'r53-final-observation-recovery-context-v1','original_run_status':audit['status'],'original_run_completed':False,'failure_inventory_sha256':c.INVENTORY_SHA,'failure_audit_sha256':c.AUDIT_SHA,'frozen_producer_manifest_sha256':c.PRODUCER_MANIFEST_SHA,'original_request':request,'original_request_sha256':c.REQUEST_SHA,'Native019_branch':native[0],'prior19':rows,'prior19_replayed_exact':True,'x19_proof_file':str(proof_path),'x19_proof_sha256':c.REPLAY_SHA,'x19_file':proof['output']['file'],'x19_sha256':c.X19_SHA,'GPU_arithmetic_unverified':True,'scope':'Frozen failed-run prefix and last Native observation only. Recovery has no completed final trajectory yet.'}
    c.write_new(a.output,result);print(json.dumps({'context':str(a.output),'sha256':c.sha(a.output),'prior19_exact':True,'original_run_completed':False}))
if __name__=='__main__':main()
