"""Run one official metric, retaining official formulas and detecting swallowed errors."""
import argparse, importlib, json, math, os, sys, time, traceback, types
from pathlib import Path

METRICS = dict(subject_consistency='quality', background_consistency='quality', temporal_flickering='quality', motion_smoothness='quality', vtss='quality', overall_semantic_consistency='compliance', phrase_semantic_consistency='compliance', instruction_satisfaction='compliance', quantity_accuracy='compliance', semantic_fidelity='fidelity', motion_fidelity='fidelity', content_fidelity='fidelity')

def applicability(metric, metadata):
    if metric == 'quantity_accuracy' and metadata.get('category','').strip().lower() != 'quantity_modification':
        return 'Official QA applies only to quantity_modification.'
    if metric == 'motion_fidelity' and (metadata.get('category') in ['subject_motion_editing','camera_motion_editing'] or metadata.get('subcategory') == 'event effect'):
        return 'Official MF excludes tasks requesting motion changes.'
    return None

def atomic(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False));temp.replace(path)

def run(a):
    job=json.loads(Path(a.job).read_text());meta=job['metadata'];reason=applicability(a.metric,meta)
    result={'job_id':job['id'],'task_id':job['task_id'],'dataset':job['dataset'],'cohort':job.get('cohort','main'),'method':job['method'],'metric':a.metric,'official_commit':'2dcf8900ee65197f43854c76f61c66a32bb8dbfc','status':'running','score':None,'started':time.time()}
    if reason:
        result.update(status='not_applicable',reason=reason);atomic(a.result,result);return
    try:
        official=Path(a.official).resolve();os.chdir(official/'metrics');sys.path.insert(0,str(official/'metrics'))
        # Namespace-only package avoids unrelated eager metric imports; metric files stay unchanged.
        for name in ['quality','compliance','fidelity']:
            package=types.ModuleType(name);package.__path__=[str(official/'metrics'/name)];sys.modules[name]=package
        import torch, random, numpy as np
        random.seed(0); np.random.seed(0); torch.manual_seed(0)
        result["evaluation_seed"]=0
        torch.set_num_threads(4)
        if a.metric == 'subject_consistency':
            import ivebench_utils
            def offline_dino(device):
                model=torch.hub.load(str(official.parent/'dino'),'dino_vits16',source='local',pretrained=False)
                weights=official.parent.parent/'weights/dino_deitsmall16_pretrain.pth'
                model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True),strict=True)
                return model.eval().to(device)
            ivebench_utils.load_dino_model=offline_dino
            result['loading_adapter']='official DINO architecture and original checkpoint loaded offline; scoring unchanged'
        fn=getattr(importlib.import_module(METRICS[a.metric]+'.'+a.metric),'compute_'+a.metric)
        _, details=fn(json_dir=job['metadata_file'],device=torch.device(a.device),source_videos_path=job['source_frames_parent'],target_videos_path=job['target_frames_parent'],path_yml=str(Path(a.model_paths).resolve()))
        if len(details)!=1:raise RuntimeError('Official metric returned %d rows, expected exactly one'%len(details))
        row=details[0];score=float(row['video_results'])
        if row.get('error') or score == -1 or not math.isfinite(score):raise RuntimeError('Official metric failure: '+str(row))
        result.update(status='done',score=score,detail=row,torch_version=torch.__version__)
    except Exception as exc:
        result.update(status='failed',error=str(exc),traceback=traceback.format_exc());atomic(a.result,result);raise
    finally:
        result['wall_seconds']=time.time()-result['started'];atomic(a.result,result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--metric',choices=METRICS,required=True);p.add_argument('--official',required=True);p.add_argument('--model-paths',required=True);p.add_argument('--result',required=True);p.add_argument('--device',default='cuda');run(p.parse_args())
