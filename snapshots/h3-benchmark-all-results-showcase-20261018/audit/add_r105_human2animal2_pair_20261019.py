from pathlib import Path
import copy,json,hashlib,time,re
R=Path(__file__).resolve().parents[1];C=R.parent/'h3-flexiact-remaining-repair-metrics-r105-20261019'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source='human2animal_2__movie_man_11';a=C/'incoming_pairs'/source;s=C/'showcase_pairs'/source
contract=C/'configs/contract.json';c=next(x for x in read(contract)['sources'] if x['source_id']==source)
pres=s/'PRESENTATION.json';pr=read(pres);gate=a/'PAIR_RUNTIME_GATE.json';g=read(gate)
review=C/'audit/full_frame_review'/source/'paired/REVIEW.json';v=read(review)
assert sha(review)=='8fd2dbdc952ccd5d1cab55a27e7f7eb297e747ef39e96cef2af0f3d09d1e2713'
assert g['passed'] and all(g['checks'].values()) and g['runs']['native']['routed_blocks']==0 and g['runs']['forced']['routed_blocks']==450
assert v['coverage']['all_frames_visually_viewed'] and v['coverage']['count']==147 and v['overall_temporal_verdict']=='NO_CLEAR_BENEFIT'
evidence=[contract,gate,a/'COLLECTION.json',pres,review,review.parent/'MEDIA_BINDINGS.json',C/'audit/ROOT_NATIVE_REVIEW_human2animal_2__movie_man_11.json',C/'prepared'/source/'paired/MF_INPUTS.json']
media={'reference_image_path':str(C/c['portrait']['file']),'reference_video_path':str(C/c['source']['file']),'ordinary_video_path':str(a/'native.mp4'),'guided_video_path':str(a/'forced.mp4'),'comparison_video_path':str(s/'source_native_guided_full_valid.mp4')}
assert sha(media['ordinary_video_path'])==g['runs']['native']['video']['sha256'] and sha(media['guided_video_path'])==g['runs']['forced']['video']['sha256'] and sha(media['comparison_video_path'])==pr['videos'][0]['sha256']
p=R/'inventory/flexiact.json';before=sha(p);d=read(p);old=copy.deepcopy(d['items']);row=copy.deepcopy(next(x for x in old if x['id']=='flex_r104_fitness__game_man_4_fixed'))
summary='全部147有效帧审阅：两版均保留目标年长男子、深蓝西装与室外场景，并做出盘腿前屈动作；视角比参考更正面，前屈幅度较浅。参考双手落地在24–32帧，两版都在64–70帧，延后持续。固定引导无清楚时序改善；低位前屈因幅度与视角差异，无法可靠指定等效姿态到达时刻。'
row.update(id='flex_r105_human2animal_2__movie_man_11_fixed',source_id='human2animal_2',reference_image_id='movie_man_11',variant='R105 · 提示词修复后普通编辑与固定时序引导',title='盘腿前屈 · movie_man_11',task=c['display_task'],display_task=c['display_task'],**media,preview_html=str(Path('/Users/researcher/Downloads')/f'H3_R105_{source}_固定时序引导对照_20261019.html'),review_status='角色替换已完成，视角与幅度有差异，手部延后持续',review_status_code='partial_camera_amplitude_no_clear_benefit',review_summary=summary,display_summary=summary,count_as_complete_task_success=False,motion_transfer='partial_camera_and_amplitude',pair_group='官方素材自建交叉配对',input_contract_path=str(contract),prompt=c['prompt'],prompt_version=c['prompt_version'],input_reference_image_sha256=c['portrait']['sha256'],input_reference_video_sha256=c['source']['sha256'],scene_requirement='目标图室外铺装路面、草地与植被场景',judgment_source='root完整审阅147帧三栏图，目标身份、场景、动作、视角与幅度分别验收。',event_review={'file':str(review),'sha256':sha(review)},parent_inventory_id='flex_r66_human2animal_2__movie_man_11',runtime={f'{k}_job_wall_seconds':g['runs'][k]['job_wall_seconds'] for k in ['native','forced']},evidence_paths=[str(x) for x in evidence],evidence_sha256={str(x):sha(x) for x in evidence},media_sha256={k:sha(x) for k,x in media.items()})
assert not any(x['id']==row['id'] for x in old);d['items'].append(row);assert d['items'][:-1]==old
d['previous_inventory_sha256']=before;d['updated_unix']=time.time();assert sha(p)==before
audit=R/'audit/r105_human2animal2_pair_20261019';audit.mkdir(exist_ok=False);(audit/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes());p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
html=Path(row['preview_html']);h=html.read_text();message='<p>成片审阅：'+summary+'</p>';new=h.replace('</p><figure>','</p>'+message+'<figure>',1);assert new!=h
assert re.findall(r'data:[^\"\s>]+',h)==re.findall(r'data:[^\"\s>]+',new);html.write_text(new)
update={'file':str(html),'previous_sha256':hashlib.sha256(h.encode()).hexdigest(),'sha256':sha(html),'review':str(review),'embedded_assets_unchanged':True};(review.parent/'HTML_UPDATE.json').write_text(json.dumps(update,ensure_ascii=False,indent=2)+'\n')
receipt={'before_sha256':before,'after_sha256':sha(p),'id':row['id'],'review_sha256':sha(review),'html':update};(audit/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))
