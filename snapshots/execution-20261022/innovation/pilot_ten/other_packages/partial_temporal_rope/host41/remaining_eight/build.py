import json,hashlib,copy,sys
from pathlib import Path
P=Path(__file__).resolve().parent; H=P.parent; E=H.parents[4]
D=E/'innovation/pilot_ten/direction_package/host41'; A=E/'supervision/innovation_handoff'
sys.path.insert(0,str(A));import activate_direction_pilots as activation
R='/data4/research-user/h3_runs/benchmark_schedule_20261022'
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
base=load(E/'inference/package/jobs.json');assert len(base['jobs'])==38
pilotids=[j['id'] for j in load(H/'jobs.json')['jobs']];assert len(pilotids)==2
node=load(H/'graphs/innov41_short_0252_partial_temporal_rope.json')['50']
rows=[];checks=[]
for source in base['jobs']:
 if not source['id'].endswith('_direction_gated') or source['metadata']['task_id'] in ('short_0252','short_0358'):continue
 job=copy.deepcopy(source);jid=source['id'].replace('_direction_gated','_partial_temporal_rope');job.update(id=jid,graph='graphs/'+jid+'.json',expected_output_prefix=jid+'/')
 original=load(D/source['graph']);g=copy.deepcopy(original);g['50']=copy.deepcopy(node)
 for k in ('model','positive','start_frame','end_frame'):g['50']['inputs'][k]=original['50']['inputs'][k]
 g['14']['inputs']['filename_prefix']=jid+'/{attempt_id}'
 for k in set(g)-{'50','14'}:assert g[k]==original[k],k
 job['metadata'].update(method='partial_temporal_rope',cohort='innovation',innovation_parameters=g['50']['inputs'],innovation_status='prepared_gpu_unverified',delta_derivation='At first PackedLayout: (reference_video_origin-output_video_origin)/(5/3), after validating every video-bin time coordinate.',attention_formula=load(H/'jobs.json')['jobs'][0]['metadata']['attention_formula'])
 job['metadata'].pop('graph_sha256',None)
 write(P/job['graph'],g);job['metadata']['graph_sha256']=sha(P/job['graph'])
 rows.append(job);checks.append({'id':jid,'source':source['id'],'changed_nodes':['14','50'],'graph_sha256':sha(P/job['graph']),'condition_node':g['5'],'geometry':job['metadata'].get('geometry'),'prompt_sha256':hashlib.sha256(job['metadata'].get('prompt','').encode()).hexdigest(),'runtime_delta_mode':'reference_origin'})
assert len(rows)==8 and len({j['id'] for j in rows+base['jobs']})==46
write(P/'jobs.json',{'jobs':rows});write(P/'base_manifest.json',base);write(P/'consistency.json',{'status':'passed','cases':checks})
assets={x['path']:x for x in load(H/'handoff_request.json')['assets'] if '/graphs/' not in x['path']}
for receipt in ('deployment_receipt.json','remaining_deployment_receipt.json'):
 for x in load(D/receipt)['records']:
  if any(v in x['destination'] for v in ('/innovation_cache/','/input/','/H3TrustedConditionCache/')):assets[x['destination']]={'path':x['destination'],'sha256':x['sha256']}
for j in rows:assets[R+'/'+j['graph']]={'path':R+'/'+j['graph'],'sha256':sha(P/j['graph'])}
req={'root':R,'base':base,'pilots':{'jobs':rows},'pilot_ids':pilotids,'assets':list(assets.values())};write(P/'handoff_request.json',req)
ops=(A/'remote_ops.py').read_text().split("if __name__ == '__main__':")[0]
body=activation.REMOTE_BODY.replace("directory/'direction_activation.json'","directory/'partial_remaining8_activation.json'")
audit=(H/'guard_logic.py').read_text().split('def guard(req):')[0]
script=ops+'\n'+body+'\n'+audit+'\n'+(P/'guard_logic.py').read_text()+'\nREQ=json.loads('+repr(json.dumps(req))+')\n'
script+='''if __name__=='__main__':
 try:guard(REQ)
 except BlockingIOError:print('Existing remaining8 guard holds lock')
 except Exception as error:
  atomic(Path(REQ['root'])/'innovation_handoff/partial_remaining8_status.json',{'status':'failed','error':repr(error),'unix':time.time()})
  raise
'''
(P/'partial_remaining8_handoff.py').write_text(script)
print(json.dumps({'base':38,'new':len(rows),'assets':len(assets),'source_graphs_unchanged_except_method_and_output':True}))
