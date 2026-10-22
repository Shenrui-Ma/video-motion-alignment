"""Synthetic CPU latency only; no sampling, attention or device-copy measurement."""
import json,time,statistics,platform
import torch
from prototype import update_gain_field

torch.set_num_threads(1)
rows=[]
for bins in (29,41):
    base=torch.ones(bins,dtype=torch.float64);count=torch.full_like(base,448.)
    _,state,_=update_gain_field(base,base,count,step_index=0,layer_index=0)
    times=[];iterations=[];failures=0
    grid=torch.arange(bins,dtype=torch.float64)
    for step in range(1,1021):
        A=(.65*torch.sin(grid*.21+step*.17)).exp()
        B=(.3*torch.cos(grid*.13+step*.09)).exp()
        if step%10==0:A[bins//2]*=30
        start=time.perf_counter()
        _,state,report=update_gain_field(A,B,count,state=state,step_index=step,layer_index=0)
        elapsed=time.perf_counter()-start
        if step>20:
            times.append(elapsed);iterations.extend(r['iterations'] for r in report['segments'])
            failures+=sum(not r['converged'] for r in report['segments'])
    rows.append({'bins':bins,'calls':len(times),'mean_ms':1000*statistics.mean(times),
                 'median_ms':1000*statistics.median(times),'p95_ms':1000*sorted(times)[int(.95*len(times))-1],
                 'max_active_set_iterations':max(iterations),'failed_segments':failures,
                 'projected_cpu_seconds_per_20_steps_50_layers':statistics.mean(times)*1000})
print(json.dumps({'scope':'synthetic CPU-only; excludes GPU synchronization, copies and attention; not measured inference overhead',
    'python':platform.python_version(),'torch':torch.__version__,'threads':torch.get_num_threads(),'rows':rows},indent=2))
