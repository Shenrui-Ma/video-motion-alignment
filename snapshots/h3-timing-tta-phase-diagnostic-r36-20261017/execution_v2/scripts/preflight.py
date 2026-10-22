"""Read-only stdlib intake; no new pose, tensor, lag or model computation."""
import argparse
from contract import ROOT,REMOTE_ROOT,read,sha,require,validate_freeze,video_pose_gate,verify_model_files


def check(remote=False):
    validate_freeze()
    if remote:require(str(ROOT)==REMOTE_ROOT,'Remote root')
    inputs=read(ROOT/'INPUTS.json');plan=read(ROOT/'PHASE_PLAN.json')
    expected=[f"pose:{e['id']}:{v}" for e in inputs['items'] for v in ('flip','pad16')]
    require(plan['pose_phases']==expected and len(expected)==10,'All original10passes retained')
    complete=read(ROOT/'evidence/identity_candidate_COMPLETE.json')
    for original,current in [('RESULTS.json','identity_candidate_ledger.json'),('SUMMARY.json','identity_candidate_SUMMARY.json')]:
        require(sha(ROOT/'evidence'/current)==complete['files'][original],'Historical candidate result SHA')
    require(complete['freeze_sha256']==sha(ROOT/'evidence/feasibility_FREEZE.json'),'Historical feasibility freeze')
    ledger=read(ROOT/'evidence/identity_candidate_ledger.json');summary=read(ROOT/'evidence/identity_candidate_SUMMARY.json')
    require(ledger['summary']==summary and summary['inputs_sha256']==sha(ROOT/'INPUTS.json'),'Historical ledger/input binding')
    require(len(ledger['rows'])==792,'All frozen candidates including UNKNOWN')
    keys=[(r['endpoint'],r['category'],tuple(r['window']),r['feature']) for r in ledger['rows']]
    require(len(set(keys))==792,'Duplicate or missing candidate identity')
    for e in inputs['items']:video_pose_gate(e,remote)
    if remote:verify_model_files(inputs['items'])
    return {'status':'PASS','freeze_sha256':sha(ROOT/'FREEZE.json'),'inputs':5,'new_pose_phases':10,'candidate_rows':792,'GPU':False,'model_imports':False,'actual_pose_executed':False}


def main():
    import json
    p=argparse.ArgumentParser();p.add_argument('--remote',action='store_true');args=p.parse_args();print(json.dumps(check(args.remote)))

if __name__=='__main__':main()
