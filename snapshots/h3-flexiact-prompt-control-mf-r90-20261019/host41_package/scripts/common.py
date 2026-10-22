from pathlib import Path
import json,hashlib,importlib.util
ROOT=Path(__file__).resolve().parents[1];METRIC=ROOT/'runtime/official_metric';INDICES=list(range(0,147,3));CASE='human/one_leg/000'
def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(Path(p).resolve()),'sha256':sha(p)}
def save(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def verify_runtime():
 j=read(ROOT/'CONSUMER_FREEZE.json')
 for name,digest in j['files'].items():require(sha(ROOT/name)==digest,'static input/code changed: '+name)
 return j
