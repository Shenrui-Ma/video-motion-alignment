"""Root-authorized SSH route for the unchanged frozen generated-pose extractor."""
import argparse, hashlib, json, time
from pathlib import Path
import run_one
run_one.SSH[1:1] = ['-J', 'H3_SERVER_B']
p = argparse.ArgumentParser()
p.add_argument('--source', required=True)
p.add_argument('--method', required=True)
p.add_argument('--metric-inputs', required=True)
p.add_argument('--mapping', required=True)
a = p.parse_args()
here = Path(__file__).resolve().parent
record = {'route': 'Mac -> authorized .41 -> same .9 account', 'SSH': run_one.SSH,
          'freeze_sha256': hashlib.sha256((here / 'FREEZE.json').read_bytes()).hexdigest(),
          'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'time': time.time()}
(here / 'audit' / ('jump_route_' + str(time.time_ns()) + '.json')).write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(run_one.execute(a.source, a.method, a.metric_inputs, a.mapping), allow_nan=False))
