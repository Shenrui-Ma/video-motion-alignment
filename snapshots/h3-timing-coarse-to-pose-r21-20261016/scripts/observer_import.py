"""Load only stdlib transport, without importing the Comfy node package."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'extensions/H3CoarsePoseObserverRouter/transport.py'
s=importlib.util.spec_from_file_location('r19_transport',p)
t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
