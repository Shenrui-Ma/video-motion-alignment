from pathlib import Path
import json,hashlib,time,collections
R=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018')
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prev=R/'audit/progress_protocol_snapshot_20261020_v12.json'
out=R/'audit/progress_protocol_snapshot_20261020_v13.json'
assert not out.exists()
x=json.loads(prev.read_text()); x['created_unix']=time.time()
summary_path=R/'audit/latest_task_pairs_20261020_v11/SUMMARY.json'; summary=json.loads(summary_path.read_text())
inventories={b:json.loads((R/'inventory'/f'{b}.json').read_text())['items'] for b in ['ivebench','flexiact']}
assert sum(map(len,inventories.values()))==110
for b in inventories:
 p=R/'inventory'/f'{b}.json'
 assert H(p)==summary['inventory_bindings'][b]['sha256']
 x['inventory_bindings'][b]={'path':str(p),'sha256':H(p)}
i=inventories['ivebench']; ids={r['source_id'] for r in i}
c=x['counts']['IVEBench']; c.update(independent_source_videos=len(ids),unique_official_edit_tasks=len(ids),result_versions=len(i),short_source_ids=sorted(s for s in ids if s.startswith('short_')))
assert c['independent_source_videos']==41 and len(c['short_source_ids'])==26
c['derived_long_source_ids']=sorted(set(c['derived_long_source_ids'])|{'long_0116','long_0191'})
assert set(c['derived_long_source_ids'])|set(c['full_duration_long_source_ids'])|set(c['short_source_ids'])==ids
c['temporal_scope']='26 official short sources, 1 full-duration long_0081, 14 long excerpts; prepared24fps with recorded crop/padding; studied subset, not full official benchmark.'
for name,b in [('FlexiAct','flexiact'),('IVEBench','ivebench')]:
 rows=inventories[b]; cc=x['counts'][name]
 pair=[r for r in rows if r.get('comparison_kind')=='guided_pair']
 active=[r for r in pair if r.get('guidance_activation') in ('active','positive','fixed_active') or (r.get('actual_routed_blocks') or r.get('routed_block_calls') or 0)>0]
 assert len(pair)==cc['paired_versions'] and len(active)==cc['actual_guidance_versions']
assert len([r for r in i if r.get('comparison_kind')=='positional_control'])==1
assert len([r for r in i if r.get('comparison_kind')=='reference_origin_control'])==1
x['previous_snapshot']={'path':str(prev),'sha256':H(prev)}
x['latest_task_pair_audit']={'path':str(summary_path),'sha256':H(summary_path),'scope':'110 versions/58 task combinations/49 original sources/42 tasks with actual nonzero guidance pairs; positional and reference-origin controls are separate.'}
x['latest_task_pair_summary']=summary['summary']
x['totals'].update(independent_source_videos=49,unique_task_combinations=58,result_versions=110)
assert sum(z['unique_sources'] for z in summary['summary'].values())==49
assert sum(z['independent_task_combinations'] for z in summary['summary'].values())==58
assert sum(z['tasks_with_actual_pair'] for z in summary['summary'].values())==42
x['in_progress_excluded_from_counts']=[{'run':'R140','source':'short_0163','status':'Native loading; move pointing person to other side of laptop; completion not counted','host':'.9','gpu':2,'service_pid':8935,'start_ticks':'2649477984'}]
x['change_from_v12']='Added R137 and R139 Native-only results. Requested subject relocation fails in both: R137 also changes three pushup cycles to two; R139 reconstructs the room while gesture timing stays close. Both skipped guidance and exact-released. R139 official MF complete; R137 MF pending. No new actual guidance pair.'
x.pop('change_from_v11',None)
x.pop('change_from_v8',None);x.pop('source_list_correction',None);x.pop('counter_refresh',None)
x['new_records']=[{k:r.get(k) for k in ['id','source_id','comparison_kind','task_status','review_status','guidance_decision','display_summary','quantitative_metrics','full_frame_review_path']} for r in i if r['id'] in {'r137_long_0116_generic_retention','r139_long_0191_generic_retention'}]
assert len(x['new_records'])==2
out.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'path':str(out),'sha256':H(out),'totals':x['totals'],'latest':x['latest_task_pair_summary']},ensure_ascii=False,indent=2))
