from pathlib import Path
import json,copy,hashlib,subprocess
root=Path(__file__).resolve().parents[2]; inv=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=Path(__file__).parent;d=read(inv);assert not any(x['id']=='r89_short_0178' for x in d['items']);prev=inv.read_bytes();(a/'PREVIOUS.json').write_bytes(prev)
p=next(x for x in read(root/'configs/contract.json')['pairs'] if x['source_id']=='short_0178');s=root/'showcase/short_0178';i=root/'incoming/short_0178';g=read(i/'PAIR_RUNTIME_GATE.json');m=read(s/'PRESENTATION.json');human=root/'results/short_0178/HUMAN_REVIEW.json';rv=root/'audit/visual_review_short0178/REVIEW.json'
assert g['passed'] is True and all(x is True for x in g['checks'].values()) and m['gate']['sha256']==sha(i/'PAIR_RUNTIME_GATE.json')
assert read(human)['collection_sha256']==sha(i/'COLLECTION.json') and read(human)['review_evidence']['sha256']==sha(rv)
r=copy.deepcopy(next(x for x in d['items'] if x['id']=='r89_short_0085'));r={k:(v.replace('short_0085','short_0178') if isinstance(v,str) else v) for k,v in r.items()}
r.update(title='腹部近景：白衬衫改蓝',task=p['original_task']['edit_prompt'],display_task='将白色衬衫改为蓝色，保留原双手动作与背景。',original_task=p['original_task'],valid_frames=121,review_summary='两版蓝衬衫编辑完成，腹部、其余服装及背景保留。全121帧中双手下移、回到腹部、停留和末段轻扫均与原片阶段接近；普通版无清楚时延，固定引导未见明显额外时序收益。')
r['evidence_paths']=[str(root.parent/'h3-timing-ive-subject-capacity-r89-20261018/configs/scientific_contract.json'),str(root.parent/'h3-timing-ive-subject-capacity-r89-20261018/configs/graphs/r89_short_0178_seed2026101701_native.json'),str(s/'PRESENTATION.json'),str(i/'PAIR_RUNTIME_GATE.json'),str(i/'COLLECTION.json'),str(human),str(rv)]
r['media_sha256']={k:sha(Path(r[k])) for k in ['reference_video_path','ordinary_video_path','guided_video_path','comparison_video_path']}
assert [r['media_sha256'][k] for k in ['reference_video_path','ordinary_video_path','guided_video_path']]==[x['sha256'] for x in m['inputs']]
assert r['media_sha256']['ordinary_video_path']==g['runs']['native']['video']['sha256'] and r['media_sha256']['guided_video_path']==g['runs']['forced']['video']['sha256']
props=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',r['comparison_video_path']]))['streams'][0]
assert (props['width'],props['height'],props['avg_frame_rate'],int(props['nb_read_frames']))==(3840,808,'24/1',121)
r['comparison_properties']=props;r['evidence_sha256']={p:sha(Path(p)) for p in r['evidence_paths']};r['quantitative_metrics']['motion_fidelity']['valid_frames']=121
d['items'].append(r);tmp=inv.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(inv)
out={'added':1,'items':len(d['items']),'unique_sources':len({x['source_id'] for x in d['items']}),'inventory_sha256':sha(inv),'prior_sha256':hashlib.sha256(prev).hexdigest(),'review_sha256':sha(rv)};(a/'UPDATE.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
