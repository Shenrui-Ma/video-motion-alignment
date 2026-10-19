"""Standalone Native019 recovery; calls the exact frozen live decoder unchanged."""
import argparse,json,os,subprocess,time,types
from pathlib import Path
import common as c

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--parent-json',required=True);p.add_argument('--admission',type=Path,required=True);a=p.parse_args()
    c.require(c.PRODUCER==c.REMOTE,'recovery decode requires exact remote runtime')
    directory=a.directory.resolve();c.require(directory.is_relative_to(c.HERE/'runs'),'recovery output outside owned runs')
    root_admission=c.read(a.admission);admission_sha=c.sha(a.admission);uuid=root_admission['gpu_uuid'];parent=json.loads(a.parent_json)
    live=c.load_live();original=live.t;request=c.original_request();bindings=original.bindings(external=False)
    copied=directory/'request.json';c.require(c.sha(copied)==c.REQUEST_SHA,'recovery request must retain original bytes')
    original.install_lifetime_guard(parent)
    own=original.identity(os.getpid());c.require(own is not None,'recovery child identity missing')
    c.write_new(directory/'decoder_ready.json',{'schema':'r53-recovery-preCUDA-v1','identity':own,'gpu_uuid':uuid,'admission_sha256':admission_sha,'original_request_sha256':c.REQUEST_SHA,'endpoint_sha256':c.ENDPOINT_SHA})
    deadline=time.monotonic()+600
    while not (directory/'decoder_go.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('root recovery decoder permission did not arrive')
        time.sleep(.25)
    go=c.read(directory/'decoder_go.json')
    c.require(go.get('root_approved') is True and go['identity']==own and go['gpu_uuid']==uuid and go['admission_sha256']==admission_sha,'root recovery decoder identity changed')
    def recovery_request(path):
        c.require(Path(path).resolve()==copied and c.sha(path)==c.REQUEST_SHA,'copied recovery request differs')
        c.require(c.sha(request['endpoint_file'])==c.ENDPOINT_SHA,'recovery endpoint changed')
        return request
    def recovery_admission(historical_parent,selected):
        c.require(historical_parent==request['parent'] and selected==uuid,'historical provenance or selected GPU differs')
        c.require(original.alive(parent),'current recovery supervisor disappeared')
        c.require(c.sha(a.admission)==admission_sha,'root recovery admission changed')
        idle=live.assert_idle_gpu(uuid)
        raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
        rows=[{'gpu_uuid':u.strip(),'pid':int(pid)} for u,pid in (line.split(',') for line in raw.splitlines() if line.strip())]
        cards=c.assert_peers(uuid,root_admission,rows,original.identity,os.getuid())
        return dict(idle,recovery=True,current_recovery_parent=parent,historical_parent=request['parent'],owned_cards_after_planned_decode=cards,root_admission_sha256=admission_sha)
    def already_guarded(value):
        c.require(value==parent and original.alive(parent),'recovery parent changed')
    # Per-process administrative adapter. Frozen producer files and decode functions stay unchanged.
    adapter=types.SimpleNamespace(**{name:getattr(original,name) for name in dir(original) if not name.startswith('__')})
    adapter.request=recovery_request;adapter.DECODER_UUID=uuid;adapter.co_resident_admission=recovery_admission;adapter.install_lifetime_guard=already_guarded
    live.t=adapter
    result=live.main([request['endpoint_file'],'--request',str(copied),'--parent-json',json.dumps(parent),'--core',bindings['comfy'],'--runtime-deps',bindings['runtime_deps'],'--vae',bindings['vae'],'--expected-vae-sha256',bindings['vae_sha256'],'--gpu-uuid',uuid,'--output',str(directory/'native.mp4')])
    decoded=c.read(directory/'native.json')
    c.require(decoded['status']=='complete' and decoded['decoded_shape']==[141,736,1312,3] and decoded['fallback_guard']['calls']==0 and decoded['fallback_guard']['installed'],'recovered decode incomplete')
    c.write_new(directory/'RECOVERY_DECODE.json',{'schema':'r53-last-native-observation-recovery-v1','status':'decoded_archived_Native019','original_run_status':'failed_step019_observer_admission','original_run_completed':False,'GPU_model_forward_calls':0,'original_request_sha256':c.REQUEST_SHA,'failure_inventory_sha256':c.INVENTORY_SHA,'endpoint_sha256':c.ENDPOINT_SHA,'frozen_producer_manifest_sha256':c.PRODUCER_MANIFEST_SHA,'live_decoder_source_sha256':c.sha(c.PRODUCER/'scripts/decode_live_child.py'),'decode_file':str(directory/'native.json'),'decode_sha256':c.sha(directory/'native.json'),'video_file':str(directory/'native.mp4'),'video_sha256':c.sha(directory/'native.mp4'),'gpu_uuid':uuid,'current_recovery_parent':parent,'historical_parent_retained_for_provenance':request['parent'],'scope':'Recovered final Native observation only; no final Euler update or successful original run claimed.'})
    return result
if __name__=='__main__':raise SystemExit(main())
