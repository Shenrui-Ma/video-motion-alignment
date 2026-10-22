from pathlib import Path
import json,hashlib,sys,copy
R=Path(__file__).resolve().parents[1];P=Path('/Users/researcher/DevProjects/h3-timing-ive-caption-ablation-r130-20261020');sys.path.insert(0,str(R/'scripts'))
from common import verify_official_prompt,info
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
row=info('long_0163'); old=read(Path('/Users/researcher/DevProjects/h3-ive-full-context-metrics-r124-20261020/incoming/long_0163/native_graph.json')); new=read(R/'configs/graphs'/f"{row['run_id']}.json")
a=row['original_task'];expected=old['5']['inputs']['prompt'].replace('Source caption: '+a['source_prompt']+'\n','').replace('[Shot 1] '+a['target_prompt']+'\n','[Shot 1] ')
assert expected==row['prompt']==new['5']['inputs']['prompt'];verify_official_prompt(row,new)
diff=read(P/'audit/ACTUAL_GRAPH_DIFF.json');actual=[]
assert old.keys()==new.keys()
for k in old:
 assert old[k]['class_type']==new[k]['class_type']
 assert old[k]['inputs'].keys()==new[k]['inputs'].keys()
 for f,v in old[k]['inputs'].items():
  if v!=new[k]['inputs'][f]:actual.append({'node':k,'field':f,'old':v,'new':new[k]['inputs'][f]})
assert sorted(actual,key=lambda x:(x['node'],x['field']))==sorted(diff['differences'],key=lambda x:(x['node'],x['field'])) and len(actual)==14
for x in actual:
 if(x['node'],x['field'])!=('5','prompt'):assert x['old'].replace('r124','r130')==x['new'].replace('timing_ive_caption_ablation_r130','timing_ive_full_context_r130')
for rel,v in read(P/'audit/INHERITED_BYTE_BINDINGS.json')['six_numerical_files'].items():assert sha(P/rel)==sha(Path(v['parent_file']))==v['parent_sha256']
rejections=[]
for field in ['source_prompt','target_prompt','edit_prompt']:
 bad=copy.deepcopy(row);bad['prompt']=(bad['prompt']+'\n'+a[field])if field!='edit_prompt'else bad['prompt'].replace(a[field],'')
 try:verify_official_prompt(bad,new)
 except Exception:rejections.append(field)
 else:raise AssertionError('mutation accepted')
# Actual submitted graph/history remains checked by inherited collection code at intake.
value={'passed':True,'producer_seal_sha256':sha(P/'deploy_manifest.json'),'consumer_freeze_sha256':sha(R/'CONSUMER_FREEZE.json'),'actual_graph_sha256':sha(R/'configs/graphs'/f"{row['run_id']}.json"),'actual_R124_graph_sha256':sha(Path(diff['actual_R124_graph'])),'difference_count':14,'only_semantic_change':'remove source and target caption narratives, preserving binding, original edit and retention','six_numerical_files_byte_equal':True,'targeted_mutations_rejected':rejections,'hypothesis':'Whether caption narratives induce subject/action rebinding or scene reconstruction; original caption states target seated and another person standing.','current_scope':'Native prompt control; optional guided requires independent decision','no_GPU_started':True}
(R/'audit/TARGETED_BINDING_CHECKS.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print(json.dumps(value,ensure_ascii=False))
