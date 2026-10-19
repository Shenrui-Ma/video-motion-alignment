"""Profile default SDPA vs explicit Flash on H3-shaped random tensors only.

No model imports, service control, or package changes. GPU execution is refused
unless physical GPU 3 matches the supplied UUID and is idle at two admissions.
The input audit supplies real layout lengths; values are synthetic, not an
assertion about model quality or every possible runtime configuration.
"""

import argparse
import gc
import hashlib
import inspect
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def snapshot(uuid):
    rows = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu",
         "--format=csv,noheader,nounits"], text=True, timeout=10).splitlines()
    gpu = None
    for row in rows:
        fields = [field.strip() for field in row.split(",")]
        if fields[1] == uuid:
            gpu = dict(index=int(fields[0]), uuid=fields[1], name=fields[2],
                       used_mib=int(fields[3]), total_mib=int(fields[4]), utilization=int(fields[5]))
    if gpu is None or gpu["index"] != 3:
        raise RuntimeError("This bounded audit is authorized only on physical GPU 3")
    rows = subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_gpu_memory",
         "--format=csv,noheader,nounits"], text=True, timeout=10).splitlines()
    gpu["compute_processes"] = [row for row in rows if row.split(",")[0].strip() == uuid]
    gpu["unix_time"] = time.time()
    return gpu


def admit(uuid):
    result = snapshot(uuid)
    if result["compute_processes"] or result["used_mib"] > 16 or result["utilization"] != 0:
        raise RuntimeError("GPU 3 is occupied; refusing allocation: " + json.dumps(result))
    return result


def layout_from(audit):
    layout = audit["validated_layout"]
    shape = audit["first_attention"]["qkv_shape"]
    if shape != [1, 56, layout["seq_len"], 128]:
        raise ValueError("Expected real H3 batch1,56heads,128dim layout")
    if audit["first_attention"]["dtype"] != "torch.bfloat16":
        raise ValueError("Expected real H3 bf16 audit")
    ka, kb = layout["key_interval_half_open"]
    qa, qb = layout["query_interval_half_open"]
    if not (0 <= ka < kb <= shape[2] and 0 <= qa < qb <= shape[2]):
        raise ValueError("Invalid event intervals")
    return dict(shape=shape, key_interval=[ka, kb], query_interval=[qa, qb],
                x3_q_length=qb - qa, x3_k_length=shape[2] + 2 * (kb - ka))


def qkv_views(packed, heads, dim):
    # Matches minimax/model.py: split [S,3*H*D], view, transpose, unsqueeze.
    seq = packed.shape[0]
    return tuple(x.view(seq, heads, dim).transpose(0, 1).unsqueeze(0)
                 for x in packed.split(heads * dim, dim=-1))


def metadata(tensor):
    return {"shape": list(tensor.shape), "stride": list(tensor.stride()),
            "storage_offset": tensor.storage_offset(), "contiguous": tensor.is_contiguous()}


def compare_outputs(torch, first, second):
    exact = torch.equal(first, second)
    maxdiff, finite = 0.0, True
    # Bounded float32 comparison; never materialize another full float32 tensor.
    for start in range(0, first.shape[2], 1024):
        a = first[:, :, start:start + 1024].float()
        b = second[:, :, start:start + 1024].float()
        finite = finite and bool((torch.isfinite(a).all() & torch.isfinite(b).all()).item())
        if not exact:
            maxdiff = max(maxdiff, float((a - b).abs().max().item()))
    return {"bitwise_equal": exact, "max_abs_difference": maxdiff, "all_finite": finite}


def profile_case(torch, name, q, k, v):
    activities = [torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA]
    start = time.monotonic()
    with torch.profiler.profile(activities=activities, record_shapes=False) as prof:
        default = torch.nn.functional.scaled_dot_product_attention(
            q, k, v, attn_mask=None, dropout_p=0.0, is_causal=False)
        torch.cuda.synchronize()
    default_seconds = time.monotonic() - start
    events = prof.key_averages()
    names = [entry.key for entry in events]
    cuda_names = sorted({entry.name for entry in prof.events()
                         if str(entry.device_type).endswith("CUDA")})
    start = time.monotonic()
    explicit = torch.ops.aten._scaled_dot_product_flash_attention.default(
        q, k, v, 0.0, False, False)[0]
    torch.cuda.synchronize()
    explicit_seconds = time.monotonic() - start
    result = dict(name=name, q=metadata(q), k=metadata(k), v=metadata(v),
                  default_aten_operators=[key for key in names if "attention" in key.lower()],
                  default_cuda_kernels=cuda_names, default_profiled_wall_seconds=default_seconds,
                  explicit_unprofiled_wall_seconds=explicit_seconds,
                  time_note="One call; profiler overhead differs; not a speed benchmark",
                  **compare_outputs(torch, default, explicit))
    result["default_dispatched_flash"] = "aten::_scaled_dot_product_flash_attention" in names
    del prof, events, default, explicit
    return result


