"""Collect the actual released pair, compact correspondence banks, and five videos."""
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from common import ROOT,ARMS,read,save,sha,bound,require,relative,verify_static,verify_gate
from common import verify_release,verify_job,verify_banks,verify_collection


def remote_path(cfg,rel):
    return Path(cfg['producer_remote'])/relative(rel)


def remote_json(cfg,rel):
    path=remote_path(cfg,rel)
    code='from pathlib import Path;p=Path('+repr(str(path))+');print(p.read_text() if p.exists() else "null")'
    r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',cfg['host'],
        shlex.join(['python3','-c',code])],capture_output=True,text=True,check=True,timeout=50)
    return json.loads(r.stdout)


def fetch(cfg,rel,output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['rsync','-az','-e','ssh -o BatchMode=yes -o ConnectTimeout=12',
        cfg['host']+':'+str(remote_path(cfg,rel)),str(output)],check=True,timeout=300)


def collect(attempt):
    cfg=verify_static();require(attempt.startswith('root_') and attempt.replace('_','').isalnum(),'invalid attempt name')
    dest=ROOT/'incoming/long_0174'
    if dest.exists():
        require(verify_collection(dest)['attempt']==attempt,'existing intake is a different attempt');return dest
    pair_rel='analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json';pair=remote_json(cfg,pair_rel)
    complete=remote_json(cfg,'audit/'+attempt+'/COMPLETE.json');release=remote_json(cfg,'audit/'+attempt+'/ROOT_EXIT_RECEIPT.json')
    if pair is None or complete is None or release is None:return None
    gates={a:remote_json(cfg,'analysis/postrun/'+cfg['runs'][a]+'/RUNTIME_GATE.json') for a in ARMS}
    require(all(gates.values()),'actual per-run gates absent');verify_gate(pair,gates,cfg)
    require(remote_json(cfg,'deploy_manifest.json')==read(ROOT/'configs/producer_deploy_manifest.json'),'deployed package differs')
    stage=ROOT/'audit'/('intake_'+str(time.time_ns()));stage.mkdir(parents=True)
    files={'PAIR_RUNTIME_GATE.json':pair_rel,'COMPLETE.json':'audit/'+attempt+'/COMPLETE.json',
        'ROOT_EXIT_RECEIPT.json':'audit/'+attempt+'/ROOT_EXIT_RECEIPT.json','STARTED.json':'audit/'+attempt+'/STARTED.json',
        'cleanup.json':'processes/cleanup.json','service.json':'processes/service.json'}
    for a in ARMS:
        run=cfg['runs'][a]
        files.update({a+'_RUNTIME_GATE.json':f'analysis/postrun/{run}/RUNTIME_GATE.json',a+'_graph.json':f'configs/graphs/{run}.json',
            a+'_job.json':f'logs/{run}_job.json',a+'_history.json':f'logs/{run}_history.json',a+'_router.json':f'audit/router/{run}.json',
            a+'.mp4':f'output/{run}_00001_.mp4'})
    for name,rel in files.items():fetch(cfg,rel,stage/name)
    require(read(stage/'PAIR_RUNTIME_GATE.json')==pair and read(stage/'COMPLETE.json')==complete
            and read(stage/'ROOT_EXIT_RECEIPT.json')==release,'producer receipts changed during transfer')
    require(read(stage/'service.json')==pair['service_owner'],'service identity changed')
    verify_release(pair,complete,release,read(stage/'STARTED.json'),read(stage/'cleanup.json'),sha(stage/'PAIR_RUNTIME_GATE.json'),cfg)
    for a in ARMS:
        require(read(stage/(a+'_RUNTIME_GATE.json'))==gates[a],'run receipt changed during transfer')
        row=next(r for r in pair['run_gate_receipts'] if r['run_id']==cfg['runs'][a])
        require(sha(stage/(a+'_RUNTIME_GATE.json'))==row['sha256'],'run gate SHA differs')
        verify_job(stage,pair,cfg,a)
        require(sha(stage/(a+'.mp4'))==pair['runs'][a]['video']['sha256'],'actual arm video bytes differ')
        # Only compact bank manifests and indices; feature tensors remain in producer storage.
        folder=stage/'banks'/a;folder.mkdir(parents=True)
        subprocess.run(['rsync','-az','--include=*/','--include=bank.json','--include=indices.npz','--exclude=*',
            '-e','ssh -o BatchMode=yes -o ConnectTimeout=12',cfg['host']+':'+str(remote_path(cfg,'audit/correspondence_banks/'+cfg['runs'][a]))+'/',
            str(folder)+'/'],check=True,timeout=300)
    verify_banks(stage,pair,cfg)
    for role,item in cfg['historical_media'].items():
        require(sha(item['file'])==item['sha256'],'historical media changed before copy');shutil.copy2(item['file'],stage/(role+'.mp4'))
    for name,item in cfg['historical_evidence'].items():shutil.copy2(item['file'],stage/(name+'.json'))
    require(remote_json(cfg,pair_rel)==pair,'paired gate changed after transfer')
    save(stage/'COLLECTION.json',{'passed':True,'attempt':attempt,'consumer_freeze_sha256':sha(ROOT/'CONSUMER_FREEZE.json'),
        'files':{str(p.relative_to(stage)):sha(p) for p in stage.rglob('*') if p.is_file()},
        'roles':['source','native','fixed',*ARMS],'valid_frames':145,'fps':24,'crop_xywh':[16,8,1280,720],
        'official_MF':'PENDING_ACTUAL_SCORING','visual_review':'PENDING_FULL145_REVIEW','created_unix':time.time()})
    dest.parent.mkdir(parents=True,exist_ok=True);stage.rename(dest);verify_collection(dest);return dest


def main():
    from media import render,prepare_mf
    from review import template
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--status',action='store_true');args=p.parse_args()
    if args.status:
        cfg=verify_static();pair=remote_json(cfg,'analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json')
        complete=remote_json(cfg,'audit/'+args.attempt+'/COMPLETE.json')
        print(json.dumps({'pair_present':pair is not None,'complete_present':complete is not None}));return
    incoming=collect(args.attempt)
    if incoming is None:print(json.dumps({'state':'PENDING_ACTUAL_COMPLETED_RELEASED_R112'}));return
    show=ROOT/'showcase/long_0174'
    if not show.exists():render(incoming,show)
    else:require(sha(show/'comparison.mp4')==read(show/'PRESENTATION.json')['video']['sha256'],'existing presentation changed')
    prepared=ROOT/'prepared/long_0174'
    if not prepared.exists():prepare_mf(incoming,prepared)
    else:
        manifest=read(prepared/'MF_INPUTS.json');require(manifest['pair_gate']['sha256']==sha(incoming/'PAIR_RUNTIME_GATE.json'),'MF input gate differs')
        for row in manifest['roles'].values():require(sha(row['score_video']['file'])==row['score_video']['sha256'],'MF pixels changed')
    review=template(incoming,show)
    print(json.dumps({'state':'ACTUAL_COMPARISON_AND_MF_INPUTS_READY','presentation':bound(show/'PRESENTATION.json'),
        'MF_inputs':bound(prepared/'MF_INPUTS.json'),'full_frame_ledger':bound(show/'FRAME_LEDGER.json'),
        'review_template':bound(review),'official_MF':'PENDING_ACTUAL_SCORING'},ensure_ascii=False))

if __name__=='__main__':main()
