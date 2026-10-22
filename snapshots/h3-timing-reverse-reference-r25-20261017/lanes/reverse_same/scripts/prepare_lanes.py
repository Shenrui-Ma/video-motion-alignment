"""Offline independent arms; never overwrite, admit, or start a service."""
import json
from pathlib import Path
import shutil
from r25_contract import ROOT, REMOTE_BASE, ARMS, SEED, read, sha, run_name, expected_graph

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def configure(root,arm):
    root=Path(root);index=ARMS.index(arm)
    write(root/'configs/runtime.json',{'arm':arm,'remote_root':str(REMOTE_BASE/arm),
        'gpu_uuid':('GPU-REDACTED','GPU-REDACTED')[index],
        'port':(8486,8487)[index],'resource_assignment':'candidate only; root exact live R24 handoff required'})
    run=run_name(arm);graph=root/'configs/graphs'/f'{run}.json';write(graph,expected_graph(root,arm))
    write(root/'configs/job_registry.json',{'root_preparation_only':True,'jobs':{run:{'seed':SEED,'arm':arm,'graph_sha256':sha(graph)}}})
    write(root/'configs/queue.json',{'jobs':[run],'finalize':False})
    write(root/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs',
        'existing_comfy_port':None,'permitted_compute_processes':[]})
    return run

def prepare(scaffold=ROOT):
    scaffold=Path(scaffold);outputs=[]
    if any((scaffold/'lanes'/arm).exists() for arm in ARMS):raise FileExistsError('preserve existing lanes/evidence')
    for arm in ARMS:
        target=scaffold/'lanes'/arm;target.mkdir(parents=True)
        for folder in ('scripts','extensions','tests','configs','inputs','parent_evidence'):
            shutil.copytree(scaffold/folder,target/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc','graphs','runtime.json','job_registry.json','queue.json','admission.json'))
        shutil.copy2(scaffold/'IMPLEMENTATION.txt',target/'IMPLEMENTATION.txt')
        for folder in ('audit','analysis'):(target/folder).mkdir()
        run=configure(target,arm)
        outputs.append({'arm':arm,'root':str(target),'run':run,'runtime':read(target/'configs/runtime.json')})
    return outputs

if __name__=='__main__':print(json.dumps(prepare(),indent=2))
