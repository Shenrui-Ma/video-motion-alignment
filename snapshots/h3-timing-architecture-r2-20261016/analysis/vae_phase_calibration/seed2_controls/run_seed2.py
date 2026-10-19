"""Reuse the frozen CPU evaluator unchanged, with the new input protocol."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import hashlib,importlib.util,json
HERE=Path(__file__).resolve().parent
PIN='1d568f1c559cf4572c78e837ffd05b4b895b6167397af322cb1c2284ecbd918b'


def main():
    if hashlib.sha256((HERE/'PROTOCOL.json').read_bytes()).hexdigest()!=PIN:raise RuntimeError('Protocol changed')
    p=json.loads((HERE/'PROTOCOL.json').read_text())
    path=Path(p['loader_path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=p['loader_sha256']:raise RuntimeError('Frozen evaluator changed')
    spec=importlib.util.spec_from_file_location('frozen_evaluator',path)
    evaluator=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluator)
    # Only input/output root and its immutable manifest binding change.
    # The scoring/normalization/rejection code is reused verbatim.
    evaluator.HERE=HERE
    evaluator.PROTOCOL_SHA=PIN
    evaluator.main()


if __name__=='__main__':main()
