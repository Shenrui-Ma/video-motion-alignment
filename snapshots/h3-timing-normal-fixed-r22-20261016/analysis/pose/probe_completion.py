"""Read-only R22 success/cleanup gate; CPU metadata only, never signals a PID."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
RUN='r22_s05_seed1313_full6to11'
ROOT='/data5/researcher/h3_runs/timing_normal_fixed_r22_20261016'
SEAL='99c4ee01097bd888259fcc690216c5c2460308fc80339f5af116b8dd1f8c111c'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def validate_binding(b):
    if b.get('approved') is not True or b.get('root')!=ROOT or b.get('run_id')!=RUN or b.get('manifest_sha256')!=SEAL or b.get('sealed_file_count')!=48:raise ValueError('Root-authorized R22 identity/seal binding missing')
    s=b['service_record']
    if type(s['pid']) is not int or s['pid']<=1 or s['port']!=8482 or s['gpu_uuid']!='GPU-REDACTED':raise ValueError('Wrong R22 service')
    if set(s['identity'])!={'uid','start_ticks','cmdline'} or ROOT not in s['identity']['cmdline']:raise ValueError('Incomplete service identity')
    if set(b['role_records'])!={'supervisor','watchdog','controller'}:raise ValueError('All role identities required')
    for r in b['role_records'].values():
        if type(r['pid']) is not int or r['pid']<=1 or set(r['identity'])!={'uid','start_ticks','cmdline'} or ROOT not in r['identity']['cmdline']:raise ValueError('Incomplete child role identity')
    if not b['authorized_admission_sha256'] or any(len(s)!=64 for s in b['authorized_admission_sha256']):raise ValueError('Root admission hash required')
    return b

def proc_identity(pid):
    p=Path('/proc')/str(pid)
    try:return {'uid':p.stat().st_uid,'start_ticks':p.joinpath('stat').read_text().split(') ',1)[1].split()[19], 'cmdline':p.joinpath('cmdline').read_bytes().replace(b'\0',b' ').decode()}
    except FileNotFoundError:return None

def evaluate_documents(b,service,history,cleanup,controller,live,compute):
    validate_binding(b)
    if service!=b['service_record']:raise ValueError('Service record does not match parent authorization')
    if history is not None and history.get('status',{}).get('status_str')=='error':return {'status':'failed','reason':'actual_history_error'}
    if history is None or history.get('status',{}).get('status_str')!='success' or history['status'].get('completed') is not True:return {'status':'waiting','reason':'actual_success_history_pending'}
    if cleanup is None or controller is None:return {'status':'waiting','reason':'cleanup_pending'}
    if cleanup.get('service_record')!=service:raise ValueError('Cleanup belongs to a different service')
    if not cleanup.get('process_absent') or not cleanup.get('own_compute_absent'):return {'status':'waiting','reason':'archived_cleanup_not_complete'}
    if controller.get('status')!='all_queued_jobs_complete' or controller.get('completed')!=[RUN]:raise ValueError('Controller did not complete exactly R22')
    records={'service':service,**b['role_records']};observed={}
    for role,r in records.items():
        actual=live.get(str(r['pid']))
        if actual==r['identity']:return {'status':'waiting','reason':role+'_still_alive'}
        reused=actual is not None
        if any(x['pid']==r['pid'] for x in compute) and not reused:return {'status':'waiting','reason':role+'_driver_compute_residual'}
        observed[role]={'pid':r['pid'],'exact_identity_absent':True,'PID_reused_by_unrelated_process':reused}
    return {'status':'ready','roles':observed,'compute_rows':compute,'no_process_modified':True}

def probe(binding):
    b=validate_binding(read(binding));root=Path(b['root'])
    if sha(root/'deploy_manifest_v1.json')!=SEAL:raise ValueError('Deployment manifest mismatch')
    if sha(root/'configs/admission.json') not in b['authorized_admission_sha256']:raise ValueError('Unregistered administrative admission')
    s=read(root/'processes/service.json')
    for role,wanted in b['role_records'].items():
        actual=read(root/'processes'/f'{role}.json')
        if any(actual[k]!=wanted[k] for k in ('pid','identity')):raise ValueError('Role registry changed: '+role)
    get=lambda p:read(p) if p.is_file() else None
    history=get(root/'logs'/f'{RUN}_history.json');cleanup=get(root/'processes/cleanup.json');controller=get(root/'logs/controller_state.json')
    records=[s,*b['role_records'].values()];live={str(r['pid']):proc_identity(r['pid']) for r in records}
    raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True)
    rows=[]
    for line in raw.splitlines():
        if line.strip():
            gpu,pid,mem=[x.strip() for x in line.split(',')];rows.append({'gpu_uuid':gpu,'pid':int(pid),'used_memory_mib':mem})
    result=evaluate_documents(b,s,history,cleanup,controller,live,rows)
    if result['status']=='ready':
        exit_path=root/'processes'/f'service_exit_{s["pid"]}.json'
        if not exit_path.is_file():return {'status':'waiting','reason':'supervisor_exit_record_pending'}
        e=read(exit_path)
        if e['service_pid']!=s['pid'] or e['service_identity']!=s['identity'] or not(e.get('exit_code')==0 or e.get('signal')==15):raise ValueError('Unexpected service exit')
    return dict(result,observed_unix=time.time(),binding_sha256=sha(binding))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binding',type=Path,required=True)
    print(json.dumps(probe(p.parse_args().binding)))
