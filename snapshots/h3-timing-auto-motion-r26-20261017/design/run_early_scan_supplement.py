"""Apply the frozen all-time pose scan to two already captured index005 endpoints."""
from pathlib import Path
import hashlib
import importlib.util
import json

HERE=Path(__file__).resolve().parent
BASE=HERE/'run_scan_baseline.py'
spec=importlib.util.spec_from_file_location('scan_baseline',BASE)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.OUT=module.ROOT/'analysis/windowfree_pose_early005'
module.OUT.mkdir(parents=True,exist_ok=True)
SOURCE=module.OLD/'05_real_megumi_v.pose.json'
ITEMS=[
    ('s05_seed1311_native_index005',SOURCE,module.DEV/'h3-timing-autoresearch-20261016/analysis/pose/x0/s05_full_seed1_native_x0/x0_step005.pose.json'),
    ('s05_seed1313_native_index005',SOURCE,module.DEV/'h3-timing-pose-observer-r15-20261016/analysis/pose/r14_native_step005.pose.json'),
]
module.cases=lambda:ITEMS
supplement={
    'scope':'Two existing actual native index005 endpoints, bad and normal development seeds; all physical time windows; no online decision or earliest-observable-step claim.',
    'source_binding_inventory':str(module.DEV/'h3-timing-pose-feedback-r19-20261016/design/EARLY_OBSERVABILITY_INVENTORY.txt'),
    'base_script_sha256':module.digest(BASE),
    'wrapper_sha256':module.digest(Path(__file__)),
    'base_protocol_sha256':module.digest(HERE/'SCAN_BASELINE_PROTOCOL.txt'),
    'numerical_rule':'Identical to complete-final scan; no threshold/window/classification changes.',
    'cases':[{ 'name':n,'source':str(s),'endpoint_pose':str(t),'source_sha256':module.digest(s),'target_sha256':module.digest(t)} for n,s,t in ITEMS],
}
with (module.OUT/'SUPPLEMENT_FREEZE.json').open('x') as f:json.dump(supplement,f,indent=2)
module.main()
