"""Read-only same-host prefix check, after an admitted formal R9 completion."""
from pathlib import Path
import json
import argparse
import consumer_r11 as consumer

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
R6=Path('/Users/researcher/DevProjects/h3-timing-feedback-r6-20261016')
REMOTE=Path('/data3/researcher/h3_runs/timing_schedule_controls_r11_20261016')
BASE=Path('/data3/researcher/h3_runs/timing_feedback_r6_20261016')
HOST='H3_SERVER_B'
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
RUN=None


def normalized_without_actuator(graph):
    graph=json.loads(json.dumps(graph))
    del graph['50']
    for node in graph.values():
        for name in ('run_id','audit_dir','source_audit_dir','output_dir','filename_prefix'):
            node.get('inputs',{}).pop(name,None)
    return graph


def main():
    global RUN
    parser=argparse.ArgumentParser();parser.add_argument("--run-id",required=True);args=parser.parse_args();RUN=consumer.formal_run(args.run_id)
    provenance=HERE/'pilot'/(RUN+'_provenance')
    manifest=json.loads((provenance/'intake_manifest.json').read_text())
    assert consumer.digest(HERE/'raw'/manifest['relative_video'])==manifest['video_sha256']
    a=R6/'analysis/pose/pilot/r6_s05_feedback_retry1_provenance/config.json'
    b=provenance/'config.json'
    graph_gate={'actual_graphs_equal_outside_declared_actuator_and_admin':normalized_without_actuator(json.loads(a.read_text()))==normalized_without_actuator(json.loads(b.read_text())),
                'config_sha256':{str(p):consumer.digest(p) for p in (a,b)},
                'excluded_node':'50: feedback operator implementation change is declared; all non-policy/mask node inputs are independently required identical below',
                'admin_keys_ignored':['run_id','audit_dir','source_audit_dir','output_dir','filename_prefix']}
    old_node=json.loads(a.read_text())['50']['inputs'];new_node=json.loads(b.read_text())['50']['inputs']
    graph_gate['actuator_model_positive_connections_equal']=all(old_node[k]==new_node[k] for k in ('model','positive'))
    def normalize_inputs(node):
        return {k:v for k,v in node.items() if k not in ('run_id','audit_dir','policy','fixed_indices')}
    graph_gate['actuator_inputs_equal_outside_declared_policy_mask_admin']=normalize_inputs(old_node)==normalize_inputs(new_node)
    graph_gate['passed']=graph_gate['actual_graphs_equal_outside_declared_actuator_and_admin'] and graph_gate['actuator_model_positive_connections_equal'] and graph_gate['actuator_inputs_equal_outside_declared_policy_mask_admin']
    consumer.save(HERE/'replication'/RUN/'graph_pair_gate.json',graph_gate)
    tool=REMOTE/'scripts/compare_x0_snapshots.py'
    expected=consumer.digest(ROOT/'scripts/compare_x0_snapshots.py')
    actual=consumer.shell(HOST,['python3','-c','import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())',str(tool)]).strip()
    assert actual==expected,'Remote prefix comparison tool differs from archived local source'
    output=REMOTE/'analysis/pose/replication'/RUN/'preintervention_actual_tensors.json'
    command=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,str(tool),str(BASE/'audit/x0/r6_s05_feedback_retry1'),str(REMOTE/'audit/x0'/RUN),str(output),'--stems','x0_step005']
    print(consumer.shell(HOST,command),flush=True)
    dest=HERE/'replication'/RUN/'preintervention_actual_tensors.json'
    consumer.copy_from(HOST,output,dest)
    tensors=json.loads(dest.read_text())
    gate={'passed':graph_gate['passed'] and tensors['all_equal'],
          'baseline':'r6_s05_feedback_retry1','new_run':RUN,
          'first_preintervention_snapshot':'x0_step005: after zero-based forward5, before first possible feedback forward6',
          'actual_video_audio_bitwise_equal':tensors['all_equal'],'actual_graph_gate_passed':graph_gate['passed'],
          'comparator_sha256':expected,'tensor_result_sha256':consumer.digest(dest),
          'scope':'Necessary causal-prefix control, not a final efficacy result. Complete actual condition/noise pairing remains separately required.'}
    consumer.save(HERE/'replication'/RUN/'preintervention_gate.json',gate)
    print(json.dumps(gate),flush=True)
    if not gate['passed']:raise ValueError('Preintervention causal/graph gate failed')
    # Registered while both new outputs were unavailable: operational schedules
    # coincide through index10, independently of proposed passive observations.
    if RUN=='r11_s05_continuous6to19':
        shared_run='r2_s05_full_6to14'
        shared_root=Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016')
        shared_mask=list(range(6,11))
    else:
        shared_run='r6_s05_feedback_retry1'
        shared_root=BASE
        shared_mask=[6,8,9,10]
    shared_output=REMOTE/'analysis/pose/replication'/RUN/'index10_shared_actual_tensors.json'
    command=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,str(tool),str(shared_root/'audit/x0'/shared_run),str(REMOTE/'audit/x0'/RUN),str(shared_output),'--stems','x0_step010']
    print(consumer.shell(HOST,command),flush=True)
    shared_local=HERE/'replication'/RUN/'index10_shared_actual_tensors.json'
    consumer.copy_from(HOST,shared_output,shared_local)
    shared_result=json.loads(shared_local.read_text())
    consumer.save(HERE/'replication'/RUN/'schedule_shared_prefix_gate.json',{
        'passed':shared_result['all_equal'],'baseline':shared_run,'new_run':RUN,
        'shared_active_indices_through10':shared_mask,'checkpoint':'x0_step010',
        'actual_video_audio_bitwise_equal':shared_result['all_equal'],
        'tensor_result_sha256':consumer.digest(shared_local),'current_config_sha256':consumer.digest(b),
        'scope':'Same operational routing history through index10. Complete actual input/noise and full masks are separately bound by actual_input_noise_pair and operator gates. A mismatch limits historical-arm causal attribution; it does not erase the new output.'})


if __name__=='__main__':main()
