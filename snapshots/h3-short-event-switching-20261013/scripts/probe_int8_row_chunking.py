"""Bounded GPU-only operator validation; no Comfy service or model loading."""
import argparse
import gc
import json
import os
from pathlib import Path
import sys
import time
import traceback


GPU_UUID = "GPU-REDACTED"
RTOL, ATOL = 0.01, 0.001


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def identity():
    p = Path("/proc") / str(os.getpid())
    return {"pid": os.getpid(), "uid": os.getuid(),
            "start_ticks": p.joinpath("stat").read_text().split(") ", 1)[1].split()[19],
            "command": p.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode()}


def difference(torch, actual, reference):
    delta = (actual.float() - reference.float()).abs()
    scale = reference.float().abs().clamp_min(ATOL)
    result = {"max_abs_difference": delta.max().item(),
              "max_relative_difference_with_atol_floor": (delta / scale).max().item(),
              "exact_equal": torch.equal(actual, reference),
              "rtol": RTOL, "atol": ATOL,
              "allclose": torch.allclose(actual, reference, rtol=RTOL, atol=ATOL)}
    if not result["allclose"]:
        raise AssertionError("Chunked operator differs from safe original: " + json.dumps(result))
    return result


def run(report, result_path):
    if os.environ.get("CUDA_VISIBLE_DEVICES") != GPU_UUID:
        raise RuntimeError("Probe must be isolated to the specifically authorized GPU UUID")
    from compatibility_bootstrap import install as install_schema_compatibility
    install_schema_compatibility()
    import torch
    import comfy_kitchen
    import comfy_kitchen.backends.triton as triton_backend
    from comfy_kitchen.registry import registry
    import int8_row_chunking

    # Match the actual task's cu121 policy locally, without modifying sources.
    registry.disable("cuda")
    if not registry.is_available("triton"):
        raise RuntimeError("Fresh probe Triton backend was not registered/enabled")
    if torch.cuda.device_count() != 1:
        raise RuntimeError("Expected one visible, isolated CUDA device")
    device = torch.device("cuda:0")
    torch.cuda.set_device(device)
    torch.manual_seed(20261013)
    torch.cuda.reset_peak_memory_stats(device)
    original = triton_backend.int8_linear
    report.update(torch_version=torch.__version__, kitchen_path=comfy_kitchen.__file__,
                  gpu_name=torch.cuda.get_device_name(device), selected_gpu_uuid=GPU_UUID,
                  backend_policy=registry.list_backends(), small_cases=[], chunk_events=[])

    with torch.inference_mode():
        for name, convrot, input_act, scalar_scale, bias_enabled, noncontiguous in [
            ("scalar_scale_bias_3d", False, None, True, True, False),
            ("per_channel_convrot_bias_3d", True, None, False, True, False),
            ("swiglu_convrot_3d", True, "swiglu", False, False, False),
            ("noncontiguous_3d", False, None, False, True, True),
        ]:
            t0 = time.monotonic()
            k, n, m = 256, 384, 130
            raw_k = k * 2 if input_act == "swiglu" else k
            x = torch.randn((2, raw_k, 65) if noncontiguous else (2, 65, raw_k),
                            dtype=torch.bfloat16, device=device) * 0.25
            if noncontiguous:
                x = x.transpose(1, 2)
            weight = torch.randint(-8, 9, (n, k), dtype=torch.int8, device=device)
            scales = torch.rand((1,) if scalar_scale else (n, 1), dtype=torch.float32, device=device) * 0.02 + 0.001
            bias = torch.randn(n, dtype=torch.bfloat16, device=device) * 0.05 if bias_enabled else None
            kwargs = dict(x=x, weight=weight, weight_scale=scales, bias=bias,
                          out_dtype=torch.bfloat16, convrot=convrot,
                          convrot_groupsize=256, input_act=input_act)
            reference = original(**kwargs)
            torch.cuda.synchronize()
            events = []
            wrapped = int8_row_chunking.wrap_int8_linear(original,
                index_limit=64 * max(raw_k, n) - 1, event_callback=events.append)
            actual = wrapped(**kwargs)
            torch.cuda.synchronize()
            comparison = difference(torch, actual, reference)
            boundary_rows = [0, 63, 64, 127, 128, 129]
            boundary = difference(torch, actual.reshape(m, n)[boundary_rows], reference.reshape(m, n)[boundary_rows])
            report["small_cases"].append({"name": name, "input_shape": list(x.shape),
                "input_contiguous": x.is_contiguous(), "weight_shape": [n, k],
                "scale_shape": list(scales.shape), "bias": bias_enabled,
                "convrot": convrot, "input_act": input_act, "chunk_events": events,
                "comparison": comparison, "boundary_rows": boundary_rows,
                "boundary_comparison": boundary, "wall_seconds": time.monotonic() - t0})
            print("SMALL", name, json.dumps(comparison), flush=True)
            save(result_path, report)
            del x, weight, scales, bias, kwargs, reference, actual, wrapped

        # Exercise the real registry export hook and verify selection remains Triton.
        install_record = int8_row_chunking.install()
        production = registry.get_implementation("int8_linear", backend="triton")
        if production is original or production._h3_row_chunk_original is not original:
            raise AssertionError("Actual registry hook did not preserve original callable")
        report["install_record"] = install_record
        if registry.get_implementation("int8_linear", kwargs={
            "x": torch.empty(1, 256, device=device, dtype=torch.bfloat16),
            "weight": torch.empty(384, 256, device=device, dtype=torch.int8),
            "weight_scale": torch.ones(384, 1, device=device), "bias": None,
            "out_dtype": torch.bfloat16, "convrot": True, "convrot_groupsize": 256,
            "input_act": None}) is not production:
            raise AssertionError("Automatic registry dispatch did not select patched Triton export")

        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
        t0 = time.monotonic()
        m, n, k = 87583, 28672, 5376
        x = torch.ones((m, k), dtype=torch.bfloat16, device=device)
        weight = torch.ones((n, k), dtype=torch.int8, device=device)
        scales = torch.ones((n, 1), dtype=torch.float32, device=device)
        kwargs = dict(x=x, weight=weight, weight_scale=scales, bias=None,
                      out_dtype=torch.bfloat16, convrot=True, convrot_groupsize=256, input_act=None)
        # Never invoke original on this full shape; only the installed wrapper.
        actual = comfy_kitchen.int8_linear(**kwargs)
        torch.cuda.synchronize()
        operator_seconds = time.monotonic() - t0
        if actual.shape != (m, n) or actual.dtype != torch.bfloat16 or actual.device != device:
            raise AssertionError("Large output shape/dtype/device changed")
        rows = sorted({0, 1, m-1, *(i for boundary in range(16384, m, 16384)
                                     for i in (boundary-1, boundary))})
        reference = original(**dict(kwargs, x=x[rows].contiguous()))
        torch.cuda.synchronize()
        comparison = difference(torch, actual[rows], reference)
        all_finite, all_rows_equal_safe_reference = True, True
        for start in range(0, m, 4096):
            block = actual[start:start+4096]
            all_finite = all_finite and torch.isfinite(block).all().item()
            all_rows_equal_safe_reference = all_rows_equal_safe_reference and torch.eq(block, reference[0]).all().item()
        if not all_finite or not all_rows_equal_safe_reference:
            raise AssertionError("Large output contains nonfinite or inconsistent equal-input rows")
        report["large_case"] = {"input_shape": [m, k], "weight_shape": [n, k],
            "output_shape": list(actual.shape), "dtype": str(actual.dtype),
            "convrot": True, "convrot_groupsize": 256, "scale_shape": [n, 1], "bias": None,
            "whole_shape_original_called": False, "reference_kind": "Safe original sub-batch with selected boundary rows; no Hadamard-value assumption",
            "reference_rows": rows, "comparison": comparison, "all_output_finite": all_finite,
            "all_identical_input_rows_equal_safe_reference": all_rows_equal_safe_reference,
            "safe_reference_first_value": reference[0, 0].item(),
            "production_chunk_rows": 16384, "production_chunks": (m+16383)//16384,
            "operator_seconds_including_autotuning": operator_seconds,
            "wall_seconds_with_checks": time.monotonic() - t0,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(device)}
        print("LARGE", json.dumps(report["large_case"]), flush=True)
        del x, weight, scales, kwargs, actual, reference, block
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        report["allocator_after_release"] = {"allocated_bytes": torch.cuda.memory_allocated(device),
                                             "reserved_bytes": torch.cuda.memory_reserved(device)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--result", type=Path, required=True)
    args = ap.parse_args()
    started = time.monotonic()
    report = {"status": "running", "identity": identity(),
              "scope": "One isolated operator probe; no model weights, Comfy service, or other GPU",
              "whole_large_original_forbidden": True}
    save(args.result, report)
    try:
        run(report, args.result)
        report["status"] = "passed"
        code = 0
    except BaseException as exc:
        report.update(status="failed", error=repr(exc), traceback=traceback.format_exc())
        traceback.print_exc()
        code = 1
    report["total_wall_seconds"] = time.monotonic() - started
    save(args.result, report)
    return code


if __name__ == "__main__":
    sys.exit(main())
