import os,sys,json
from pathlib import Path
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
R=Path('/data4/research-user/h3_runs/benchmark_schedule_20261022')
sys.path[:0]=['/data3/research-user/h3_runs/silverwolf_486_ref2va4_clean/ComfyUI',str(R/'scripts'),str(R/'custom_nodes')]
import compatibility_bootstrap
compatibility_bootstrap.install();compatibility_bootstrap.install_video_compat()
import comfy.cli_args
comfy.cli_args.args.cpu=True;comfy.cli_args.args.disable_xformers=True
import torch
import comfy.ldm.minimax.model as h3
from H3PartialRoPE.adapter import source_hash
expected=json.loads((R/'custom_nodes/H3PartialRoPE/source_contract.json').read_text())
observed={name:source_hash(fn) for name,fn in {'_video_t_grid':h3._video_t_grid,'rope_rotation_table':h3.rope_rotation_table,'Attention.forward':h3.Attention.forward,'MiniMaxH3Model.rope_freqs':h3.MiniMaxH3Model.rope_freqs}.items()}
assert expected==observed
assert not torch.cuda.is_initialized()
out={'status':'passed','hashes':observed,'cuda_initialized':False}
(R/'innovation_handoff/partial_runtime_contract.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
