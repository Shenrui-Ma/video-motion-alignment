"""Future, explicit GPU-only comparison. Import/--help does not initialize CUDA."""

import argparse
import hashlib
import inspect
import json
import math
import sys
import traceback
from pathlib import Path

from adapter import SageAttentionLSE
from diagnostics import (
    error_metrics,
    flash_attention_lse,
    fp32_attention,
    make_case,
    mass_preserve,
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-gpu", action="store_true", help="explicitly execute CUDA kernels")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", choices=("float16", "bfloat16", "both"), default="both")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-core-sha256", help="explicit audited source override")
    parser.add_argument("--output-max-abs", type=float, default=0.05)
    parser.add_argument("--lse-max-abs", type=float, default=0.10)
    parser.add_argument("--mass-max-abs", type=float, default=0.02)
    parser.add_argument("--positive-delta-tolerance", type=float, default=0.001)
    args = parser.parse_args()
    if not args.run_gpu:
        parser.error("--run-gpu is required; this script never silently substitutes a CPU run")
    if args.output.exists():
        parser.error("output already exists; choose a new result path")
    if any(not math.isfinite(x) or x < 0 for x in (
        args.output_max_abs, args.lse_max_abs, args.mass_max_abs, args.positive_delta_tolerance
    )):
        parser.error("error thresholds must be finite and nonnegative")
    return args


def tensor_stats(torch, value):
    return {
        "finite": bool(torch.isfinite(value).all()),
        "min": value.min().item(),
        "max": value.max().item(),
        "mean": value.mean().item(),
        "values": value.detach().cpu().tolist(),
    }


def call_preserving_qkv(torch, attention, inputs, originals, evidence, stage):
    """Check the complete original QKV, including parent tensors of subset views."""
    before = tuple(x.clone() for x in originals)
    try:
        return attention(*inputs)
    finally:
        unchanged = {name: torch.equal(actual, saved) for name, actual, saved in
                     zip(("q", "k", "v"), originals, before)}
        evidence[stage] = unchanged
        if not all(unchanged.values()):
            raise RuntimeError(f"{stage} attention mutated original Q/K/V: {unchanged}")


