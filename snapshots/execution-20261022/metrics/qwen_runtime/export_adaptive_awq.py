"""Read-only AWQ score export; keep evaluator and immutable input provenance per row."""
from pathlib import Path
import argparse, hashlib, json, math, subprocess, time
Q=Path(__file__).resolve().parent
E=Q.parent.parent
METRICS={'IS':'instruction_satisfaction','CF':'content_fidelity'}

def load(path):
    return json.loads(path.read_text())

def validate_score(record, job, prepared, expected_sha=None):
    """Fail closed if the result or prepared target video belongs to another input."""
    result=record['value']; reasons=[]
    if result.get('status')!='done': return {'status':'pending','reason':result.get('status','missing')}
    if result.get('job_id')!=job['id'] or result.get('task_id')!=job['task_id'] or result.get('method')!=job['method']:
        reasons.append('result_identity_mismatch')
    sha=job.get('sha256')
    if not sha or (expected_sha is not None and sha!=expected_sha): reasons.append('video_sha_mismatch')
    if not prepared or prepared.get('sha256')!=sha: reasons.append('prepared_video_sha_mismatch')
    if prepared and (prepared.get('frames')!=job.get('valid_frames') or prepared.get('crop_xywh')!=job.get('crop_xywh')): reasons.append('prepared_geometry_mismatch')
    evaluator=result.get('evaluator',{})
    if not evaluator.get('configuration_id'): reasons.append('missing_evaluator_configuration')
    try: finite=math.isfinite(float(result['score']))
    except (ValueError,TypeError,KeyError): finite=False
    if not finite: reasons.append('invalid_score')
    row={'status':'invalid_input' if reasons else 'done','score':None if reasons else result['score'],'input_video_sha256':sha,'configuration_id':evaluator.get('configuration_id'),'evaluator':evaluator,'official_commit':result.get('official_commit'),'original_result_file':record['source_file'],'original_result_file_sha256':record['source_sha256']}
    if reasons: row['reasons']=reasons
    return row

def planned_rows():
    batch=E/'innovation/adaptive_strength_20261023/batch'
    jobs=load(batch/'jobs.json')['jobs']+load(batch/'anchor_pilots/jobs.json')['jobs']
    if (batch/'field_pilots/jobs.json').exists(): jobs += load(batch/'field_pilots/jobs.json')['jobs']
    if (batch/'layer_pilots/jobs.json').exists(): jobs += load(batch/'layer_pilots/jobs.json')['jobs']
    for cohort in ['field_extension_two','role5_pilots','uniform_pilots']:
        path=batch/cohort/'jobs.json'
        if path.exists(): jobs += load(path)['jobs']
    fixed=E/'innovation/feature_gain_field_fixed_budget/pilots/jobs.json'
    if fixed.exists(): jobs += load(fixed)['jobs']
    result=[]; controls={}
    for j in jobs:
        m=j['metadata'];result.append({'job_id':j['id'],'task_id':m['task_id'],'method':m['method'],'expected_sha':None})
        for method,v in m['comparison_outputs'].items():
            key=(m['task_id'],method)
            assert key not in controls or controls[key]['expected_sha']==v['sha256']
            controls[key]={'job_id':m['task_id']+'__'+method,'task_id':m['task_id'],'method':method,'expected_sha':v['sha256']}
    return list(controls.values())+result

def manifests():
    main=load(Q/'host41/manifest.main.json')['jobs']
    extra=load(Q/'host60_extra/snapshot/extra26_20261022/expected_manifest.json')['jobs']
    return {j['id']:j for j in main+extra}

def prepared_receipts():
    out={}
    paths=list(Q.glob('host41*/input_snapshot.json'))+list(Q.glob('host41*/sync_runs/*/source_snapshot.json'))
    for p in paths:
        for folder in load(p).get('folders',[]):
            item=folder.get('prepared',{});key=(folder['path'],item.get('sha256'))
            if key in out: assert out[key]==item, 'conflicting immutable prepared receipt'
            out[key]=item
    return out

def refresh_records(ids):
    code="""from pathlib import Path
import json,sys,hashlib
request=json.load(sys.stdin);r=Path(request['root']);out={}
for job in request['ids']:
 for metric in ['instruction_satisfaction','content_fidelity']:
  p=r/job/(metric+'.json')
  if p.exists():
   raw=p.read_bytes();out[job+'/'+metric]={'source_file':str(p),'source_sha256':hashlib.sha256(raw).hexdigest(),'value':json.loads(raw)}
print(json.dumps(out))
"""
    sources=[('H3_HOST_PRIMARY','/data4/research-user/h3_metrics_qwen_20261022/qwen_runtime/evaluation_awq/results'),('H3_HOST_AUXILIARY','/data3/research-user/h3_metrics_20261022/qwen_runtime/extra26_20261022/evaluation_awq/results')]
    output={}
    for host,root in sources:
        request={'root':root,'ids':ids}
        # JSON is sent only to stdin; shell code is a constant, no user interpolation.
        import shlex
        run=subprocess.run(['ssh','-o','ConnectTimeout=12',host,shlex.join(['python3','-c',code])],input=json.dumps(request),text=True,capture_output=True,check=True,timeout=45)
        for key,value in json.loads(run.stdout).items():
            value['source_host']=host
            assert key not in output, 'duplicate job results in two producer roots'
            output[key]=value
    p=Q/'adaptive_awq_source_records.json';p.write_text(json.dumps(output,ensure_ascii=False,indent=2));return output

def export(refresh=False):
    plans=planned_rows(); jobs=manifests();prepared=prepared_receipts()
    records=refresh_records([r['job_id'] for r in plans]) if refresh else load(Q/'adaptive_awq_source_records.json')
    out={'schema':1,'created_at':time.time(),'score_scale':'official raw score 1–5','configuration_policy':'each score retains its actual evaluator; original precision and different AWQ execution configurations remain separate','jobs':{}}
    for plan in plans:
        jid=plan['job_id'];job=jobs.get(jid);row={k:v for k,v in plan.items() if k!='expected_sha'};row['metrics']={}
        for label,metric in METRICS.items():
            record=records.get(jid+'/'+metric)
            if not job or not record: row['metrics'][label]={'status':'pending','reason':'result_not_completed_or_not_returned'};continue
            target=Path(job['target_frames_parent'])/Path(job['metadata']['src_video_name']).stem
            relative=str(target.relative_to('/data/research-user/h3_metrics_20261022'))
            receipt=prepared.get((relative,job.get('sha256')))
            row['metrics'][label]=validate_score(record,job,receipt,plan['expected_sha'])
            row['metrics'][label]['source_host']=record['source_host']
        out['jobs'][jid]=row
    out['counts']={status:sum(m['status']==status for r in out['jobs'].values() for m in r['metrics'].values()) for status in ['done','pending','invalid_input']}
    p=Q/'adaptive_awq_scores.json';temp=p.with_suffix('.tmp');temp.write_text(json.dumps(out,ensure_ascii=False,indent=2));temp.replace(p);return out

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args();result=export(args.refresh);print(json.dumps({'output':str(Q/'adaptive_awq_scores.json'),'counts':result['counts']}))
