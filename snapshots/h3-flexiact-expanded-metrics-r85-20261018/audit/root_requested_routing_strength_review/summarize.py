from pathlib import Path
import json,hashlib,statistics,math
O=Path(__file__).resolve().parent; D=Path('/Users/researcher/DevProjects')
def bind(p):return {'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
rows=[]
for tag,consumer,prod,pair in [('R85','h3-flexiact-expanded-metrics-r85-20261018','h3-timing-flexiact-expanded-r85-20261018','one_leg__movie_man_9'),('R73','h3-ivebench-expanded-metrics-r73-20261018','h3-timing-ivebench-expanded-r73-20261018','short_0252')]:
 p=D/consumer/'incoming'/pair; gate=p/'PAIR_RUNTIME_GATE.json';G=json.loads(gate.read_text());assert G['passed'] is True
 row={'run':tag,'pair':pair,'gate':bind(gate),'core':bind(D/prod/'extensions/H3TemporalRouter/core.py'),'arms':{}}
 for arm in ['native','forced']:
  f=p/(arm+'_router.json');r=json.loads(f.read_text());active=[s for s in r['forward_summaries'] if s['routed_blocks']]
  assert r['completed_forward_calls']==20 and r['routed_calls']==(450 if arm=='forced' else 0)
  a={'input':bind(f),'completed_forward_calls':r['completed_forward_calls'],'routed_calls':r['routed_calls'],'router_status_string':r['status'],'method':{k:r[k] for k in ['mode','alpha','radius','time_offset','block_interval_half_open','step_interval_half_open','pixel_interval_inclusive']},'validated_layout':r['validated_layout'],'first_attention':r['first_attention'],'per_active_step':[],'temporal_readouts':[]}
  for s in active:
   assert s['routed_blocks']==50 and len(s['layer_stats'])==50 and all(x['finite'] for x in s['layer_stats'])
   a['per_active_step'].append({k:v for k,v in s.items() if k!='layer_stats'})
  if active:
   a['equal_step_layer_summary']={
    'sampled_ref_mass_mean':statistics.mean(s['sampled_ref_mass_mean'] for s in active),
    'sampled_correction_ratio_mean':statistics.mean(s['sampled_correction_ratio_mean'] for s in active),
    'maximum_layer_sampled_correction_ratio':max(s['sampled_correction_ratio_max'] for s in active),
    'n_step_layer_records':sum(len(s['layer_stats']) for s in active),
    'absolute_correction_rms_available':any('sampled_component_correction_rms_mean' in s for s in active)}
  for x in r['temporal_readouts']:
   Q=x['query_records'];assert all(abs(sum(q['p_ref_frame'])-1)<1e-5 for q in Q)
   a['temporal_readouts'].append({'step':x['forward_index'],'block':x['block_index'],'scope':x['scope'],'query_bins':len(Q),'reference_bins':x['reference_temporal_bins'],'head_indices':x['head_indices'],'spatial_indices':x['spatial_indices'],'same_bin_conditional_mean':statistics.mean(q['same_bin_mass'] for q in Q),'within_one_bin_conditional_mean':statistics.mean(q['within_one_bin_mass'] for q in Q),'entropy_nats_mean':statistics.mean(q['entropy_nats'] for q in Q)})
  row['arms'][arm]=a
 rows.append(row)
assert len({r['core']['sha256'] for r in rows})==1
out={'scope':'Post-hoc scalar audit only, two heterogeneous completed samples. No causal inference, no new model execution, no PT reads.','rows':rows}
(O/'EVIDENCE.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({r['run']:r['arms']['forced']['equal_step_layer_summary'] for r in rows},indent=2))
