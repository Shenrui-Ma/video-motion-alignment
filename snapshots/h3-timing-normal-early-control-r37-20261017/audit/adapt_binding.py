from pathlib import Path
R=Path(__file__).resolve().parents[1]
f=R/'extensions/H3StaticWindowRouter/pair_gate.py';s=f.read_text().replace('Actual R26 normalized AV prefix; historical processed tree/raw input absent.','Actual R27 normal AV prefix and complete condition signature tree; raw input4 entity absent.').replace('import copy,uuid','import copy,uuid,hashlib,json')
pos=s.index('\ndef condition_audit_matches')
s=s[:pos]+'''
def parent_condition_matches(actual,expected):
    digest=lambda tree:hashlib.sha256(json.dumps(tree,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    t.require(digest(actual['tree'])==actual['sha256'] and digest(expected['tree'])==expected['sha256'],'condition signature tree digest mismatch')
    t.require(canonical_condition(actual['tree'])==canonical_condition(expected['tree']),'actual full processed/original condition signature differs beyond two UUID leaves')
    return {'historical_processed_condition_signature_tree':'matched_except_two_corresponding_UUIDs','historical_tensor_entity_comparison':False,'parent_condition_sha256':expected['sha256'],'current_condition_sha256':actual['sha256']}

def historical_input_signature(row,expected):
    t.require(row['same_input']==expected['native_input_signature'],'historical actual Native input signature differs')
    return {'historical_packed_input_signature_equal':True,'historical_packed_input_tensor_entity_comparison':False}
''' +s[pos:]
s=s.replace("'historical_packed_input_comparison':'not_available','historical_processed_tree_comparison':'not_available'","'historical_packed_input_tensor_entity_comparison':False")
s=s.replace("canonical_condition(s.initial_condition['tree'])","tree_gate=parent_condition_matches(s.initial_condition,t.read_json(t.ROOT/'configs/parent_actual_condition_tree.json'))")
s=s.replace("protocol['actual_native_prefix_evidence']","protocol['pairing']['actual_prefix_evidence']")
s=s.replace("'historical_processed_condition_tree':'not_archived','historical_packed_input':'not_archived',","'historical_processed_condition_tree':tree_gate,'historical_packed_input_tensor':'not_archived',")
s=s.replace("result=actual_prefix(row,self.records[n],row['file']);self.done.add(n)","result=actual_prefix(row,self.records[n],row['file']);result.update(historical_input_signature(row,self.records[n]));self.done.add(n)")
s=s.replace('diverge permanently from R26 Native','diverge permanently from R27 normal Native')
f.write_text(s)
f=R/'scripts/verify_completed.py';s=f.read_text().replace('actual_prefix,canonical_condition,condition_audit_matches','actual_prefix,canonical_condition,condition_audit_matches,parent_condition_matches,historical_input_signature')
s=s.replace("canonical_condition(c['conditioning']['tree']) # current UUID correspondence only; old full tree was not archived","parent_condition_matches(c['conditioning'],t.read_json(root/'configs/parent_actual_condition_tree.json'))")
s=s.replace("t.read_json(root/'PROTOCOL.json')['actual_native_prefix_evidence']","t.read_json(root/'PROTOCOL.json')['pairing']['actual_prefix_evidence']")
s=s.replace("if expected=='pass':prefix_proofs.append(actual_prefix(branches[n,b],expected_prefix[n],branches[n,b]['file']))","if expected=='pass':\n                proof=actual_prefix(branches[n,b],expected_prefix[n],branches[n,b]['file']);proof.update(historical_input_signature(branches[n,b],expected_prefix[n]));prefix_proofs.append(proof)")
s=s.replace('historical packedinput4 and processed full condition tree unavailable; only current same-state input and tree are verified; all future old endpoints N/A.','historical raw packedinput4 entity absent; historical actual input signatures0..4 and full original/processed condition signature tree independently matched (only two corresponding UUID leaves allowed); current rawinput4 archived; all future old endpoints N/A.')
f.write_text(s)
f=R/'tests/test_static.py';s=f.read_text().replace('test_actual_graph_and_no_fabricated_parent_tree','test_actual_graph_and_archived_parent_tree').replace("self.assertFalse((R/'configs/parent_actual_condition_tree.json').exists())","self.assertTrue((R/'configs/parent_actual_condition_tree.json').exists())")
f.write_text(s)
f=R/'scripts/build_manifest.py';s=f.read_text().replace('source40372 parent','normal source05 parent').replace("('PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json')","('PROTOCOL.json','design/PROTOCOL.json','design/README.txt','design/COMPARABILITY.json','design/FREEZE.json')").replace('timing_global_full_r29_20261017/inputs','timing_auto_controller_r27_20261017/inputs')
f.write_text(s)
# CPU stage scaffolding inherited, actual full-layout checks and binding-specific tests added separately.
old=R.parent/'h3-timing-fixed-early-global-r34-20261017'
for name in ('run_cpu_gate.py','seal_after_cpu.py'):
 s=(old/'audit'/name).read_text().replace('r34','r37').replace('R34','R37').replace('seed1701','seed1313')
 s=s.replace("('PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json')","('PROTOCOL.json','design/PROTOCOL.json','design/README.txt','design/COMPARABILITY.json','design/FREEZE.json')")
 # Preserve design directory in staging; flat rsync filenames would collide.
 s=s.replace("*[str(r/name) for name in ('PROTOCOL.json','design/PROTOCOL.json','design/README.txt','design/COMPARABILITY.json','design/FREEZE.json')]","str(r/'PROTOCOL.json'),str(r/'design')")
 (R/'audit'/name).write_text(s)
