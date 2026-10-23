from pathlib import Path
import json,sys,subprocess,shlex,concurrent.futures,time
D=Path(__file__).parent;E=D.parent.parent
extension="""from pathlib import Path
import sys,json,time
r=Path(ROOT);sys.path.insert(0,str(r/'scripts'));import extension_helpers as g;s=g.snapshot(r);out={'time':time.time(),'worker':s['worker'],'service':s['service'],'locks':s['locks'],'api':s['api_queue'],'jobs':{},'guards':{}}
for j,st in s['states'].items():
 if any(x in j for x in CASES):
  t=g.read(r/'audit/timing'/(str(st.get('attempt_id'))+'.json'),{});a=g.read(r/'audit/router'/(str(st.get('attempt_id'))+'.json'),{});out['jobs'][j]={'status':st['status'],'prompt_id':st.get('prompt_id'),'steps':len(t.get('steps',[])),'forwards':a.get('completed_forward_calls'),'sampling_seconds':t.get('sampler_wall_seconds')}
for n in GUARDS:
 p=r/'innovation_handoff'/n;out['guards'][n]={'identity':g.read(p/'GUARD.json',{}),'progress':g.read(p/'PROGRESS.json',{}),'result':g.read(p/'RESULT.json',{}).get('status')}
print(json.dumps(out))"""
live="""from pathlib import Path
import json,time,hashlib
r=Path('/data/research-user/h3_inference_20261023/live_phase_pair_20261023')
def read(p):return json.loads(p.read_text()) if p.exists() else None
def ident(o):
 if not o:return None
 p=Path('/proc')/str(o['pid'])
 if not p.exists():return {'state':'exited','record':o}
 st=(p/'stat').read_text().rsplit(')',1)[1].split();return {'uid':p.stat().st_uid,'start_ticks':st[19],'process_state':st[0],'cmdline':(p/'cmdline').read_bytes().replace(bytes([0]),b' ').decode()[:220],'record':o}
out={'time':time.time(),'status':read(r/'STATUS.json'),'service':ident(read(r/'service.json')),'started':read(r/'STARTED.json'),'jobs':{}}
for m in ['native','global_weak']:
 tid='live_phase_short0358_'+m+'_20261023';p=r/'audit/live_phase'/tid/'OBSERVATION.json';o=read(p) or {};out['jobs'][m]={'observation':{k:o.get(k) for k in ['callback_count','actual_model_forward_count','extra_model_forward_calls']},'gate':{'passed':(read(r/'jobs'/m/'TRAJECTORY_GATE.json') or {}).get('passed')},'cleanup':read(r/'jobs'/m/'SERVICE_CLEANUP.json'),'submitted':read(r/'jobs'/m/'SUBMITTED.json')}
print(json.dumps(out))"""
def get(host,code):
 p=subprocess.run(['ssh','-o','ConnectTimeout=8','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=1',host,shlex.join(['python3','-c',code])],capture_output=True,text=True,timeout=45);assert p.returncode==0,p.stderr;return json.loads(p.stdout)
with concurrent.futures.ThreadPoolExecutor() as ex:
 fs={
 'host41':ex.submit(get,'H3_HOST_PRIMARY',extension.replace('ROOT',repr('/data4/research-user/h3_runs/benchmark_schedule_20261022')).replace('CASES',repr(['short_0220','long_0174'])).replace('GUARDS',repr(['extension_followon_0220_20261023','extension_followon_0174_20261023']))),
 'host9':ex.submit(get,'H3_HOST_SECONDARY',extension.replace('ROOT',repr('/home/research-user/h3_runs/adaptive_role5_20261023')).replace('CASES',repr(['short_0166','short_0185'])).replace('GUARDS',repr(['extension_three_20261023','extension_followon_0185_20261023']))),
 'host81':ex.submit(get,'H3_HOST_RTX4090',live)}
 out={}
 for k,f in fs.items():
  try:out[k]=f.result()
  except Exception as e:out[k]={'error':str(e),'time':time.time()}
for k,v in out.items():(D/(k+'.json')).write_text(json.dumps(v,indent=2))
for k in ['host41','host9']:print(k,json.dumps(out[k])[:3000])
v=out['host81'];print('host81',v.get('status',v.get('error')),{m:{'callbacks':o['observation'].get('callback_count'),'forwards':o['observation'].get('actual_model_forward_count'),'extra':o['observation'].get('extra_model_forward_calls'),'gate':(o['gate'] or {}).get('passed')} for m,o in v.get('jobs',{}).items()})
A=E/'metrics/qwen_runtime/host41_extension_live_incremental_20261023';p=json.loads((A/'COORDINATOR_STARTED.json').read_text());ps=subprocess.run(['ps','-p',str(p['pid']),'-o','uid=,lstart=,command='],capture_output=True,text=True);a={'identity':p,'current_ps':ps.stdout,'discovery':json.loads((A/'DISCOVERY_CHECK.json').read_text())};(D/'awq.json').write_text(json.dumps(a,indent=2));print('AWQ',ps.stdout.strip(),a['discovery'])
