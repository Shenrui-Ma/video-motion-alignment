from pathlib import Path
import json,hashlib,copy,sys
P=Path(__file__).resolve().parent;E=P.parents[4];A=E/'supervision/innovation_handoff';D=E/'innovation/pilot_ten/direction_package/host41';C=E/'innovation/temporal_coverage';PART=E/'innovation/pilot_ten/other_packages/partial_temporal_rope/host41';R='/data4/research-user/h3_runs/benchmark_schedule_20261022'
sys.path.insert(0,str(A));import activate_direction_pilots as activation
load=lambda p:json.loads(p.read_text());write=lambda p,d:p.write_text(json.dumps(d,indent=2)+'\n');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
base=load(E/'inference/package/jobs.json');assert len(base['jobs'])==46
prereq=[j['id'] for j in base['jobs'] if j['metadata'].get('method')=='partial_temporal_rope'];assert len(prereq)==10
jobs=[];checks=[]
for case in ('short_0252','short_0358'):
 source=next(j for j in base['jobs'] if j['id']==f'innov41_{case}_direction_gated');j=copy.deepcopy(source);orig=load(D/source['graph']);g=copy.deepcopy(orig);generic=load(P.parent/'graphs'/f'innov_{case}_temporal_coverage.json')
 n=copy.deepcopy(generic['50']);n['inputs'].update(model=orig['50']['inputs']['model'],positive=orig['50']['inputs']['positive'],start_frame=orig['50']['inputs']['start_frame'],end_frame=orig['50']['inputs']['end_frame'],audit_dir=R+'/audit/temporal_coverage')
 g['50']=n;jid=f'innov41_{case}_temporal_coverage';g['14']['inputs']['filename_prefix']=jid+'/{attempt_id}'
 for k in set(g)-{'14','50'}:assert g[k]==orig[k]
 j.update(id=jid,graph='graphs/'+jid+'.json',expected_output_prefix=jid+'/');j['metadata'].update(method='temporal_coverage',cohort='innovation',innovation_parameters=n['inputs'],innovation_status='prepared_gpu_unverified',attention_formula='O + alpha*m_ref*(sum_j P[t,j]*Attention(Q_t,K_j,V_j)-Attention(Q_t,K_all_ref,V_all_ref))',coverage_unit='unit conditional probability per latent bin; rows and columns normalized to one',routing_constraints='radius2; entropic Sinkhorn; nondecreasing expected reference-bin time')
 write(P/j['graph'],g);j['metadata']['graph_sha256']=sha(P/j['graph']);jobs.append(j);checks.append({'id':jid,'source':source['id'],'changed_nodes':['14','50'],'graph_sha256':sha(P/j['graph']),'exact_other_nodes':True})
assets=[]
for a in load(PART/'handoff_request.json')['assets']:
 p=a['path']
 if '/graphs/' in p or '/H3PartialRoPE/' in p:continue
 if '/innovation_cache/' in p or '/input/' in p:
  if not any(case in p for case in ('short_0252','short_0358')):continue
 assets.append(a)
for name in ('__init__.py','nodes.py','attention.py','routing.py','frozen.py'):assets.append({'path':R+'/custom_nodes/H3TemporalCoverage/'+name,'sha256':sha(C/name)})
for j in jobs:assets.append({'path':R+'/'+j['graph'],'sha256':sha(P/j['graph'])})
assets.append({'path':R+'/scripts/host_worker.py','sha256':sha(E/'inference/package/scripts/host_worker.py')})
assets=list({a['path']:a for a in assets}.values());req={'root':R,'base':base,'pilots':{'jobs':jobs},'prerequisite_ids':prereq,'assets':assets}
write(P/'jobs.json',{'jobs':jobs});write(P/'handoff_request.json',req);write(P/'consistency.json',{'status':'passed','checks':checks})
ops=(A/'remote_ops.py').read_text().split("if __name__ == '__main__':")[0];body=activation.REMOTE_BODY.replace("directory/'direction_activation.json'","directory/'coverage_pilots_activation.json'")
partial_audit=(PART/'guard_logic.py').read_text().split('def guard(req):')[0]
script=ops+'\n'+(P/'lifecycle.py').read_text()+'\n'+body+'\n'+partial_audit+'\n'+(P/'guard_logic.py').read_text()+'\nREQ=json.loads('+repr(json.dumps(req))+')\n'
script+='''if __name__=='__main__':
 try:guard(REQ)
 except BlockingIOError:print('Existing coverage pilot guard holds lock')
 except Exception as error:
  atomic(Path(REQ['root'])/'innovation_handoff/coverage_pilots_status.json',{'status':'failed','error':repr(error),'unix':time.time()});raise
'''
(P/'coverage_pilots_handoff.py').write_text(script);print(json.dumps({'base':46,'new':2,'prerequisite_partial':10,'assets':len(assets)}))
