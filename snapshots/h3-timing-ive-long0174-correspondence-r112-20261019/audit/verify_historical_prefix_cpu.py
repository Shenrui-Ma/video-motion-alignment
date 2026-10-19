"""Read-only CPU check against actual prior tensors; no deployment or CUDA."""
from pathlib import Path
import json
import subprocess
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'extensions/H3TemporalRouter/correspondence.py').read_text()
body="import torch,json\ntorch.set_num_threads(1)\n"+source+"\n"
body+="""
r111='/data4/researcher/h3_runs/timing_ive_long0174_spatial_marginal_r111_20261019/audit/x0/r111_long_0174_seed2026101701_forced/manifest.json'
r107='/data4/researcher/h3_runs/timing_ive_long0174_guidance_r107_20261019/audit/x0/r107_long_0174_seed2026101701_forced/manifest.json'
r96='/data4/researcher/h3_runs/timing_ive_native_screen_r96_20261018/audit/x0/r96_long_0174_seed2026101701_native/manifest.json'
assert not torch.cuda.is_initialized()
result={'r111_vs_r107':verify_common_prefix(r111,r107),'r111_vs_r96':verify_common_prefix(r111,r96),
        'noise_schema':json.loads(Path(r111).read_text())['noise'],'CUDA_initialized':torch.cuda.is_initialized(),
        'scope':'actual historical files loaded on CPU via stdin; no R112 files copied to remote'}
assert not result['CUDA_initialized']
print(json.dumps(result,indent=2))
"""
run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','H3_SERVER_B',
    'OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /data3/researcher/ComfyUI/.venv/bin/python -'],input=body,text=True,capture_output=True,timeout=90)
if run.returncode:raise RuntimeError(run.stderr)
value=json.loads(run.stdout);(ROOT/'audit/ACTUAL_HISTORICAL_PREFIX_CHECK.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
