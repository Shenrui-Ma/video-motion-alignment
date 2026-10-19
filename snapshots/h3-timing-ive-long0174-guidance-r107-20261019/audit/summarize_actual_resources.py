"""Summarize observed runtime evidence after the actual R107 paired gate."""
import hashlib
import json
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN='r107_long_0174_seed2026101701_forced'
def read(p):return json.loads(p.read_text())
def bound(p):return {'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
gate=ROOT/'analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json'
g=read(gate);assert g['passed'] is True and all(g['checks'].values())
resource=ROOT/'logs/resources.jsonl'
rows=[json.loads(l) for l in resource.read_text().splitlines()]
groups={}
for row in rows:
    cg=row.get('cgroup',{});s=cg.get('snapshot')
    if not cg.get('sample_available') or not s:continue
    for ancestor in s['ancestors']:
        if ancestor.get('current_bytes') is not None:
            groups.setdefault(ancestor['path'],[]).append((s['observed_unix'],ancestor,cg.get('since_startup',{})))
summary={}
for name,values in groups.items():
    first,last=values[0],values[-1]
    summary[name]={
      'samples':len(values),'first_unix':first[0],'last_unix':last[0],
      'first_current_bytes':first[1]['current_bytes'],'last_current_bytes':last[1]['current_bytes'],
      'maximum_sampled_current_bytes':max(x[1]['current_bytes'] for x in values),
      'maximum_recorded_cgroup_peak_bytes':max(x[1].get('peak_bytes') or 0 for x in values),
      'maximum_sampled_anon_bytes':max(x[1].get('stat',{}).get('anon',0) for x in values),
      'maximum_sampled_file_bytes':max(x[1].get('stat',{}).get('file',0) for x in values),
      'maximum_sampled_PSI_full_avg10':max(x[1]['pressure']['full']['avg10'] for x in values),
      'last_delta_since_startup':last[2].get('paths',{}).get(name),
      'peak_scope':'session peak belongs to this service attempt; ancestor peaks can predate this experiment'}
job=read(ROOT/'logs'/f'{RUN}_job.json')
x0=read(ROOT/'audit/x0'/RUN/'manifest.json')
history=read(ROOT/'logs'/f'{RUN}_history.json')
end=next(v['timestamp']/1000 for k,v in history['status']['messages'] if k=='execution_success')
time_summary={
 'input_setup_until_sampler_seconds':x0['created_unix']-job['submitted_unix'],
 'sampler_wall_including_capture_seconds':x0['finished_unix']-x0['created_unix'],
 'capture_seconds_sum':sum(x['capture_seconds'] for x in x0['captures']),
 'decode_save_after_sampler_seconds':end-x0['finished_unix'],
 'job_seconds':end-job['submitted_unix'],
 'NFE':x0['callback_count'],
 'scope':'Observed end-to-end phase timing; includes audit capture and shared-resource effects. Pure kernel timing is not inferred.'}
result={'created_unix':time.time(),'actual_gate':bound(gate),'resource_log':bound(resource),
        'memory':summary,'timing':time_summary,
        'maximum_sampled_gpu_board_used_mib':max(float(r['sample'].split(',')[1]) for r in rows if r.get('sample_available') and r.get('sample')),
        'gpu_memory_scope':'Whole selected GPU including other users; no own-process peak is inferred.',
        'caution':'Anon maxima are sampled every20s, not exact peak. Historical R96 lacked memory.stat.'}
out=ROOT/'audit/ACTUAL_RESOURCE_SUMMARY.json'
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'file':str(out),'timing':time_summary,'memory':summary},indent=2))
