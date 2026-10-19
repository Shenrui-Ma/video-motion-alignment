"""Explicit read-only imports; compatible with v3's private proxy imports."""
import importlib.util
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
V2_ROOT=HERE.parent/'phase_shape_profile_candidate_v2'
V3_ROOT=HERE.parent/'phase_shape_profile_candidate_v3'
for path in (V2_ROOT,V3_ROOT):
    if str(path) not in sys.path:sys.path.append(str(path))
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
V2=load(V2_ROOT/'profile_v2.py','v4_sealed_v2')
V3=load(V3_ROOT/'profile_v3.py','v4_sealed_v3')
from frozen import V1 as BASE,SYNTH
from selector import solve
import synthetic_v2 as ORIGINAL_SYNTH
import evaluation as ORIGINAL_EVAL
