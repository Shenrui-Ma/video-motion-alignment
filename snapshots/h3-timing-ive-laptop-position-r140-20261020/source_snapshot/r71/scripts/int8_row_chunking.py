"""Task-local, inference-only protection for Triton's signed-32 row offsets.

No checkpoint, attention, sampler, or shared dependency files are changed.
Install once in the isolated Comfy process after comfy_kitchen is importable.
"""
from __future__ import annotations

from functools import wraps
import importlib
import inspect
import json
from pathlib import Path

import torch


PARAMETERS = ("x", "weight", "weight_scale", "bias", "out_dtype", "convrot",
              "convrot_groupsize", "input_act")
INDEX_LIMIT = (1 << 31) - 1
MAX_CHUNK_ROWS = 16384


def wrap_int8_linear(original, *, index_limit=INDEX_LIMIT, max_chunk_rows=MAX_CHUNK_ROWS,
                     event_callback=None):
    """Keep safe calls intact; partition only independent activation rows.

    ``index_limit`` can be lowered for CPU regression tests. Production should
    use its signed-int32 default. No scales in this API depend on other rows:
    activations are quantized per row inside ``original``; weight scales are
    scalar or per output channel. SwiGLU/ConvRot also act within each row.
    """
    signature = inspect.signature(original)
    if tuple(signature.parameters) != PARAMETERS:
        raise RuntimeError("Triton int8_linear API changed; re-audit before installing")
    if type(index_limit) is not int or index_limit < 0 or index_limit > INDEX_LIMIT:
        raise ValueError("index_limit must be a nonnegative signed-int32 bound")
    if type(max_chunk_rows) is not int or not 1 <= max_chunk_rows <= MAX_CHUNK_ROWS:
        raise ValueError("max_chunk_rows must be between 1 and 16384")
    policy = {"index_limit": index_limit, "max_chunk_rows": max_chunk_rows,
              "trigger": "max(flattened input elements, flattened output elements) - 1 > index_limit",
              "partition": "leading dimensions flattened into independent rows; no column splitting",
              "original_signature": str(signature)}

    @wraps(original)
    def chunked(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        values = bound.arguments
        x, weight = values["x"], values["weight"]
        # Leave malformed/empty inputs and normal calls to the original API.
        if x.ndim < 1 or weight.ndim != 2 or x.shape[-1] == 0 or x.numel() == 0:
            return original(*args, **kwargs)
        raw_width = x.shape[-1]
        rows = x.numel() // raw_width
        output_width = weight.shape[0]
        widest_row = max(raw_width, output_width)
        max_offset = rows * widest_row - 1
        if max_offset <= index_limit:
            return original(*args, **kwargs)
        chunk_rows = min(max_chunk_rows, (index_limit + 1) // widest_row)
        if chunk_rows < 1:
            raise RuntimeError("A single INT8 linear row exceeds the safe offset bound")
        if event_callback is not None:
            event_callback({"event": "int8_row_chunk", "input_shape": list(x.shape),
                            "weight_shape": list(weight.shape), "input_dtype": str(x.dtype),
                            "out_dtype": str(values["out_dtype"]), "device": str(x.device),
                            "max_flat_offset": max_offset, "chunk_rows": chunk_rows,
                            "chunks": (rows + chunk_rows - 1) // chunk_rows,
                            "input_act": values["input_act"], "convrot": values["convrot"],
                            "convrot_groupsize": values["convrot_groupsize"]})
        flat = x.reshape(rows, raw_width).contiguous()
        output = None
        for start in range(0, rows, chunk_rows):
            end = min(start + chunk_rows, rows)
            call = dict(values, x=flat[start:end])
            part = original(**call)
            if part.shape != (end - start, output_width):
                raise RuntimeError("Original INT8 linear returned an unexpected chunk shape")
            if output is None:
                output = part.new_empty((rows, output_width))
            if part.dtype != output.dtype or part.device != output.device:
                raise RuntimeError("Original INT8 linear changed dtype/device between chunks")
            output[start:end].copy_(part)
            del part
        return output.reshape(*x.shape[:-1], output_width)

    chunked._h3_row_chunk_policy = policy
    chunked._h3_row_chunk_original = original
    return chunked


def install(*, log_path=None, index_limit=INDEX_LIMIT, max_chunk_rows=MAX_CHUNK_ROWS):
    """Replace only the task process's registered Triton INT8 linear export.

    registry.get_implementation resolves attributes on the registered backend
    module on every dispatch. Patching only quantization.int8_linear would miss
    that module's already-imported alias. Shared source files stay unchanged.
    """
    backend = importlib.import_module("comfy_kitchen.backends.triton")
    registry = importlib.import_module("comfy_kitchen.registry").registry
    original = backend.int8_linear
    if registry.get_implementation("int8_linear", backend="triton") is not original:
        raise RuntimeError("Registered Triton backend differs from imported export; refusing patch")
    previous = getattr(original, "_h3_row_chunk_policy", None)
    if previous is not None:
        if (previous["index_limit"], previous["max_chunk_rows"]) != (index_limit, max_chunk_rows):
            raise RuntimeError("INT8 row chunking already installed with a different policy")
        return {"status": "already_installed", **previous}

    def record(event):
        if log_path is not None:
            path = Path(log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as stream:
                stream.write(json.dumps(event, sort_keys=True) + "\n")

    replacement = wrap_int8_linear(original, index_limit=index_limit,
                                   max_chunk_rows=max_chunk_rows, event_callback=record)
    backend.int8_linear = replacement
    if registry.get_implementation("int8_linear", backend="triton") is not replacement:
        backend.int8_linear = original
        raise RuntimeError("Registry did not resolve replacement; original export restored")
    result = {"status": "installed", "hook": "comfy_kitchen.backends.triton.int8_linear",
              **replacement._h3_row_chunk_policy}
    record(result)
    return result
