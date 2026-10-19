from pathlib import Path
import hashlib,json,subprocess,time
R=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
backup=R/'audit/BEFORE_EVALUATION_SCOPE_SEAL.json';assert not backup.exists()
backup.write_bytes((R/'deploy_manifest.json').read_bytes())
p=R/'configs/scientific_contract.json';old=p.read_bytes();(R/'audit/BEFORE_EVALUATION_SCOPE_CONTRACT.json').write_bytes(old)
rule=R/'design/EVALUATION_RULES.txt';rule.write_text('只评估IVEBench short_0114这一条原片；105有效帧。对照为R100六段提示词普通编辑与R109一句话提示词普通编辑。先检查篮球改变、人物身份、头部/上身裁切、地面占比和相机运动，再描述动作相位。R100引导成片不构成本次新提示词配对。\n')
v=json.loads(old);v['evaluation'].update(fixed_case_denominator=1,rules_sha256=sha(rule),visibility_policy='One basketball source: ball appearance, player identity, framing and camera motion first, then physical event phase.',adaptation='Same official short_0114 source in both ordinary prompt conditions; all105valid frames, no temporal guidance.')
p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
subprocess.run(['python3','scripts/execution_gate.py','seal'],cwd=R,check=True)
(R/'audit/EVALUATION_SCOPE_AMENDMENT.json').write_text(json.dumps({'old_seal_sha256':sha(backup),'new_seal_sha256':sha(R/'deploy_manifest.json'),'changed_fields':['evaluation.fixed_case_denominator','evaluation.rules_sha256','evaluation.visibility_policy','evaluation.adaptation'],'graph_changed':False,'numerical_kernels_changed':False,'reason':'Independent review found inherited two-source evaluation metadata; fix to single basketball source before launch.','unix':time.time()},indent=2)+'\n')
print(sha(R/'deploy_manifest.json'))
