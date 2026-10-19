"""Administrative SSH route wrapper; frozen consumer remains byte-identical."""
import hashlib, json, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import consume, one_phase
consume.SSH[1:1] = ['-J', 'H3_SERVER_B']
(HERE / 'audit').mkdir(exist_ok=True)
record = {'route': 'Mac -> authorized .41 -> same .9 SSH account', 'SSH': consume.SSH,
          'root_authorized': True, 'scientific_files_changed': False,
          'consumer_freeze_sha256': hashlib.sha256((HERE / 'FREEZE.json').read_bytes()).hexdigest(),
          'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'time': time.time()}
(HERE / 'audit' / ('jump_route_' + str(time.time_ns()) + '.json')).write_text(json.dumps(record, indent=2) + '\n')
try:
    one_phase.main()
except Exception as exc:
    one_phase.save(HERE / 'CONSUMER_FAILURE.json', {'time': time.time(), 'entry': 'authorized_jump_route', 'error': repr(exc), 'traceback': traceback.format_exc(), 'automatic_retry': False})
    raise
