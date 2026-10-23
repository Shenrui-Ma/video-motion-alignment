"""Build a finite diagnostic graph from one exact historical graph, no submission."""
import argparse,copy,hashlib,json
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def build(original,provenance,config):
    if (provenance['case'],provenance['method'])!=('short_0358','native'):raise ValueError('initial release permits only native drinking step9')
    if not provenance['assets_verified'] or not provenance['source_identity_verified']:raise ValueError('asset provenance not verified')
    for node,kind in [('1','UNETLoader'),('41','MiniMaxH3SigmaShift'),('7','BasicGuider'),('9','ManualSigmas'),('50','H3TemporalRouter'),('52','H3X0Readout')]:
        if original[node]['class_type']!=kind:raise ValueError('unexpected historical graph node '+node)
    old=original['50']['inputs']
    fixed={'mode':'native','alpha':1.,'radius':0,'time_offset':0,'start_frame':0,'end_frame':104,'block_start':0,'block_end':50,'step_start':6,'step_end':15}
    if any(old[k]!=v for k,v in fixed.items()):raise ValueError('historical native router configuration differs')
    if original['41']['inputs']!={'model':['1',0],'shift_video':12.,'shift_audio':3.}:raise ValueError('historical shifts differ')
    if original['6']['inputs']['noise_seed']!=2026101701:raise ValueError('historical seed differs')
    root=Path(config['task_root'])
    if not root.is_absolute():raise ValueError('absolute isolated task root required')
    for key in ('state_file','historical_x0_file','noise_file','provenance_file'):
        if not Path(config[key]).is_relative_to(root/'inputs'):raise ValueError('staged input outside isolated inputs: '+key)
    if config['cache_manifest_sha256']!=provenance['source_identity_evidence']['cache_manifest_sha256']:raise ValueError('cache differs from verified original')
    graph={k:copy.deepcopy(original[k]) for k in ('1','41','9')}
    graph['5']={'class_type':'H3TrustedConditionCache','inputs':{'cache_manifest':config['cache_manifest'],'manifest_sha256':config['cache_manifest_sha256']}}
    graph['6']={'class_type':'H3HistoricalNoise','inputs':{'noise_file':config['noise_file'],'noise_sha256':config['noise_sha256'],'seed':2026101701}}
    route={**fixed,'model':['41',0],'positive':['5',0],'schedule':'fixed','run_id':'passive_short0358_native_step009','audit_dir':str(root/'audit_construction')}
    graph['50']={'class_type':'H3StudySchedule','inputs':route}
    graph['7']={'class_type':'BasicGuider','inputs':{'model':['50',0],'conditioning':['5',0]}}
    gate={k:config[k] for k in ('state_file','state_sha256','historical_x0_file','historical_x0_sha256','provenance_file','provenance_sha256')}
    gate.update(noise=['6',0],guider=['7',0],sigmas=['9',0],latent_image=['5',1],output_dir=str(root/'gate_short0358_native_step009'),case='short_0358',method='native',valid_frames=105)
    graph['70']={'class_type':'H3HistoricalReplayGate','inputs':gate}
    changes={'preserved_exact_nodes':['1','41','9'],'router_preserved_parameters':fixed,
      'router_class_substitution':'H3TemporalRouter -> H3StudySchedule fixed; same frozen core EventBlockPatch/route_attention, same selected steps6..14',
      'conditioning_substitution':'SHA-pinned exact historical embedding/tags/positions/reference and zero AV target; no reencoding',
      'noise_substitution':'SHA-pinned exact original two FP32 AV noise streams; no regeneration',
      'removed_old_writers':['H3X0Readout','H3PairConditionSnapshot','H3EventAuditReference','H3EventAuditNoise','SamplerCustomAdvanced','SaveVideo'],
      'no_VAE_no_video_no_full_sampler':True,'all_new_writer_paths':[route['audit_dir'],gate['output_dir']],
      'physical_model_calls':2,'historical_step_zero_based':9,'capture_layer_zero_based':25,
      'old_graph_canonical_sha256':canonical(original),'derived_graph_canonical_sha256':canonical(graph),'status':'review_only_not_submitted'}
    for nid in ('1','41','9'):
        if graph[nid]!=original[nid]:raise AssertionError('frozen node changed')
    return graph,changes

def main():
    p=argparse.ArgumentParser();p.add_argument('--original',required=True);p.add_argument('--provenance',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    original=json.loads(Path(a.original).read_text());prov=json.loads(Path(a.provenance).read_text());cfg=json.loads(Path(a.config).read_text())
    if sha(a.provenance)!=cfg['provenance_sha256']:raise ValueError('provenance byte identity differs')
    if sha(a.original)!=prov['historical_graph_sha256']:raise ValueError('original graph byte identity differs from provenance')
    graph,diff=build(original,prov,cfg);out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    (out/'graph.json').write_text(json.dumps(graph,indent=2,ensure_ascii=False)+'\n')
    diff.update(original_file_sha256=sha(a.original),provenance_sha256=sha(a.provenance),config_sha256=sha(a.config),graph_file_sha256=sha(out/'graph.json'))
    (out/'GRAPH_DIFF.json').write_text(json.dumps(diff,indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
