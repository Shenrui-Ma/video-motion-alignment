"""Narrow compatibility interface for inherited CPU tensor verification."""
from pathlib import Path
from r86_contract import ROOT,read,sha,require,registry
PARENT_PRODUCER=Path('/data4/researcher/h3_runs/timing_oxygen_seed_replication_r113_host41_20261019')
def safe(root,relative):
 root=Path(root).resolve();p=root/relative
 require(not p.is_symlink() and p.resolve().is_relative_to(root),'path outside bound root')
 return p

def file_record(path):
 p=Path(path);return {'sha256':sha(p),'bytes':p.stat().st_size}

def verify_candidate(root=ROOT):registry(root);return read(Path(root)/'configs/protocol.json')
