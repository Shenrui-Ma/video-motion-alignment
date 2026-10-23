"""CPU-only identity and graph-isolation checks for one frozen reproduction."""
from pathlib import Path
import hashlib,json
D=Path(__file__).parent;E=D.parents[1];P=E/'innovation/signed_phase_calibration_20261023';F=E/'innovation/feature_gain_field';B=E/'innovation/adaptive_strength_20261023/batch'
R='/data/research-user/h3_inference_20261023/field_environment_reproduction_20261023'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(graph,jobs):
 old=json.loads((P/'replay_live_pair/plans/global_weak_graph.json').read_text());original=json.loads((B/'field_pilots/graphs/adapt41_short_0358_temporal_gain_field.json').read_text())
 assert set(graph)==set(old)
 assert {k for k in graph if graph[k]!=old[k]}=={'14','50','52'}
 job=jobs['jobs'][0];tid=job['id'];assert len(jobs['jobs'])==1 and job['max_attempts']==1
 assert graph['50']['class_type']=='H3TemporalGainField'
 expected=original['50']['inputs'].copy();expected.update(run_id=tid,audit_dir=R+'/audit/feature_gain_field');assert graph['50']['inputs']==expected
 expected=original['52']['inputs'].copy();expected.update(run_id=tid,output_dir=R+'/audit/timing');assert graph['52']['class_type']=='H3StudyTiming' and graph['52']['inputs']==expected
 assert graph['14']['inputs']['filename_prefix']==tid+'/'+tid
 assert job['expected_output_prefix']==tid+'/'
 m=job['metadata'];assert m['remote_root']==R and m['actual_producer']==m['producer_host']=='host81_field_environment_reproduction'
 assert m['cohort']=='field_environment_reproduction' and m['method']=='temporal_gain_field'
 assert 'calibration pair' not in m['comparison_scope']
 assert graph['7']['inputs']['model']==['52',0]
 assert not any(n['class_type'] in ['H3LivePhaseObservation','H3HistoricalReplayGate','H3X0Readout'] for n in graph.values())
 return True
if __name__=='__main__':
 g=json.loads((D/'graph.json').read_text());j=json.loads((D/'jobs.json').read_text());check(g,j)
 ready=json.loads((F/'READY.json').read_text());runtime={n:h for n,h in ready['source_shas'].items() if not n.startswith('test_')}
 for n,h in runtime.items():assert sha(F/n)==h,n
 out={'status':'science_and_isolation_verified_not_released','changed_nodes':['14','50','52'],'graph_sha256':sha(D/'graph.json'),'jobs_sha256':sha(D/'jobs.json'),'live_weak_graph_sha256':sha(P/'replay_live_pair/plans/global_weak_graph.json'),'original_field_graph_sha256':sha(B/'field_pilots/graphs/adapt41_short_0358_temporal_gain_field.json'),'field_ready_sha256':sha(F/'READY.json'),'frozen_six_sources':runtime,'identical_nodes':[k for k in g if k not in ['14','50','52']],'scope':'one original frozen field trajectory; independent cohort; no full inference until review and root release'}
 (D/'SCIENCE_CHECK.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
