"""Extract audited native routines via AST without importing GPU dependencies.

This verifies exact native preparation/sampling code with fake encoders. It is
not a full Comfy integration test. Resize is restricted to unchanged geometry;
real resize kernels and real model loading require the production environment.
"""
import ast
import math
import sys
import types

import numpy as np
import torch


def install_native_subset(core):
    def module(name):
        result = types.ModuleType(name)
        sys.modules[name] = result
        if "." in name:
            parent, attr = name.rsplit(".", 1)
            setattr(sys.modules[parent], attr, result)
        return result

    def extract(path, names, namespace):
        tree = ast.parse(path.read_text())
        body = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
        if {node.name for node in body} != set(names):
            raise AssertionError("native definitions missing")
        exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), namespace)

    comfy = module("comfy")
    mm = module("comfy.model_management")
    mm.intermediate_device = lambda: "cpu"
    utils = module("comfy.utils")

    def unchanged_resize(samples, width, height, *args):
        if tuple(samples.shape[-2:]) != (height, width):
            raise AssertionError("AST test fixture must not resize")
        return samples

    utils.common_upscale = unchanged_resize
    nested = module("comfy.nested_tensor")
    nested.__dict__["torch"] = torch
    extract(core / "comfy/nested_tensor.py", ["NestedTensor"], nested.__dict__)
    sample = module("comfy.sample")
    sample.__dict__.update(torch=torch, np=np, comfy=comfy)
    extract(core / "comfy/sample.py", ["prepare_noise_inner", "prepare_noise"], sample.__dict__)
    module("comfy.ldm")
    module("comfy.ldm.minimax")
    model = module("comfy.ldm.minimax.model")
    model.__dict__.update(torch=torch, math=math, FRAME_PER_TOKEN=(1, 4, 4, 4, 4), FRAME_RESCALE=5 / 3)
    names = ["_axis_from_sqrt_area", "_frame_grid", "_video_t_spans", "_video_t_grid", "_ref_t_span", "_audio_grid", "_video_grid", "PackedLayout", "patchify_video"]
    extract(core / "comfy/ldm/minimax/model.py", names, model.__dict__)
    tree = ast.parse((core / "comfy/ldm/minimax/model.py").read_text())
    method = next(method for cls in tree.body if isinstance(cls, ast.ClassDef)
                  for method in cls.body if isinstance(method, ast.FunctionDef) and method.name == "_cond_video_rows")
    namespace = dict(torch=torch, patchify_video=model.patchify_video, VISUAL_COND_TIMESTEP=0.999)
    exec(compile(ast.Module(body=[method], type_ignores=[]), "native_cond_video_rows", "exec"), namespace)
    model.MiniMaxH3Model = type("MiniMaxH3Model", (), {"_cond_video_rows": namespace["_cond_video_rows"]})
    module("comfy_extras")
    nodes = module("comfy_extras.nodes_minimax_h3")

    class Output:
        def __init__(self, *args):
            self.args = args
        def __getitem__(self, index):
            return self.args[index]

    def conditioning_set_values(cond, values):
        return [[embedding, dict(meta, **values)] for embedding, meta in cond]

    nodes.__dict__.update(torch=torch, math=math, comfy=comfy,
                          CANVAS_MULTIPLE=32, BASE_SHORT_EDGE=768, MAX_PIXELS=768 * 1344,
                          REF_IMAGE_SHORT_EDGE=2048, FPS=24, AUDIO_LATENT_FPS=40,
                          io=types.SimpleNamespace(ComfyNode=object, NodeOutput=Output),
                          node_helpers=types.SimpleNamespace(conditioning_set_values=conditioning_set_values))
    extract(core / "comfy_extras/nodes_minimax_h3.py",
            ["align_frame_count", "video_latent_t", "temporal_shape", "adapt_canvas", "_resize", "_empty_av_latent", "MiniMaxH3ReferenceToVideo"], nodes.__dict__)