def self_test():
    import torch
    example = {"validated_layout": {"seq_len": 100, "key_interval_half_open": [10, 20],
                                    "query_interval_half_open": [80, 90]},
               "first_attention": {"qkv_shape": [1, 56, 100, 128], "dtype": "torch.bfloat16"}}
    plan = layout_from(example)
    assert plan["x3_q_length"] == 10 and plan["x3_k_length"] == 120
    packed = torch.arange(20 * 3 * 4 * 8).reshape(20, 3 * 4 * 8)
    q, k, v = qkv_views(packed, 4, 8)
    assert q.shape == (1, 4, 20, 8) and q.stride() == (32, 8, 96, 1)
    assert q.storage_offset() == 0 and k.storage_offset() == 32 and v.storage_offset() == 64
    assert q[0, 2, 7, 3] == packed[7, 2 * 8 + 3]
    assert torch.cat((k, k[:, :, 3:6], k[:, :, 3:6]), dim=-2).shape[2] == 26
    assert compare_outputs(torch, q, q.clone())["bitwise_equal"]
    different = q.clone()
    different[0, 0, 0, 0] += 1
    assert compare_outputs(torch, q, different)["max_abs_difference"] == 1.0
    example["first_attention"]["qkv_shape"][1] = 8
    try:
        layout_from(example)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid shape was accepted")
    print(json.dumps({"status": "cpu_self_test_passed", "checks": 9}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--gpu-uuid")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.audit_json or not args.output or not args.gpu_uuid:
        parser.error("GPU run requires --audit-json, --output and --gpu-uuid")
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite an earlier dispatch audit")
    raw = args.audit_json.read_bytes()
    plan = layout_from(json.loads(raw))
    data = {"schema": "h3-sdpa-shape-dispatch-v1", "status": "preflight", "pid": os.getpid(),
            "audit_path": str(args.audit_json), "audit_sha256": hashlib.sha256(raw).hexdigest(),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "layout": plan, "started_unix": time.time(), "admissions": [], "cases": [],
            "scope": "Random tensor backend/precision control, not model inference or quality validation",
            "stride_source": "comfy/ldm/minimax/model.py:175-198; fused QKnorm/RoPE is in-place"}

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_suffix(".json.tmp")
        temp.write_text(json.dumps(data, indent=2) + "\n")
        os.replace(temp, args.output)

    def timed_out(signum, frame):
        data["status"] = "timeout"
        save()
        os._exit(124)  # Own process only; CUDA context is released by process exit.

    signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(110)
    try:
        data["admissions"].append(admit(args.gpu_uuid))
        # Set visibility before importing torch or querying CUDA in any way.
        os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu_uuid
        import torch
        data["admissions"].append(admit(args.gpu_uuid))
        if torch.cuda.device_count() != 1:
            raise RuntimeError("UUID isolation failed")
        torch.set_num_threads(2)
        data["torch"] = torch.__version__
        data["cuda"] = torch.version.cuda
        data["device_name"] = torch.cuda.get_device_name(0)
        data["sdpa_flags"] = {"flash": torch.backends.cuda.flash_sdp_enabled(),
                              "memory_efficient": torch.backends.cuda.mem_efficient_sdp_enabled(),
                              "math": torch.backends.cuda.math_sdp_enabled()}
        from torch.nn.attention import sdpa_kernel
        data["sdpa_kernel_supports_set_priority"] = "set_priority" in inspect.signature(sdpa_kernel).parameters
        data["status"] = "running"
        save()
        torch.cuda.reset_peak_memory_stats()
        torch.manual_seed(20261016)
        with torch.inference_mode():
            _, heads, seq, dim = plan["shape"]
            packed = torch.empty((seq, 3 * heads * dim), device="cuda", dtype=torch.bfloat16).normal_()
            q, k, v = qkv_views(packed, heads, dim)
            data["cases"].append(profile_case(torch, "native_full", q, k, v))
            save()
            ka, kb = plan["key_interval"]
            qa, qb = plan["query_interval"]
            event_q = q[:, :, qa:qb]
            event_k = torch.cat((k, k[:, :, ka:kb], k[:, :, ka:kb]), dim=-2)
            event_v = torch.cat((v, v[:, :, ka:kb], v[:, :, ka:kb]), dim=-2)
            data["cases"].append(profile_case(torch, "x3_local_queries_duplicated_kv", event_q, event_k, event_v))
            data["peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
            data["peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
            del event_q, event_k, event_v, q, k, v, packed
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        data["allocated_bytes_after_cleanup"] = torch.cuda.memory_allocated()
        data["reserved_bytes_after_cleanup"] = torch.cuda.memory_reserved()
        data["status"] = "passed" if all(
            case["default_dispatched_flash"] and case["bitwise_equal"] and case["all_finite"]
            for case in data["cases"]) else "backend_or_numeric_difference"
    except Exception as error:
        data["status"] = "failed_or_busy"
        data["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        data["finished_unix"] = time.time()
        save()
        signal.alarm(0)
    print(json.dumps({"status": data["status"], "output": str(args.output),
                      "cases": [{k: case[k] for k in ("name", "default_aten_operators", "bitwise_equal",
                                "max_abs_difference")} for case in data["cases"]]}))


if __name__ == "__main__":
    main()
