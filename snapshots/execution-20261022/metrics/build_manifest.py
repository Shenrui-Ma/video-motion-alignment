import json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEV=Path('/Users/researcher/DevProjects')
REMOTE='/data/researcher/h3_metrics_20261022'

def build():
    inv=json.loads((DEV/'h3-timing-auto-motion-r26-20261017/literature/benchmark_selection_20261017/IVE_FULL_600_INVENTORY.json').read_text())
    meta={Path(x['metadata']['src_video_name']).stem:x['metadata'] for x in inv['items']}
    keep={'short_0252','short_0358','short_0085','short_0274','long_0039','long_0059'}
    jobs=[];transfers=[]
    for batch in ['r149-20261020','r150-20261021']:
        base=DEV/('h3-guidance-schedule-eval-'+batch)
        for case in json.loads((base/'EVALUATION_MANIFEST.json').read_text())['cases']:
            sid=case['source_id']
            if sid not in keep:continue
            for method in ['source','native','fixed','early','late','split','global_weak']:
                item=case['media'].get(method)
                path=Path(item['file']) if item else base/'actual'/sid/method/'video.mp4'
                if not path.exists():raise FileNotFoundError(path)
                sha=hashlib.sha256(path.read_bytes()).hexdigest()
                remote=f'{REMOTE}/videos/{sid}/{method}.mp4';transfers.append({'local':str(path),'remote':remote,'sha256':sha})
                g=case['geometry'];m=meta[sid].copy()
                jobs.append({'id':sid+'__'+method,'task_id':sid,'dataset':'IVEBench','method':method,'metadata':m,'metadata_file':f'{REMOTE}/metadata/{sid}.json','source_frames_parent':f'{REMOTE}/frames/source','target_frames_parent':f'{REMOTE}/frames/{method}','video':remote,'sha256':sha,'valid_frames':g['valid_frames'],'crop_xywh':g['crop_xywh'],'fps':g['fps'],'prompt_provenance':'historical_R149_R150_prompt_preserved','seed':case.get('seed'),'source_manifest':str(base/'EVALUATION_MANIFEST.json')})
    out={'schema':'h3-12metrics-v1','root':REMOTE,'jobs':jobs,'source_self_MF':'source method scored against the same source frames through official MF evaluator','aggregate_scopes':['IVEBench_only','all_datasets_separately_labelled'],'pending_new_tasks':['short_0114','short_0343','long_0167','crouch__movie_man_4']}
    (ROOT/'manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(ROOT/'transfers.json').write_text(json.dumps(transfers,indent=2));print('jobs',len(jobs),'bytes',sum(Path(x['local']).stat().st_size for x in transfers))
if __name__=='__main__':build()
