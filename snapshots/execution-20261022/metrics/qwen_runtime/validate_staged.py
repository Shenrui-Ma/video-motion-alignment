"""Validate staged job completeness and optionally exercise real inputs on CPU."""
import argparse
import json
import os
from pathlib import Path
import tempfile
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import batch_eval as batch


def main(args):
    manifest = json.loads((batch.ROOT / 'manifest.input.json').read_text())
    mapping = [('/data/researcher/h3_metrics_20261022', str(batch.ROOT / 'staged'))]
    jobs = [batch.remap_job(job, mapping) for job in manifest['jobs']]
    ready, pending = [], []
    for job in jobs:
        missing = []
        stem = Path(job['metadata']['src_video_name']).stem
        if not Path(job['metadata_file']).exists():missing.append('metadata')
        else:
            rows = json.loads(Path(job['metadata_file']).read_text())
            if len(rows) != 1 or rows[0]['src_video_name'] != job['metadata']['src_video_name']:
                missing.append('metadata_mismatch')
        for key in ('source_frames_parent', 'target_frames_parent'):
            folder = Path(job[key]) / stem
            receipt = folder / 'PREPARED.json'
            if not receipt.exists():missing.append(key + ':missing_receipt');continue
            prep = json.loads(receipt.read_text())
            frames = sorted(folder.glob('*.png'))
            numbers = [int(frame.stem) for frame in frames]
            if len(frames) != job['valid_frames'] or prep['frames'] != len(frames):missing.append(key + ':frame_count')
            if not numbers or numbers != list(range(numbers[0], numbers[0] + len(numbers))):missing.append(key + ':numbering')
            if key == 'target_frames_parent' and prep['sha256'] != job['sha256']:missing.append(key + ':video_hash')
        if missing:pending.append({'job_id':job['id'],'missing':missing})
        else:ready.append(job)
    result = {'status':'ready' if not pending else 'partial_snapshot','manifest_jobs':len(jobs),
              'ready_jobs':[job['id'] for job in ready],'pending_jobs':pending,'cpu_real_input_checks':[]}
    if args.exercise and ready:
        import torch
        from transformers import AutoProcessor
        torch.set_num_threads(4)
        processor = AutoProcessor.from_pretrained(str(batch.ROOT.parent / 'weights/Qwen2.5-VL-72B-Instruct-AWQ'),local_files_only=True)
        modules = batch.official_modules()
        captures=[]
        class FakeGenerator:
            device=torch.device('cpu')
            def generate(self,**kwargs):
                captures.append({'max_new_tokens':kwargs.pop('max_new_tokens'),'input_ids_shape':list(kwargs['input_ids'].shape),'video_tensor_shape':list(kwargs['pixel_values_videos'].shape)})
                answer=torch.tensor([processor.tokenizer.encode('[4] [CPU protocol validation stub]',add_special_tokens=False)])
                return torch.cat([kwargs['input_ids'],answer],dim=1)
        # Exercise a source/edit pair, preserving all staged frame bytes and numbering.
        job=next((job for job in ready if job['method']!='source'),ready[0])
        import importlib
        with tempfile.TemporaryDirectory() as temp:
            for metric,(package,class_name) in batch.METRICS.items():
                cls=getattr(modules[metric],class_name);evaluator=cls.__new__(cls)
                evaluator.model=FakeGenerator();evaluator.processor=processor
                evaluator.process_vision_info=importlib.import_module(package+'.qwen_vl_utils').process_vision_info
                output=Path(temp)/(metric+'.json')
                if not batch.evaluate_one(job,metric,modules[metric],evaluator,output,{'synthetic_output_stub':True}):
                    raise RuntimeError(output.read_text())
                result['cpu_real_input_checks'].append({'job_id':job['id'],'metric':metric,'status':'passed','generation':'fixed CPU stub; not a metric result',**captures[-1]})
        result['cuda_initialized']=torch.cuda.is_initialized()
        assert not result['cuda_initialized']
    batch.atomic(batch.ROOT / 'STAGED_VALIDATION.json', result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exercise',action='store_true');main(p.parse_args())
