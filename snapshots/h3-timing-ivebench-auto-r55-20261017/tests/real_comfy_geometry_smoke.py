"""Actual CPU factory/Layout/node registration; no weights, DiT, VAE, or pose."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--core', required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('CPU smoke requires CUDA hidden before importing torch')
    started = time.monotonic()
    sys.path[:0] = [str(root / 'scripts'), str(root / 'extensions'), args.core,
                   json.loads((root/'configs/runtime.json').read_text())['dependencies']]
    sys.argv = ['r55-cpu-component', '--cpu', '--disable-dynamic-vram', '--use-pytorch-cross-attention']
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    import comfy.options
    comfy.options.enable_args_parsing()
    from compatibility_bootstrap import install, install_video_compat
    install(); install_video_compat()
    import nodes
    assert asyncio.run(nodes.load_custom_node(str(root / 'extensions/H3AutomaticWindowRouter'), module_parent='custom_nodes'))
    node = nodes.NODE_CLASS_MAPPINGS['H3AutomaticWindowRouter']
    from comfy_extras.nodes_minimax_h3 import _empty_av_latent, temporal_shape
    from comfy.model_base import MiniMaxH3
    from comfy.model_patcher import ModelPatcher
    import comfy.ldm.minimax.model as h3
    from H3AutomaticWindowRouter.geometry import Geometry
    cases = json.loads((root / "configs/protocol.json").read_text())["cases"]
    geometries = [Geometry.from_case(c) for c in cases]
    from H3AutomaticWindowRouter.dependencies import layout, readout
    geometry_checks = []
    for g in geometries[:1]:
        packed, count = _empty_av_latent(g.width, g.height, g.frames)
        video, audio = packed['samples'].unbind()
        assert count == g.frames and (tuple(video.shape), tuple(audio.shape)) == g.stream_shapes
        assert temporal_shape(g.frames) == (g.frames, g.latent_bins, g.stream_shapes[1][-1])
        assert readout.CaptureConfig('smoke', '/tmp/cpu-only', g.width, g.height, g.frames).shapes == g.stream_shapes
        refs = [{'kind': 'video', 'latent': video, 'latent_t': g.latent_bins, 'latent_h': g.height//16,
                 'latent_w': g.width//16, 'ref_audio_t': 0}]
        positive = [[torch.empty((1, 100, 5120), device='meta'), {'minimax_refs': refs}]]
        actual = h3.PackedLayout(100, *video.shape[2:], audio.shape[-1], refs=refs)
        plan = layout.validate_layout(layout.conditioning_metadata(positive), actual, 0, g.frames-1)
        assert plan['frame_rows'] == g.frame_rows and plan['latent_interval_half_open'] == [0, g.latent_bins]
        geometry_checks.append({'geometry': g.video_geometry, 'shapes': [list(x.shape) for x in (video, audio)],
                                'fixture_seq_len': actual.seq_len, 'actual_case_seq_len_proved': False})
        del video, audio, packed, positive, refs, actual

    model = MiniMaxH3.__new__(MiniMaxH3)
    torch.nn.Module.__init__(model)
    with torch.device('meta'):
        model.diffusion_model = h3.MiniMaxH3Model(num_attention_heads=56, device='meta', dtype=torch.float32, operations=torch.nn)
    base = ModelPatcher(model, torch.device('cpu'), torch.device('cpu'), size=1)
    g = geometries[0]
    reference = torch.zeros(g.stream_shapes[0])
    cases = json.loads((root / 'configs/protocol.json').read_text())['cases']
    states = []
    records = []
    with tempfile.TemporaryDirectory(prefix='r55-comfy-cpu-') as tmp:
        for i, case in enumerate(cases):
            # Different fixture context/image lengths test the metadata path, not real benchmark token counts.
            side = 32 + 2*i
            g=geometries[i]
            refs = [{'kind': 'video', 'latent': reference, 'latent_t': 27, 'latent_h': 46, 'latent_w': 82, 'ref_audio_t': 0}]
            positive = [[torch.empty((1,100+i,5120), device='meta'), {'minimax_refs': refs}]]
            routed = node().apply(base, positive, case['run_id'], tmp)[0]
            patches = routed.model_options['transformer_options']['patches_replace']['dit']
            state = patches[('double_block',0)].state
            states.append(state)
            assert state.config.shapes == g.stream_shapes and state.config.geometry.valid_frames == case["valid_frame_count"]
            assert state.controller.policy.previous == [] and state.controller.policy.last_index == -1
            assert all(patches[('double_block',j)].state is state for j in range(50))
            actual = h3.PackedLayout(100+i,27,46,82,150,refs=refs)
            plan = layout.validate_layout(layout.conditioning_metadata(positive),actual,0,89)
            assert plan['frame_rows']==943 and plan['position_bin_coverage_inclusive']==[0,89] and plan['reference_image_segments']==[]
            records.append({'run_id':case['run_id'],'fresh_state':True,'fixture_seq_len':actual.seq_len,
                            'latent_bins':27,'frame_rows':943,'valid_frames':g.valid_frames,'production_parent_evidence_checked':False})
        assert len({id(s) for s in states}) == 5
        assert not base.model_options.get('transformer_options', {}).get('patches_replace', {}).get('dit')
    del routed, base, model
    import gc
    gc.collect()
    print(json.dumps({'status':'PASS','CUDA_available':torch.cuda.is_available(), 'loaded_checkpoint':False,
                      'DiT_NFE':0,'VAE_calls':0,'pose_calls':0,'official_geometry_checks':geometry_checks,
                      'cached_base_five_node_registrations':records,'wall_seconds':time.monotonic()-started,
                      'scope':'Actual Comfy CPU geometry/layout/node registration only; full wrapper/Euler integration and actual parent data pending'},allow_nan=False))


if __name__ == '__main__':
    main()
