from pathlib import Path
import json,hashlib,os,time,math
A=Path(__file__).parent;R=A.parents[1];B=R.parent;H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();p=R/'inventory/ivebench.json';before=H(p);assert before=='22aa3d0234ffa9751b486d21ab2735054b36becb8515d311a09e714aea3716f2'
x=json.loads(p.read_text());rows=json.loads((A/'DRAFT_ROWS.json').read_text());by={r['id']:r for r in rows};proof=B/'h3-ive-bird-aligned-mf-host41-20261020/audit/RESULTS_VERIFIED.json';release=proof.parent/'FINAL_RELEASE_VERIFIED.json';assert H(proof)=='8e3856e6a05300cd84fe21dc386a7ece955b684eb0547b9525ec37b5261b470f';assert H(release)=='1afb6c5132fbb6bb3f9f012b585305a952b64dc5981ed09bb39dad536a05a34e';j=json.loads(proof.read_text());assert j['completed_targets']==j['requested_targets']==3
for z in j['results']:
 for bd in z['inventory_bindings']:
  r=by[bd['id']];field=bd['field'];m=r['quantitative_metrics']['motion_fidelity'];media={'native':'ordinary_video_path','guided':'guided_video_path','aligned':'alternative_video_path'}[field]
  assert r['media_sha256'][media]==z['actual_generated_video_sha256'];assert z['valid_frames']==z['evaluation_frames']==r['valid_frames']==106;assert z['evaluation_fps']==24
  for key in ['result','release']:assert H(z[key+'_file'])==z[key+'_sha256']
  actual=json.loads(Path(z['result_file']).read_text());assert math.isfinite(z['score'])
  m[field]=z['score'];m.setdefault('source_files',[]).extend([str(proof),str(release),z['result_file'],z['release_file']])
for r in rows:
 m=r['quantitative_metrics']['motion_fidelity'];m['status']='complete';m['scope']='官方IVEBench MF；基础任务验收和逐帧动作结论单独记录。'
 if r['comparison_kind']=='guided_pair':m['delta']=m['guided']-m['native']
 else:
  assert r['guided_video_path'] is None and m['guided'] is None and r['actual_routed_blocks']==0
  m['delta_aligned_minus_native']=m['aligned']-m['native'];old=next(z for z in x['items'] if z['id']=='r122_long_0039_generic_retention');assert old['media_sha256']['ordinary_video_path']==r['media_sha256']['ordinary_video_path'];assert old['quantitative_metrics']['motion_fidelity']['native']==m['native'];m['source_files']+=old['quantitative_metrics']['motion_fidelity'].get('source_files',[])
 m['source_files']=list(dict.fromkeys(m['source_files']));m['source_sha256']={f:H(f) for f in m['source_files']};r['evidence_paths']+=m['source_files'];r['evidence_paths']=list(dict.fromkeys(r['evidence_paths']));r['evidence_sha256']={f:H(f) for f in r['evidence_paths']}
 assert not any(z['id']==r['id'] for z in x['items']);x['items'].append(r)
x['updated_unix']=time.time();i=x['items'];x['counts'].update(items=len(i),unique_sources=len({v['source_id'] for v in i}),guided_pairs=sum(v.get('comparison_kind')=='guided_pair' for v in i),activated_fixed_pairs=sum(v.get('comparison_kind')=='guided_pair' and (v.get('actual_routed_blocks') or v.get('routed_block_calls') or 0)>0 for v in i),native_only=sum(v.get('comparison_kind')=='native_only' for v in i),positional_controls=sum(v.get('comparison_kind')=='positional_control' for v in i))
assert len(i)==70;assert H(p)==before;(A/'ivebench_before.json').write_bytes(p.read_bytes());tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
r={'before_sha256':before,'after_sha256':H(p),'added':[r['id'] for r in rows],'created_unix':time.time(),'proof':str(proof),'proof_sha256':H(proof),'ive_counts':x['counts']};(A/'RECEIPT.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))
