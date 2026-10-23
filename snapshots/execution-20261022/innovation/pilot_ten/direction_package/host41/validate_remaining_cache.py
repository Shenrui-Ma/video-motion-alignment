import os,sys,json,hashlib,importlib.util,time,gc
from pathlib import Path
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
ROOT=Path('/data4/research-user/h3_runs/benchmark_schedule_20261022')
CORE=Path('/data3/research-user/h3_runs/silverwolf_486_ref2va4_clean/ComfyUI')
sys.path[:0]=[str(CORE),str(ROOT/'scripts')]
import compatibility_bootstrap
compatibility_bootstrap.install();compatibility_bootstrap.install_video_compat()
import comfy.cli_args
comfy.cli_args.args.cpu=True;comfy.cli_args.args.disable_xformers=True
import torch
path=ROOT/'custom_nodes/H3TrustedConditionCache/__init__.py'
spec=importlib.util.spec_from_file_location('trusted_cache',path);node=importlib.util.module_from_spec(spec);spec.loader.exec_module(node)
selected=['long_0039','long_0059','short_0085','short_0274']
rows=[]
for p in sorted((ROOT/'innovation_cache').glob('*/manifest.json')):
 if selected and p.parent.name not in selected:continue
 start=time.monotonic();manifest=json.loads(p.read_text());h=node.sha(p)
 positive,target=node.H3TrustedConditionCache().load(str(p),h)
 rows.append(dict(task_id=manifest['source_id'],manifest_sha256=h,prompt_sha256=manifest['prompt_sha256'],embedding_signature=node.signature(positive[0][0]),reference_latent_signature=node.signature(positive[0][1]['minimax_refs'][0]['latent']),target_shapes=[list(x.shape) for x in target['samples'].unbind()],cpu_reconstruction_seconds=time.monotonic()-start,packed_layout_exact=True,cuda_initialized=torch.cuda.is_initialized()))
 print(manifest['source_id'],'CPU replay exact',flush=True)
 del positive,target;gc.collect()
assert len(rows)==(len(selected) if selected else 6) and not torch.cuda.is_initialized()
out=dict(status='passed',cache_replays=rows,node_schema=node.H3TrustedConditionCache.INPUT_TYPES(),node_sha256=node.sha(path),torch=torch.__version__,cuda_initialized=torch.cuda.is_initialized())
(ROOT/('innovation_cache/CPU_REPLAY_REMAINING.json' if selected else 'innovation_cache/CPU_REPLAY_VERIFIED.json')).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(status='passed',replays=len(rows),cuda_initialized=torch.cuda.is_initialized())),flush=True)
