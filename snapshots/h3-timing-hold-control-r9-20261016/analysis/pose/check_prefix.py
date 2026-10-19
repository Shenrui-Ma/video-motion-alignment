"""Read-only same-host prefix check, after an admitted formal R9 completion."""
from pathlib import Path
import json
import consumer_r9 as consumer

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
R6=Path('/Users/researcher/DevProjects/h3-timing-feedback-r6-20261016')
REMOTE=Path('/data3/researcher/h3_runs/timing_hold_control_r9_20261016')
BASE=Path('/data3/researcher/h3_runs/timing_feedback_r6_20261016')
HOST='H3_SERVER_B'
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
RUN='r9_s05_hold2'


def normalized_without_actuator(graph):
    graph=json.loads(json.dumps(graph))
    del graph['50']
    for node in graph.values():
        for name in ('run_id','audit_dir','source_audit_dir','output_dir','filename_prefix'):
            node.get('inputs',{}).pop(name,None)
    return graph


def main():
    provenance=HERE/'pilot'/(RUN+'_provenance')
    manifest=json.loads((provenance/'intake_manifest.json').read_text())
    assert consumer.digest(HERE/'raw'/manifest['relative_video'])==manifest['video_sha256']
    a=R6/'analysis/pose/pilot/r6_s05_feedback_retry1_provenance/config.json'
    b=provenance/'config.json'
    graph_gate={'actual_graphs_equal_outside_declared_actuator_and_admin':normalized_without_actuator(json.loads(a.read_text()))==normalized_without_actuator(json.loads(b.read_text())),
                'config_sha256':{str(p):consumer.digest(p) for p in (a,b)},
                'excluded_node':'50: feedback operator implementation change is declared; all node inputs are independently required identical below',
                'admin_keys_ignored':['run_id','audit_dir','source_audit_dir','output_dir','filename_prefix']}
    old_node=json.loads(a.read_text())['50']['inputs'];new_node=json.loads(b.read_text())['50']['inputs']
    graph_gate['actuator_model_positive_connections_equal']=all(old_node[k]==new_node[k] for k in ('model','positive'))
    def normalize_inputs(node):
        return {k:v for k,v in node.items() if k not in ('run_id','audit_dir')}
    graph_gate['all_actuator_inputs_equal_outside_admin']=normalize_inputs(old_node)==normalize_inputs(new_node)
    graph_gate['passed']=graph_gate['actual_graphs_equal_outside_declared_actuator_and_admin'] and graph_gate['actuator_model_positive_connections_equal'] and graph_gate['all_actuator_inputs_equal_outside_admin']
    consumer.save(HERE/'replication/graph_pair_gate.json',graph_gate)
    tool=REMOTE/'scripts/compare_x0_snapshots.py'
    expected=consumer.digest(ROOT/'scripts/compare_x0_snapshots.py')
    actual=consumer.shell(HOST,['python3','-c','import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())',str(tool)]).strip()
    assert actual==expected,'Remote prefix comparison tool differs from archived local source'
    output=REMOTE/'analysis/pose/replication/preintervention_actual_tensors.json'
    command=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,str(tool),str(BASE/'audit/x0/r6_s05_feedback_retry1'),str(REMOTE/'audit/x0'/RUN),str(output),'--stems','x0_step005']
    print(consumer.shell(HOST,command),flush=True)
    dest=HERE/'replication/preintervention_actual_tensors.json'
    consumer.copy_from(HOST,output,dest)
    tensors=json.loads(dest.read_text())
    gate={'passed':graph_gate['passed'] and tensors['all_equal'],
          'baseline':'r6_s05_feedback_retry1','new_run':RUN,
          'first_preintervention_snapshot':'x0_step005: after zero-based forward5, before first possible feedback forward6',
          'actual_video_audio_bitwise_equal':tensors['all_equal'],'actual_graph_gate_passed':graph_gate['passed'],
          'comparator_sha256':expected,'tensor_result_sha256':consumer.digest(dest),
          'scope':'Necessary causal-prefix control, not a final efficacy result. Complete actual condition/noise pairing remains separately required.'}
    consumer.save(HERE/'replication/preintervention_gate.json',gate)
    print(json.dumps(gate),flush=True)
    if not gate['passed']:raise ValueError('Preintervention causal/graph gate failed')


if __name__=='__main__':main()
