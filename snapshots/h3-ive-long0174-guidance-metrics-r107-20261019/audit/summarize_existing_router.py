"""Read only existing sampled router stats; no model execution."""
from pathlib import Path
import hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[1]
def bound(p):return {'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def summary(p):
 a=json.loads(p.read_text());fs=[f for f in a['forward_summaries'] if f.get('layer_stats')]
 assert a['mode']=='mass_preserve' and a['alpha']==1
 rows=[x for f in fs for x in f['layer_stats']]
 def stats(key):
  vals=[r[key] for r in rows]
  return {'n':len(vals),'mean':statistics.mean(vals),'median':statistics.median(vals),'min':min(vals),'max':max(vals)}
 return {'source':bound(p),'run_id':a['run_id'],'scope':a['metric_scope'],'routed_calls':a['routed_calls'],
  'm_ref':stats('ref_mass_mean'),'correction_over_native_attention_output_rms':stats('correction_ratio'),
  'per_step':[{'step':f['forward_index'],'m_ref':f['sampled_ref_mass_mean'],'correction_ratio':f['sampled_correction_ratio_mean'],'max_layer_correction_ratio':f['sampled_correction_ratio_max']} for f in fs],
  'per_layer':[{'block':b,'m_ref':statistics.mean(r['ref_mass_mean'] for r in rows if r['block']==b),'correction_ratio':statistics.mean(r['correction_ratio'] for r in rows if r['block']==b)} for b in range(50)]}
paths=[ROOT/'incoming/long_0174/router.json']
for run in ['h3-flexiact-expanded-metrics-r85-20261018','h3-ive-subject-capacity-metrics-r89-20261018']:
 paths.extend(sorted((ROOT.parent/run/'incoming').glob('*/forced_router.json')))
results=[summary(p) for p in paths]
core=ROOT.parent/'h3-timing-ive-long0174-guidance-r107-20261019/extensions/H3TemporalRouter/core.py'
x={'schema':'existing-sampled-routing-statistics-v1','code':bound(core),'formula':'RMS(sample(after-before)) / max(RMS(sample(before)),1e-8); before and after are attention outputs on affected canvas queries, before output projection and residual addition. m_ref is exp(LSE_ref-LSE_all).','sampling':'At most8heads x128queries x16channels per layer. All layers and routed steps have one sampled statistic each. Means across layers/steps use equal weighting. Not a whole-network/global RMS or action measure.','results':results,
 'conclusion':'R107 correction is material in the recorded attention-output sample; current records do not support the explanation that almost no signal was applied. Temporal redistribution is inside the reference-video group and preserves its original total mass. Cause of failed motion alignment remains open.',
 'not_recorded':['post-output-projection correction norm','post-residual hidden-state relative norm','subject/occlusion-specific correction statistics','direct action timing signal inside DiT']}
out=ROOT/'audit/EXISTING_ROUTER_STATISTICS.json'
with out.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
print('path',out)
for a in results:print(a['run_id'],a['m_ref'],a['correction_over_native_attention_output_rms'])
print('R107_by_step',results[0]['per_step'])
