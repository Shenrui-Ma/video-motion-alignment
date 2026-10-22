from pathlib import Path
import json,hashlib,subprocess,copy
E=Path('/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022');D=Path(__file__).parent
B=E/'innovation/adaptive_strength_20261023/batch/anchor_pilots';PKG=E/'innovation/feature_anchor';ready=json.loads((PKG/'READY.json').read_text());assert ready['test_exit_code']==0
OLD='/data4/research-user/h3_runs/benchmark_schedule_20261022';NEW='/data4/research-user/h3_inference_20261023/run'
profiles=[('host41','H3_HOST_taizun_research_user',OLD,'short_0252',OLD+'/innovation_handoff/anchor_priority_20261023/PARKED.json'),('host60','H3_HOST_A100',NEW,'short_0358',NEW+'/handoff/anchor_priority/PARKED.json')]
def remote(host,path):return subprocess.check_output(['ssh',host,'cat '+path])
def sha(b):return hashlib.sha256(b).hexdigest()
def remap(x,r):
 if isinstance(x,str):return x.replace(OLD,r)
 if isinstance(x,list):return [remap(v,r) for v in x]
 if isinstance(x,dict):return {k:remap(v,r) for k,v in x.items()}
 return x
for name,host,r,case,parkpath in profiles:
 out=D/name;(out/'graphs').mkdir(exist_ok=True,parents=True);(out/'nodes').mkdir(exist_ok=True)
 base=json.loads(remote(host,r+'/jobs.json'));park=json.loads(remote(host,parkpath));(out/'PARKED.json').write_text(json.dumps(park,indent=2))
 src=next(j for j in json.loads((B/'jobs.json').read_text())['jobs'] if j['metadata']['task_id']==case);g=json.loads((B/src['graph']).read_text());tg=remap(g,r)
 if name=='host60':tg['5']['inputs']['manifest_sha256']='f6c53258e9a644036110205e1a13b88c0f12a8d3abb1c00c531a4fb82811206a'
 inverse=json.loads(json.dumps(tg).replace(r,OLD));inverse['5']['inputs']['manifest_sha256']=g['5']['inputs']['manifest_sha256'];assert inverse==g
 graphraw=(json.dumps(tg,indent=2)+'\n').encode();(out/src['graph']).write_bytes(graphraw)
 j=remap(copy.deepcopy(src),r);j['metadata']['producer_host']=name;j['metadata']['host']=host;j['metadata']['remote_root']=r;j['metadata']['source_job_id']=j['id'];j['metadata']['graph_sha256']=sha(graphraw)
 assets=[{'path':r+'/'+j['graph'],'sha256':sha(graphraw),'local':str(out/j['graph'])}]
 for file,expected in ready['source_shas'].items():
  if file.startswith('test_'):continue
  data=(PKG/file).read_bytes();assert sha(data)==expected
  (out/'nodes'/file).write_bytes(data);assets.append({'path':r+'/custom_nodes/H3AnchoredGuidance/'+file,'sha256':expected,'local':str(out/'nodes'/file)})
 before=remote(host,r+'/scripts/manage_service.py');after=before.replace(b"'H3FeatureGuidance'",b"'H3FeatureGuidance','H3AnchoredGuidance'")
 assert after!=before and after.count(b'H3AnchoredGuidance')==1;compile(after,'manage','exec');(out/'manage_service.staged.py').write_bytes(after)
 request={'status':'staged_waiting_review','cpu_tests':{'passed':True,'node_tests':ready['test_count'],'guard_tests':12},'root':r,'owner_host':name,'base':base,'pilots':{'jobs':[j]+park['parked_jobs']},'assets':assets,'service_change':{'path':r+'/scripts/manage_service.py','staged_path':r+'/scripts/manage_service.anchor.staged.py','before_sha256':sha(before),'after_sha256':sha(after)},'source_science':str(B/'SCIENCE_CHECK.json'),'source_ready':ready,'path_only_equivalence':True}
 (out/'request.json').write_text(json.dumps(request,indent=2));print(name,'base',len(base['jobs']),'append',[x['id'] for x in request['pilots']['jobs']])
