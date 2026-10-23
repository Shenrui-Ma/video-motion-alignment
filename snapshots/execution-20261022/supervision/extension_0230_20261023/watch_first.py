from pathlib import Path
import sys,json,time
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'scripts'));import extension_helpers as g
d=r/'innovation_handoff/extension_followon_0230_20261023';j='expand_short_0230_native'
for _ in range(240):
 s=g.snapshot(r);state=s['states'].get(j,{})
 if state.get('status') in ('failed','failed_exhausted','invalid','blocked'):
  g.atomic(d/'FIRST_SAMPLING.json',{'status':'failed','state':state,'time':time.time()});break
 files=list((r/'audit/router').glob(j+'__a*.json'))
 if files:
  a=g.read(max(files,key=lambda p:p.stat().st_mtime_ns),{});steps=a.get('completed_forward_calls',0)
  if steps>=1:
   assert a.get('native_override_calls',0)>=50 and a.get('routed_calls')==0
   g.atomic(d/'FIRST_SAMPLING.json',{'status':'actual_sampling','forwards':steps,'native_override_calls':a['native_override_calls'],'routed_calls':0,'worker':s['worker'],'service':s['service'],'prompt_id':state.get('prompt_id'),'time':time.time()});break
 g.atomic(d/'PREPROCESSING.json',{'status':state.get('status','waiting_api'),'api':s.get('api_queue'),'worker':s['worker'],'service':s['service'],'time':time.time()});time.sleep(30)
else:raise TimeoutError('No first sampling within2h')
