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
(R/'innovation_handoff/partial_remaining8_runtime_contract.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))

from H3TrustedConditionCache import H3TrustedConditionCache,sha
from H3PartialRoPE.layout import conditioning_metadata,validate_layout
from H3PartialRoPE.adapter import reference_origin_delta
rows=[]
for task in ('long_0039','long_0059','short_0085','short_0274'):
 p=R/'innovation_cache'/task/'manifest.json';m=json.loads(p.read_text());positive,target=H3TrustedConditionCache().load(str(p),sha(p));video,audio=target['samples'].unbind();refs=positive[0][1]['minimax_refs'];layout=h3.PackedLayout(positive[0][0].shape[1],*video.shape[2:],audio.shape[-1],refs=refs)
 metadata=conditioning_metadata(positive);plan=validate_layout(metadata,layout,0,m['valid_frames']-1 if 'valid_frames' in m else m['geometry']['frames']-1);delta,evidence=reference_origin_delta(metadata,layout,plan);assert delta!=0
 rows.append({'task':task,'delta_frames':delta,'derivation':evidence})
assert not torch.cuda.is_initialized()
(R/'innovation_handoff/partial_remaining8_actual_cache_delta.json').write_text(json.dumps({'status':'passed','rows':rows,'cuda_initialized':False},indent=2));print(json.dumps(rows))
