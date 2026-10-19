"""Run the frozen decoder and report its allocator high-water marks."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

D = Path('/data5/researcher/h3_runs/timing_native_observer_r12_20261016/scripts/decode_x0.py')
assert hashlib.sha256(D.read_bytes()).hexdigest() == '799e64e1d2e1dab3582fe4600fea810c388facbab447fd0887dc51f4a1494014'
sys.path.insert(0, str(D.parent))
spec = importlib.util.spec_from_file_location('frozen_decoder', D)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    module.main(sys.argv[1:])
finally:
    import torch
    if torch.cuda.is_initialized():
        result = {'max_allocated_bytes': torch.cuda.max_memory_allocated(),
                  'max_reserved_bytes': torch.cuda.max_memory_reserved(),
                  'allocated_after_cleanup_bytes': torch.cuda.memory_allocated(),
                  'reserved_after_cleanup_bytes': torch.cuda.memory_reserved(),
                  'visible_device_name': torch.cuda.get_device_name(0),
                  'scope': 'standalone full VAE decode resource prerequisite; no DiT or speed tuning'}
        path = Path(__file__).with_name('allocator_peak.json')
        with path.open('x') as handle:
            json.dump(result, handle, indent=2)
