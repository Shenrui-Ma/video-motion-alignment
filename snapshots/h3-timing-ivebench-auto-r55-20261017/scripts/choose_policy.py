"""Root selects an existing policy from independent R53 evidence before production seal."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R53=ROOT.parent/'h3-timing-signed-source6980766-r53-20261017'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def policy_dependencies(choice):
 if choice!='signed_R53':return {}
 manifest=read(R53/'deploy_manifest.json');result={}
 for rel in ('scripts/delayed_window_policy.py','extensions/H3AutomaticWindowRouter/delayed_window_policy.py'):
  digest=sha(R53/rel)
  if digest!=manifest['files'][rel]['sha256']:raise ValueError('frozen signed-policy dependency changed: '+rel)
  result[rel]=digest
 return result
def main(choice,evidence,reason,root_decision=False):
 if not root_decision:raise ValueError('explicit root policy decision required')
 evidence=Path(evidence).resolve()
 if not evidence.is_relative_to(R53.resolve()) or evidence.suffix!='.json':raise ValueError('use independent R53 JSON evidence')
 if not reason.strip():raise ValueError('record the scientific decision reason')
 if (ROOT/'deploy_manifest.json').exists() or (ROOT/'configs/POLICY_SELECTION.json').exists():raise FileExistsError('policy already selected or production sealed')
 protocol=read(ROOT/'configs/protocol.json')
 if protocol['policy_choice']['status']!='ROOT_DECISION_PENDING' or read(ROOT/'configs/PARENT_CLOSURE.json')['ready']:raise ValueError('policy must precede actual parent production binding')
 candidates=read(ROOT/'configs/POLICY_CANDIDATES.json')['candidates']
 record={'schema':'r55-independent-policy-selection-v1','status':'FROZEN_BY_ROOT','choice':choice,'reason':reason,'independent_evidence_original':str(evidence),'independent_evidence_sha256':sha(evidence),'selected_files':{}}
 original=read(evidence)  # ensure complete JSON before making any changes
 for name,rel in [('scripts_policy.py','scripts/automatic_window_policy.py'),('controller_policy.py','extensions/H3AutomaticWindowRouter/automatic_window_policy.py')]:
  path=ROOT/'configs/policy_candidates'/choice/name
  if sha(path)!=candidates[choice][name]:raise ValueError('candidate policy bytes changed')
  record['selected_files'][rel]=sha(path)
 record['selected_files'].update(policy_dependencies(choice))
 for name,rel in [('scripts_policy.py','scripts/automatic_window_policy.py'),('controller_policy.py','extensions/H3AutomaticWindowRouter/automatic_window_policy.py')]:shutil.copyfile(ROOT/'configs/policy_candidates'/choice/name,ROOT/rel)
 for rel in policy_dependencies(choice):shutil.copyfile(R53/rel,ROOT/rel)
 shutil.copyfile(evidence,ROOT/'configs/POLICY_EVIDENCE_R53.json')
 record['independent_evidence_copy']='configs/POLICY_EVIDENCE_R53.json'
 (ROOT/'configs/POLICY_SELECTION.json').write_text(json.dumps(record,indent=2)+'\n')
 protocol['policy_choice']=dict(record,source_result_used='independent R53; no IVEBench output selection')
 (ROOT/'configs/protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
 inheritance=read(ROOT/'configs/NUMERICAL_INHERITANCE.json')
 for rel,digest in record['selected_files'].items():inheritance[rel]={'current_sha256':digest,'parent_sha256':digest,'exact':True,'source':choice,'selection_sha256':sha(ROOT/'configs/POLICY_SELECTION.json')}
 (ROOT/'configs/NUMERICAL_INHERITANCE.json').write_text(json.dumps(inheritance,indent=2)+'\n')
 print(json.dumps(record,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--choice',required=True,choices=['delay_only_R50','signed_R53']);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--reason',required=True);p.add_argument('--root-decision',action='store_true');a=p.parse_args();main(a.choice,a.evidence,a.reason,a.root_decision)
