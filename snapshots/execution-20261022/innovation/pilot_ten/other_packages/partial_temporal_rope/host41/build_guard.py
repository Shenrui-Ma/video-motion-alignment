import sys,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;E=P.parents[4];H=E/'supervision/innovation_handoff';sys.path.insert(0,str(H))
import activate_direction_pilots as activation
ROOT='/data4/research-user/h3_runs/benchmark_schedule_20261022'
override=P/'base_manifest_override.json'
base=json.loads(override.read_text()) if override.exists() else json.loads((H/'records/host41/remaining_activation.json').read_text())['manifest']
assert sum(j['id'].endswith('_direction_gated') for j in base['jobs'])==10
pilots=json.loads((P/'jobs.json').read_text())
records=json.loads((E/'innovation/pilot_ten/direction_package/host41/deployment_receipt.json').read_text())['records']
assets=[{'path':r['destination'],'sha256':r['sha256']} for r in records if any(x in r['destination'] for x in ('/innovation_cache/','/input/','/H3TrustedConditionCache/'))]
assets+=json.loads((P/'node_sha_verification.json').read_text())+json.loads((P/'graph_deployment.json').read_text())['files']
for name in ('core.py','layout.py','schedule.py'):
 assets.append({'path':ROOT+'/custom_nodes/H3Study/'+name,'sha256':hashlib.sha256((E/'inference/package/custom_nodes/H3Study'/name).read_bytes()).hexdigest()})
assets.append({'path':ROOT+'/scripts/manage_service.py','sha256':hashlib.sha256((E/'inference/package/scripts/manage_service.py').read_bytes()).hexdigest()})
req={'root':ROOT,'base':base,'pilots':pilots,'assets':assets}
(P/'handoff_request.json').write_text(json.dumps(req,indent=2)+'\n')
ops=(H/'remote_ops.py').read_text().split("if __name__ == '__main__':")[0]
body=activation.REMOTE_BODY.replace("directory/'direction_activation.json'","directory/'partial_activation.json'")
script=ops+'\n'+body+'\n'+(P/'guard_logic.py').read_text()+'\nREQ=json.loads('+repr(json.dumps(req))+')\n'
script+='''if __name__=='__main__':
 try:guard(REQ)
 except BlockingIOError:print('existing handoff guard holds lock')
 except Exception as error:
  atomic(Path(REQ['root'])/'innovation_handoff/partial_guard_status.json',{'status':'failed','error':repr(error),'unix':time.time()})
  raise
'''
(P/'partial_pilot_handoff.py').write_text(script)
print('Guard prepared: base',len(base['jobs']),'pilots',len(pilots['jobs']),'assets',len(assets))
