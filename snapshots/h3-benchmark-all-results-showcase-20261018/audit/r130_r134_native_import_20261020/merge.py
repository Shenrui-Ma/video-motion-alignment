from pathlib import Path
import hashlib, json, os, time

B=Path('/Users/researcher/DevProjects'); R=B/'h3-benchmark-all-results-showcase-20261018'; A=Path(__file__).parent
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/ivebench.json'; prepared=json.loads((A/'PREPARED_ROWS.json').read_text())
before=H(p); assert before==prepared['inventory_sha256']
x=json.loads(p.read_text()); (A/'ivebench_before.json').write_bytes(p.read_bytes())
proof=B/'h3-ive-caption-scrubs-mf-host9-20261020/audit/RESULTS_VERIFIED.json'
release=proof.parent/'FINAL_RELEASE_VERIFIED.json'
assert H(proof)=='5383d687c2bca30bc2b60729a1775ec2f2f5df8c6eb477cd24d513f1f0b2a367'
assert H(release)=='6898f3855df0bc9956cb36904f1ced534bba0d4a084ff189f3a825cfddecfd67'
scores=json.loads(proof.read_text())['results']
for r in prepared['rows']:
    assert r['id'] not in {v['id'] for v in x['items']}
    score=next(s for s in scores if {'id':r['id'],'field':'native'} in s['inventory_bindings'])
    assert score['actual_generated_video_sha256']==r['media_sha256']['ordinary_video_path']
    assert score['valid_frames']==score['evaluation_frames']==r['valid_frames']
    assert H(score['result_file'])==score['result_sha256'] and H(score['release_file'])==score['release_sha256']
    files=[proof,release,Path(score['result_file']),Path(score['release_file'])]
    mf=r['quantitative_metrics']['motion_fidelity']
    mf.update(native=score['score'],status='complete',source_files=[str(f) for f in files],source_sha256={str(f):H(f) for f in files},scope='官方IVEBench MF；任务验收和源事件时间区间分别记录。')
    r['evidence_paths'] += [str(f) for f in files]
    r['evidence_sha256'].update({str(f):H(f) for f in files})
    for f,s in r['evidence_sha256'].items():assert H(f)==s,f
    x['items'].append(r)
extra=B/'h3-timing-architecture-r2-20261016/audit/short0344_full_review_20261020/ROOT_REVIEW.json'
assert H(extra)=='7131fc7a4b84efab7297136d5b4ef2846b4142b9618eb230f3b1dcf04df8ce96'
e=json.loads(extra.read_text());r=next(v for v in x['items'] if v['id']=='r73_short_0344')
assert H(e['input'])==e['input_sha256'];assert e['inspected_frames']==list(range(58))
assert Path(r['comparison_video_path']).resolve()==Path(e['input']).resolve()
r.setdefault('supplementary_full_frame_reviews',[]).append({'file':str(extra),'sha256':H(extra),'scope':e['review_scope'],'events':e['event_brackets'],'result':e['motion_result']})
r['evidence_paths'].append(str(extra));r['evidence_sha256'][str(extra)]=H(extra)
x['updated_unix']=time.time(); x['previous_inventory_sha256']=before
rows=x['items']; x['counts'].update(items=len(rows),unique_sources=len({r['source_id'] for r in rows}),native_only=sum(r.get('comparison_kind')=='native_only' for r in rows),native_only_skipped_after_review=sum(r.get('comparison_kind')=='native_only' and r.get('guidance_decision')=='skip' for r in rows))
assert H(p)==before
t=p.with_suffix('.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
overlay=R/'task_view_20261019/display_evidence.json'; (A/'display_evidence_before.json').write_bytes(overlay.read_bytes()); d=json.loads(overlay.read_text())
for r in prepared['rows']:
    d['versions'][r['id']]={'alignment_native':r['action_alignment_bool'],'alignment_guided':None,'summary':r['display_summary'],'still_frame':r['key_same_frame_indices'][0],'still_reason':'同帧检查编辑范围与原构图','review_file':r['full_frame_review_path'],'review_sha256':H(r['full_frame_review_path']),'guided_presence':False,'mode':'native_only'}
d['latest_presentation_update']={'created_unix':time.time(),'version_ids':[r['id'] for r in prepared['rows']],'scope':'两条完整Native审阅、实际skip与MF已绑定。'}
t=overlay.with_suffix('.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.replace(t,overlay)
receipt={'created_unix':time.time(),'before_sha256':before,'after_sha256':H(p),'added':[r['id'] for r in prepared['rows']],'extra_review':'r73_short_0344','ive_counts':x['counts'],'total_versions':len(rows)+31,'display_evidence_sha256':H(overlay),'published':False}
(A/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))
