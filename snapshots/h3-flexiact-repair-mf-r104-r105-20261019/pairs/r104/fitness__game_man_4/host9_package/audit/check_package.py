import json,sys,copy,ast
from pathlib import Path
R=Path(sys.argv[1]).resolve();sys.path.insert(0,str(R/'scripts'))
from common import *
verify_runtime();inherit=read(R/'configs/NUMERIC_INHERITANCE.json')
for n,h in inherit['files'].items():require(sha(METRIC/n)==h,'official numeric file changed: '+n)
runner=load('repair_official_tracker_cpucheck',METRIC/'run_tracks.py');checks=[]
for role in ['reference','native','guided']:
 manifest=METRIC/'SOURCE_INPUTS.json' if role=='reference' else R/'prepared'/role/'TRACK_INPUTS.json';item=read(manifest)['inputs'][0];require(item['id']==CASE and sha(item['file'])==item['sha256'],'source identity/media mismatch');runner.check_timebase(Path(item['file']));checks.append(role+'_original_49_timestamps')
 if role!='reference':
  runner.validate_generated_binding(item,Path(item['file']));checks.append(role+'_generation_binding');bad=copy.deepcopy(item);bad['id']='human/wrong/000'
  try:runner.validate_generated_binding(bad,Path(bad['file']))
  except ValueError:checks.append(role+'_wrong_pair_rejected')
  else:raise AssertionError('wrong pair accepted')
for p in (R/'scripts').glob('*.py'):ast.parse(p.read_text())
ast.parse((R/'audit/HOST41_WRAPPER_REFERENCE.txt').read_text());require('torch' not in sys.modules,'CPU check imported torch');print(json.dumps({'passed':True,'checks':checks,'numeric_files':len(inherit['files']),'GPU_started':False}))