def run(args, report):
    import sageattention.core as sage_core
    import torch

    if not args.device.startswith("cuda") or not torch.cuda.is_available():
        raise RuntimeError("a compatible CUDA device and existing Sage runtime are required")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")
    provenance = json.loads((Path(__file__).parent / "provenance.json").read_text())
    source = Path(inspect.getsourcefile(sage_core)).resolve()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    expected = args.expected_core_sha256 or provenance["sage_core_content_sha256"]
    report["runtime"] = {
        "python": sys.version, "torch": torch.__version__, "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(args.device),
        "capability": torch.cuda.get_device_capability(args.device),
        "sage_core": str(source), "sage_core_sha256": digest,
        "expected_sage_core_sha256": expected, "tf32": False,
        "backend": "sageattn_qk_int8_pv_fp16_cuda",
        "layout": "NHD", "pv_accum_dtype": "fp32", "qk_quant_gran": "per_warp",
    }
    if digest != expected:
        raise RuntimeError("Sage source hash differs from the audited API; audit before overriding")
    dtypes = ("float16", "bfloat16") if args.dtype == "both" else (args.dtype,)
    for dtype_name in dtypes:
        for dim in (64, 128):
            for case in ("random", "different_k_means", "mass_near_zero", "mass_near_one"):
                (q, k, v), ref, aligned = make_case(
                    torch, case, device=args.device, dtype=getattr(torch, dtype_name), dim=dim
                )
                outputs = {}
                record = {"case": case, "dtype": dtype_name, "head_dim": dim, "backends": {}}
                report["cases"].append(record)
                for label, attention in (
                    ("fp32_oracle", fp32_attention),
                    ("flash", flash_attention_lse),
                    ("sage_smooth_k", SageAttentionLSE()),
                    ("sage_no_smooth_k", SageAttentionLSE(smooth_k=False)),
                ):
                    evidence = {"input_qkv_unchanged": {}}
                    record["backends"][label] = evidence
                    original_qkv = (q, k, v)
                    full, full_lse = call_preserving_qkv(
                        torch, attention, original_qkv, original_qkv,
                        evidence["input_qkv_unchanged"], "full",
                    )
                    ref_out, ref_lse = call_preserving_qkv(
                        torch, attention, (q, k[:, :, ref], v[:, :, ref]), original_qkv,
                        evidence["input_qkv_unchanged"], "reference",
                    )
                    aligned_out, aligned_lse = call_preserving_qkv(
                        torch, attention, (q, k[:, :, aligned], v[:, :, aligned]), original_qkv,
                        evidence["input_qkv_unchanged"], "aligned",
                    )
                    delta = ref_lse.float() - full_lse.float()
                    mass = delta.exp()
                    corrected = mass_preserve(
                        full, ref_out, aligned_out, full_lse, ref_lse, alpha=1.0
                    )
                    zero = mass_preserve(full, None, None, None, None, alpha=0.0)
                    outputs[label] = (full, full_lse, ref_out, ref_lse, aligned_out,
                                      aligned_lse, mass, corrected)
                    evidence.update({
                        "raw_l_ref_minus_l_full": tensor_stats(torch, delta),
                        "unclamped_reference_mass": tensor_stats(torch, mass),
                        "alpha_zero_bitwise_native": torch.equal(zero, full),
                        "all_outputs_finite": all(bool(torch.isfinite(x).all()) for x in outputs[label]),
                        "all_input_qkv_unchanged": all(
                            all(flags.values()) for flags in evidence["input_qkv_unchanged"].values()
                        ),
                    })
                    if label == "fp32_oracle":
                        evidence["mass_extreme_reached"] = (
                            mass.max().item() < 0.0001 if case == "mass_near_zero" else
                            mass.min().item() > 0.9999 if case == "mass_near_one" else True
                        )
                        continue
                    names = ("full_output", "full_lse", "reference_output", "reference_lse",
                             "aligned_output", "aligned_lse", "reference_mass", "routed_output_fp32")
                    errors = {name: error_metrics(a, b) for name, a, b in
                              zip(names, outputs[label], outputs["fp32_oracle"])}
                    evidence["error_vs_fp32_oracle"] = errors
                    limits = [args.lse_max_abs if "lse" in name else
                              args.mass_max_abs if name == "reference_mass" else
                              args.output_max_abs for name in names]
                    evidence["passes_provisional_thresholds"] = (
                        evidence["all_outputs_finite"] and evidence["alpha_zero_bitwise_native"]
                        and evidence["all_input_qkv_unchanged"]
                        and delta.max().item() <= args.positive_delta_tolerance
                        and all(errors[name]["max_abs"] <= limit for name, limit in zip(names, limits))
                    )
                record["sage_vs_flash"] = {
                    label: {
                        "full_output": error_metrics(outputs[label][0], outputs["flash"][0]),
                        "routed_output_fp32": error_metrics(outputs[label][-1], outputs["flash"][-1]),
                        "reference_mass": error_metrics(outputs[label][-2], outputs["flash"][-2]),
                    } for label in ("sage_smooth_k", "sage_no_smooth_k")
                }
    torch.cuda.synchronize(args.device)
    report["passed"] = all(
        entry.get("passes_provisional_thresholds", entry.get("mass_extreme_reached", True))
        and entry["all_outputs_finite"] and entry["alpha_zero_bitwise_native"]
        and entry["all_input_qkv_unchanged"]
        for case in report["cases"] for entry in case["backends"].values()
    )


def json_safe(value):
    """Represent nonfinite measurements explicitly while preserving valid JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def main():
    args = parse_args()
    report = {
        "purpose": "engineering compatibility only; no novelty, speed or video-quality claim",
        "thresholds_status": "provisional micro-test limits, not a production acceptance decision",
        "no_clamp": True, "passed": False, "cases": [],
        "thresholds": {name: getattr(args, name) for name in
                       ("output_max_abs", "lse_max_abs", "mass_max_abs", "positive_delta_tolerance")},
    }
    try:
        run(args, report)
    except Exception:  # noqa: BLE001 -- save kernel/import failure, then exit nonzero.
        report["error"] = traceback.format_exc()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Invalid numerics remain explicit in the saved evidence, never clamped.
    with args.output.open("x") as handle:
        json.dump(json_safe(report), handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"passed": report["passed"], "output": str(args.output),
                      "error": report.get("error")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
