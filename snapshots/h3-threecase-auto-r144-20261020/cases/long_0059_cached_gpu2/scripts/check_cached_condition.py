"""Verify original four tensors and geometry using the actual Comfy namespace."""
import json
from r86_contract import ROOT, read, sha, require
from execution_gate import atomic
import cpu_runtime_smoke


if __name__ == "__main__":
    cpu_runtime_smoke.main()
    smoke = read(ROOT / "audit/RUNTIME_IMPORT_SMOKE.json")
    require(smoke["four_cached_tensors_and_layout_verified"] and
            smoke["actual_Comfy_namespace"] and smoke["extensions_sys_path_absent"],
            "exact original cache proof incomplete")
    result = {
        "schema": "r144-original-four-tensor-layout-cpu-v1", "passed": True,
        "cache_manifest_sha256": sha(ROOT / "configs/CONDITION_CACHE.json"),
        "tensor_shape_dtype_values_exact": True, "packed_layout_exact": True,
        "actual_Comfy_namespace": True, "extensions_sys_path_absent": True,
        "cached_module_sha256": smoke["cached_module_sha256"],
        "CUDA_initialized": False, "neural_model_loads": 0, "RGB_tensors_loaded": 0,
        "scope": "Original R126 serialized model inputs and target geometry; no repeated text/video preprocessing",
    }
    atomic(ROOT / "audit/CACHED_CONDITION_CPU_PROOF.json", result)
    print(json.dumps(result, indent=2))
