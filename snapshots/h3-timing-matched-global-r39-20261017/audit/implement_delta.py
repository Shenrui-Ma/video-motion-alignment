from pathlib import Path
import json,hashlib
r=Path('/Users/researcher/DevProjects/h3-timing-matched-global-r39-20261017');read=lambda p:json.loads(p.read_text());save=lambda p,v:p.write_text(json.dumps(v,indent=2)+'\n')
f=r/'configs/parent_counterfactual.json';d=read(f);c=d['counterfactual'];save(f,{'source_complete_audit_sha256':read(r/'PROTOCOL.json')['source_evidence']['R32_counterfactual_sha256'],'counterfactual':{k:c[k] for k in ('conditioning','seed','full_grid','full_physical_indices','initial_noise','reference')},'native_prefix':[x for x in c['branches'] if x['branch']=='native' and x['physical_index']<=2]})
f=r/'extensions/H3StaticWindowRouter/core.py';s=f.read_text();repls={"Frozen single global Full branch":"Frozen four matched global Full branches","frozen-index4-v1":"frozen-matched-indices-v1","ELIGIBLE_STEPS = (4,)":"ELIGIBLE_STEPS = (2, 4, 5, 6)","INPUT_STEPS = (4,)":"INPUT_STEPS = (2, 4, 5, 6)","def indices(self): return (4,)":"def indices(self): return (2, 4, 5, 6)","'expected_model_nfe': 21":"'expected_model_nfe': 24","'model_nfe_bounds': [21, 21]":"'model_nfe_bounds': [24, 24]","s.full_indices != [4] or nfe != 21":"s.full_indices != [2, 4, 5, 6] or nfe != 24","requires static index4 only,21NFE":"requires static indices2/4/5/6,24NFE","incomplete frozen21NFE":"incomplete frozen24NFE"}
for a,b in repls.items():assert a in s,a;s=s.replace(a,b)
f.write_text(s)
f=r/'extensions/H3StaticWindowRouter/static_plan.py';s=f.read_text().replace('active=n==4','active=n in (2,4,5,6)').replace('predeclared_global_pulse','matched_timing_global_full');f.write_text(s)
# Count/schema gates, no numerical kernel changed.
f=r/'scripts/preflight.py';s=f.read_text().replace("!=[4]","!=[2,4,5,6]").replace("s['NFE']!=21","s['NFE']!=24").replace("s['blocks']!=1050","s['blocks']!=1200").replace("s['route_calls']!=50","s['route_calls']!=200").replace("'NFE':21","'NFE':24").replace("'branch_PT':21","'branch_PT':24");f.write_text(s)
f=r/'scripts/build_manifest.py';s=f.read_text().replace("('PROTOCOL.json','README.txt'","('SCIENCE_PROTOCOL.json','PROTOCOL.json','README.txt'");f.write_text(s)
