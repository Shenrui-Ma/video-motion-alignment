from pathlib import Path
import json,hashlib,copy,time,subprocess
R=Path(__file__).resolve().parents[2];D=R.parent;C=D/'h3-ive-p1-guidance-metrics-r99-20261019';M=D/'h3-ive-followup-quantitative-r97-r99-r100-20261019';A=Path(__file__).parent
I=R/'inventory/ivebench.json'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
presfile=C/'showcase/short_0210/PRESENTATION.json';pres=read(presfile);gatefile=Path(pres['gate']['file']);gate=read(gatefile);assert gate['passed'] and sha(gatefile)==pres['gate']['sha256']
reviewfile=C/'audit/agent_full_review_short0210/REVIEW.json';review=read(reviewfile);assert review['reviewed_frames']==list(range(87)) and review['pair_gate_sha256']==sha(gatefile)
colfile=C/'incoming/short_0210/COLLECTION.json';col=read(colfile)
for name,digest in col['files'].items():assert sha(colfile.parent/name)==digest
for row in pres['inputs']:assert sha(Path(row['file']))==row['sha256']
graph=read(colfile.parent/'graph.json');assert 'ref_image' not in graph['5']['inputs'] and '21' not in graph
comparison=presfile.parent/pres['video']['file'];assert sha(comparison)==pres['video']['sha256']
inputfile=M/'cases/r99_short_0210/INPUTS.json';inputs=read(inputfile);assert inputs['gate_sha256']==sha(gatefile) and inputs['valid_frames']==87 and inputs['fps']==24 and inputs['crop_xywh']==[16,8,1280,720]
metric_evidence=[inputfile,M/'audit/R99_0210_RESULT_VERIFIED.json'];scores={}
for role,media in zip(('source','native','forced'),pres['inputs']):
 r=inputs['roles'][role];assert r['full_sha256']==media['sha256']
 reportfile=M/'actual_host41/cases/r99_short_0210/tracks'/role/'REPORT.json';report=read(reportfile)
 assert report['selection_sha256']==sha(inputfile) and report['effective_frame_count']==87 and report['score_video']['sha256']==r['score_sha256'] and report['decoded_frame_md5']==r['score_frame_md5']
 assert report['tracker']=={'grid_size':10,'grid_query_frame':0,'backward_tracking':False,'offline':True,'window_len':60}
 metric_evidence.append(reportfile)
 if role!='source':
  f=M/'actual_host41/cases/r99_short_0210/results'/(role+'.json');score=read(f);scores[role]=score['motion_fidelity'];assert score['actual_generated_video_sha256']==media['sha256'] and score['actual_gate_sha256']==sha(gatefile) and score['case_inputs_sha256']==sha(inputfile)
  assert score['target_report']['sha256']==sha(reportfile) and score['target_tracks_sha256']==report['tracks_sha256']
  assert score['source_report']['sha256']==sha(M/'actual_host41/cases/r99_short_0210/tracks/source/REPORT.json')
  metric_evidence.append(f)
inv=read(I);assert not any(x['id']=='r99_short_0210' for x in inv['items'])
parent=next(x for x in inv['items'] if x['id']=='r71_short_0210');assert parent['alternative_video_path'] and sha(Path(parent['alternative_video_path']))==pres['inputs'][1]['sha256']
evidence=[presfile,gatefile,colfile,reviewfile,colfile.parent/'graph.json']
item={'id':'r99_short_0210','benchmark':'IVEBench','source_id':'short_0210','variant':'R99 / P1-local-v1 / matched historical Native plus fixed guidance','title':'舞台演讲：女人替换为男人（修复后的引导对照）','task':parent['task'],'original_task':copy.deepcopy(parent.get('original_task')),'display_task':'将舞台上的女讲者替换为男讲者，保留原舞台、构图和手势。','reference_image_used':False,'reference_image_path':None,'reference_video_path':pres['inputs'][0]['file'],'ordinary_video_path':pres['inputs'][1]['file'],'guided_video_path':pres['inputs'][2]['file'],'comparison_video_path':str(comparison),'review_summary':'全87有效帧审阅：两版男性替换、蓝色舞台及手势顺序均成立。普通编辑已大致同步，固定引导未见明确新增时序收益；官方MF由0.907711降至0.897710。','review_status':'任务完成，无明确时序收益，MF下降','review_status_code':'neutral_mf_decrease','evidence_paths':list(map(str,evidence)),'evidence_sha256':{str(p):sha(p) for p in evidence},'valid_frames':87,'generated_frames':90,'fps':24,'method_label':'固定时序引导（结构化提示词修复后的配对）','comparison_kind':'guided_pair','column_labels':['1.参考视频','2.普通编辑','3.时序引导'],'guidance_activation':'active','actual_routed_blocks':450,'prompt_version':'P1-local-v1','independent_sample':False,'parent_inventory_id':'r71_short_0210','sample_scope':'同一short0210原片；普通编辑复用R71实际P1，R99实际8条件/噪声/前6步门核验（本例为视频单参考6条件）后补引导。','support_for_clear_whole_event_repair':False}
item['sample_scope']='同一short0210原片；普通编辑复用R71实际P1，R99已核验实际视频单参考6条件、原AV噪声与前6步AV预测一致后补引导。'
item['media_sha256']={k:sha(Path(item[k])) for k in ('reference_video_path','ordinary_video_path','guided_video_path','comparison_video_path')}
item['quantitative_metrics']={'motion_fidelity':{'native':scores['native'],'guided':scores['forced'],'delta':scores['forced']-scores['native'],'higher_is_better':True,'status':'complete','source_files':list(map(str,metric_evidence)),'source_sha256':{str(p):sha(p) for p in metric_evidence},'valid_frames':87,'scope':'修复P1普通编辑与匹配固定引导的87有效帧；MF衡量轨迹相似性，具体动作时差由独立逐帧审阅说明。','protocol':'IVEBench official MF; commit2dcf8900ee65197f43854c76f61c66a32bb8dbfc; CoTracker3 offline,grid10,window60'}}
previous=I.read_bytes();(A/'PREVIOUS_INVENTORY.json').write_bytes(previous);inv['items'].append(item)
assert I.read_bytes()==previous
I.write_text(json.dumps(inv,ensure_ascii=False,indent=2)+'\n')
receipt={'changed':['r99_short_0210'],'preserved_old_items':len(inv['items'])-1,'count':len(inv['items']),'unique_sources':len(set(x['source_id'] for x in inv['items'])),'inventory_sha256':sha(I),'all_media_hashes_verified':True,'actual_pair_and_score_bindings_verified':True,'created_unix':time.time()}
(A/'IMPORT_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
