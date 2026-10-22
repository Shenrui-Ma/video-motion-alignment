"""Apply this batch's attempt prefix to the unchanged final release audit."""
from pathlib import Path
import hashlib, json

_root = Path(__file__).resolve().parents[1]
_path = _root / 'audit/final_release.py'
_raw = _path.read_bytes()
assert hashlib.sha256(_raw).hexdigest() == json.loads((_root / 'SEAL.json').read_text())['files']['audit/final_release.py']
_code = _raw.decode()
_old = "glob('actual_context_mf_attempt*')"
assert _code.count(_old) == 1
_code = _code.replace(_old, "glob('actual_new_sources_attempt*')")
_old = ' rows=cuda_process_rows();trackers=[read(x[\'file\'])[\'identity\'] for x in all_releases]'
assert _code.count(_old) == 1
_code = _code.replace(_old, " assert wrappers and len(all_releases) == len(states), 'wrapper or tracker release coverage incomplete'\n" + _old)
exec(compile(_code, str(_path), 'exec'), globals())
