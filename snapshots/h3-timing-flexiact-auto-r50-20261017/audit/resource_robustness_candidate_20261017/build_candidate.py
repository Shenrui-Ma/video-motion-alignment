"""Construct isolated overlays; never write into either producer tree."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOTS = {
    'r50': HERE.parents[1],
    'r55': Path('/Users/researcher/DevProjects/h3-timing-ivebench-auto-r55-20261017'),
}
FILES = ['extensions/H3AutomaticWindowRouter/transport.py',
         'scripts/run_observer.py', 'scripts/decode_live_child.py',
         'scripts/gpu_release_gate.py']


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Source drift or ambiguous replacement: ' + old[:100])
    return text.replace(old, new, 1)


def function_span(text, name):
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = text.splitlines(keepends=True)
    return ''.join(lines[node.lineno - 1:node.end_lineno])


def transport(text):
    text = replace_once(text, function_span(text, 'run_child'), (HERE / 'fragments/supervise.py.txt').read_text())
    start = text.index('def validate_separate_decoder(')
    end = text.index('def validate_response(', start)
    text = text[:start] + (HERE / 'fragments/admission.py.txt').read_text() + '\n' + text[end:]
    old = function_span(text, 'validate_response')
    new = '''def validate_response(response,r,request_sha):
 require(response.get('status')=='complete' and response.get('request_sha256')==request_sha,'stale/incomplete response')
 for key in ('request_id','physical_index','nfe_index','endpoint_file_sha256','condition_sha256','reference_sha256','seed','sigma'):
  require(response.get(key)==r.get(key),'response identity differs: '+key)
 require(response.get('decoder_released_before_pose') is True,'decoder lifecycle incomplete')
 admission=response['decoder_admission']
 require(admission['uuid']==DECODER_UUID and admission['main_compute_parent']==r['parent'],'response decoder/main placement differs')
 require(admission['memory_free_mib']>=45000 and admission['memory_used_mib']<=1024 and admission['utilization_percent']==0,'response decoder admission invalid')
 released=response['after_decoder_release']
 require(released['schema']=='h3-own-decoder-release-v1' and released['gpu_uuid']==DECODER_UUID,'response release schema/device differs')
 require(released['child_identity']==response['decoder']['process'] and released['original_generation_absent'] is True,'response original decoder generation remains')
 require(released['nvml_pid_absent'] is True or released['pid_reused'] is True,'response original decoder NVML tail remains')
 for key in ('decoder','pose_process'):
  require(response[key]['returncode']==0,'nonzero child exit')
 return response
'''
    return replace_once(text, old, new)


def observer(text):
    a = text.index('  while True:\n')
    b = text.index("  admission=t.admission_document", a)
    text = text[:a] + '''  resource_deadline=time.monotonic()+600
  record['decoder_admission']=t.wait_decoder_admission(r['parent'],deadline=resource_deadline,audit_path=d/'observer_admission.jsonl')
''' + text[b:]
    text = replace_once(text, "record['owned_GPU_cards']=t.validate_owned_gpu_limit(own_gpus(),admission['permitted_compute_processes'])", "record['owned_GPU_cards']=record['decoder_admission']['owned_GPU_cards']")
    text = replace_once(text, "env=dict(os.environ,CUDA_VISIBLE_DEVICES=t.DECODER_UUID,OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')", "env=dict(os.environ,CUDA_VISIBLE_DEVICES=t.DECODER_UUID,OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',H3_DECODER_RESOURCE_DEADLINE=str(resource_deadline),H3_DECODER_EXECUTION_MARKER=str(d/'decoder_cuda_started.json'))")
    text = replace_once(text, "  record['decoder']=t.run_child(args,env,d,'decoder',180,own)", "  decoder_budget=max(0,resource_deadline-time.monotonic())+180\n  record['decoder']=t.run_child(args,env,d,'decoder',decoder_budget,own,execution_started_path=d/'decoder_cuda_started.json',execution_timeout=180)")
    a = text.index('  # A new unrelated process')
    b = text.index("  env['CUDA_VISIBLE_DEVICES']=''", a)
    text = text[:a] + '''  from gpu_release_gate import wait_own_child_released
  record['after_decoder_release']=wait_own_child_released(t.DECODER_UUID,record['decoder'],t.identity,audit_path=d/'decoder_release.jsonl')
  record['decoder_released_before_pose']=True
''' + text[b:]
    return text


def decoder(text):
    text = replace_once(text, "    admission = t.separate_decoder_admission(REQUEST['parent'],args.gpu_uuid)", '''    resource_deadline = float(os.environ.get('H3_DECODER_RESOURCE_DEADLINE', time.monotonic()+600))
    admission = t.wait_decoder_admission(REQUEST['parent'],args.gpu_uuid,deadline=resource_deadline,audit_path=args.request.parent/'decoder_admission.jsonl')''')
    text = replace_once(text, "    t.separate_decoder_admission(REQUEST['parent'],args.gpu_uuid)  # exact parent+headroom recheck", '''    admission = t.wait_decoder_admission(REQUEST['parent'],args.gpu_uuid,deadline=resource_deadline,audit_path=args.request.parent/'decoder_admission.jsonl')
    t.require(t.sha(args.request)==REQUEST_SHA,'request changed during resource wait')
    t.request(args.request)  # revalidate endpoint/data binding immediately before CUDA
    marker = os.environ.get('H3_DECODER_EXECUTION_MARKER')
    if marker is not None:
        marker = t.inside(marker,t.ROOT/'audit/observations')
        t.require(marker==args.request.parent.resolve()/'decoder_cuda_started.json','execution marker outside current observation')
        own_identity = t.identity(os.getpid())
        t.require(own_identity is not None,'decoder execution identity unavailable')
        t.write_new(marker,{'schema':'h3-child-execution-start-v1','identity':own_identity,'started_monotonic':time.monotonic()})''')
    return text


def main():
    records = {}
    for name, root in ROOTS.items():
        entries = {}; patch = []
        for rel in FILES:
            source = (root / rel).read_text()
            if rel.endswith('transport.py'): result = transport(source)
            elif rel.endswith('run_observer.py'): result = observer(source)
            elif rel.endswith('decode_live_child.py'): result = decoder(source)
            else: result = source + '\n\n' + (HERE / 'fragments/release.py.txt').read_text()
            ast.parse(result)
            for folder, value in [('before', source), ('overlay', result)]:
                target = HERE / name / folder / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(value)
            entries[rel] = {'before_sha256': hashlib.sha256(source.encode()).hexdigest(),
                            'after_sha256': hashlib.sha256(result.encode()).hexdigest()}
            patch += difflib.unified_diff(source.splitlines(True), result.splitlines(True),
                                         fromfile='a/' + rel, tofile='b/' + rel)
        (HERE / name / 'candidate.patch').write_text(''.join(patch))
        records[name] = {'source_root': str(root), 'files': entries,
                         'patch_sha256': hashlib.sha256(''.join(patch).encode()).hexdigest()}
    (HERE / 'SOURCE_SNAPSHOTS.json').write_text(json.dumps(records, indent=2)+'\n')


if __name__ == '__main__': main()
