import json,copy,hashlib,sys
from pathlib import Path
P=Path(__file__).resolve().parent;E=P.parents[4];H=E/'innovation/pilot_ten/other_packages/temporal_coverage/host41';C=E/'innovation/temporal_coverage_v2';A=E/'supervision/innovation_handoff';R='/data4/research-user/h3_runs/benchmark_schedule_20261022'
sys.path.insert(0,str(A));import activate_direction_pilots as activation
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
base=load(P/'base_manifest.json');assert len(base['jobs'])==46
jobs=[]
for src in load(H/'jobs.json')['jobs']:
 j=copy.deepcopy(src);g=load(H/src['graph']);jid=src['id'].replace('temporal_coverage','temporal_coverage_v2');j.update(id=jid,graph='graphs/'+jid+'.json',expected_output_prefix=jid+'/');g['50']['class_type']='H3TemporalCoverageV2';g['50']['inputs'].update(iterations=64,audit_dir=R+'/audit/temporal_coverage_v2');g['14']['inputs']['filename_prefix']=jid+'/{attempt_id}'
 j['metadata'].update(method='temporal_coverage_v2',innovation_parameters=g['50']['inputs'],innovation_status='cpu_verified_gpu_pending',solver='damped_newton_cpu_float64',fallback_policy='same_time_weak',solver_change='Same entropy-regularized transport objective, bounded dual Newton instead of fixed128 Sinkhorn; max64 Newton steps and24 Armijo reductions',preserved_v1_result=src['id']);write(P/j['graph'],g);j['metadata']['graph_sha256']=sha(P/j['graph']);jobs.append(j)
assets={x['path']:x for x in load(H/'handoff_request.json')['assets'] if '/graphs/' not in x['path'] and '/H3TemporalCoverage/' not in x['path']}
for n in ('__init__.py','nodes.py','attention.py','routing.py','frozen.py'):assets[R+'/custom_nodes/H3TemporalCoverageV2/'+n]={'path':R+'/custom_nodes/H3TemporalCoverageV2/'+n,'sha256':sha(C/n)}
for j in jobs:assets[R+'/'+j['graph']]={'path':R+'/'+j['graph'],'sha256':sha(P/j['graph'])}
old=(P/'manage_service.before.py').read_text();assert "'H3TemporalCoverageV2'" not in old
new=old.replace("'H3TemporalCoverage',","'H3TemporalCoverage','H3TemporalCoverageV2',");assert old!=new;(P/'manage_service.after.py').write_text(new)
service={'path':R+'/scripts/manage_service.py','before_sha256':sha(P/'manage_service.before.py'),'after_sha256':sha(P/'manage_service.after.py'),'staged_path':R+'/scripts/manage_service.coverage_v2.staged.py'}
assets[service['path']]={'path':service['path'],'sha256':service['after_sha256']}
req={'root':R,'base':base,'pilots':{'jobs':jobs},'prerequisite_ids':['innov41_long_0039_temporal_coverage'],'assets':list(assets.values()),'service_change':service};write(P/'jobs.json',{'jobs':jobs});write(P/'handoff_request.json',req)
ops=(A/'remote_ops.py').read_text().split("if __name__ == '__main__':")[0];body=activation.REMOTE_BODY.replace("directory/'direction_activation.json'","directory/'coverage_v2_activation.json'")
audit=(H/'guard_logic.py').read_text().split('def guard(req):')[0]
script=ops+'\n'+(H/'lifecycle.py').read_text()+'\n'+body+'\nimport math\n'+audit+'\n'+(P/'guard_logic.py').read_text()+'\nREQ=json.loads('+repr(json.dumps(req))+')\n'
script+='''if __name__=='__main__':
 try:guard(REQ)
 except BlockingIOError:print('Existing coverage v2 guard holds lock')
 except Exception as e:
  atomic(Path(REQ['root'])/'innovation_handoff/coverage_v2_status.json',{'status':'failed','error':repr(e),'unix':time.time()});raise
'''
(P/'coverage_v2_handoff.py').write_text(script)
print(json.dumps({'base':46,'target':48,'assets':len(assets),'pilot_ids':[j['id'] for j in jobs]}))
