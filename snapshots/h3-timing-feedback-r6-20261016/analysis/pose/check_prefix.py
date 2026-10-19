"""Read-only same-host prefix check, after an admitted formal R6 completion."""
from pathlib import Path
import json
import consumer_r6 as consumer

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
R4=Path('/Users/researcher/DevProjects/h3-timing-target-path-r4-20261016')
REMOTE=Path('/data3/researcher/h3_runs/timing_feedback_r6_20261016')
BASE=Path('/data3/researcher/h3_runs/timing_target_path_r4_20261016')
HOST='H3_SERVER_B'
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
RUN='r6_s05_feedback_retry1'


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
    a=R4/'analysis/pose/pilot/r4_s05_native_path_probe_provenance/config.json'
    b=provenance/'config.json'
    graph_gate={'actual_graphs_equal_outside_declared_actuator_and_admin':normalized_without_actuator(json.loads(a.read_text()))==normalized_without_actuator(json.loads(b.read_text())),
                'config_sha256':{str(p):consumer.digest(p) for p in (a,b)},
                'excluded_node':'50: declared native-to-feedback actuator; unchanged model/conditioning connections checked below',
                'admin_keys_ignored':['run_id','audit_dir','source_audit_dir','output_dir','filename_prefix']}
    old_node=json.loads(a.read_text())['50']['inputs'];new_node=json.loads(b.read_text())['50']['inputs']
    graph_gate['actuator_model_positive_connections_equal']=all(old_node[k]==new_node[k] for k in ('model','positive'))
    graph_gate['passed']=graph_gate['actual_graphs_equal_outside_declared_actuator_and_admin'] and graph_gate['actuator_model_positive_connections_equal']
    consumer.save(HERE/'replication/graph_pair_gate.json',graph_gate)
    tool=REMOTE/'scripts/compare_x0_snapshots.py'
    expected=consumer.digest(ROOT/'scripts/compare_x0_snapshots.py')
    actual=consumer.shell(HOST,['python3','-c','import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())',str(tool)]).strip()
    assert actual==expected,'Remote prefix comparison tool differs from archived local source'
    output=REMOTE/'analysis/pose/replication/preintervention_actual_tensors.json'
    command=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,str(tool),str(BASE/'audit/x0/r4_s05_native_path_probe'),str(REMOTE/'audit/x0'/RUN),str(output),'--stems','x0_step005']
    print(consumer.shell(HOST,command),flush=True)
    dest=HERE/'replication/preintervention_actual_tensors.json'
    consumer.copy_from(HOST,output,dest)
    tensors=json.loads(dest.read_text())
    gate={'passed':graph_gate['passed'] and tensors['all_equal'],
          'baseline':'r4_s05_native_path_probe','new_run':RUN,
          'first_preintervention_snapshot':'x0_step005: after zero-based forward5, before first possible feedback forward6',
          'actual_video_audio_bitwise_equal':tensors['all_equal'],'actual_graph_gate_passed':graph_gate['passed'],
          'comparator_sha256':expected,'tensor_result_sha256':consumer.digest(dest),
          'scope':'Necessary causal-prefix control, not a final efficacy result. Complete actual condition/noise pairing remains separately required.'}
    consumer.save(HERE/'replication/preintervention_gate.json',gate)
    print(json.dumps(gate),flush=True)


if __name__=='__main__':main()
