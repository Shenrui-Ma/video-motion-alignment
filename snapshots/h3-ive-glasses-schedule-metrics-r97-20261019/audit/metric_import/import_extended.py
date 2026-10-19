from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[2];A=Path(__file__).parent;Q=R.parent/'h3-ive-followup-quantitative-r97-r99-r100-20261019';C=Q/'cases/r97_short0358';T=Q/'actual_host41/cases/r97_short0358';I=R.parent/'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json'
def rd(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
d=rd(I);r=next(x for x in d['items'] if x['id']=='r97_short_0358_extended');old=next(x for x in d['items'] if x['id']=='r89_short_0358');score=T/'results/extended.json';s=rd(score);inputp=C/'INPUTS.json';ip=rd(inputp);sreport=C/'tracks/source/REPORT.json';treport=T/'tracks/extended/REPORT.json';reuse=C/'SOURCE_REUSE_RECEIPT.json';ver=Q/'audit/R97_RESULT_VERIFIED.json';v=rd(ver)
assert s['actual_generated_video_sha256']==sha(Path(r['guided_video_path']))==ip['roles']['extended']['full_sha256']
assert s['actual_gate_sha256']==sha(R/'incoming/CONTROL_RUNTIME_GATE.json')==ip['gate_sha256']
assert s['case_inputs_sha256']==sha(inputp) and s['source_report']['sha256']==sha(sreport) and s['target_report']['sha256']==sha(treport)
assert s['valid_frames']==ip['valid_frames']==105 and s['fps']==ip['fps']==24 and ip['crop_xywh']==[16,8,1280,720]
assert sha(Path(r['reference_video_path']))==ip['roles']['source']['full_sha256']
tr=rd(treport);sr=rd(sreport);rr=rd(reuse)
assert tr['passed'] is True and tr['effective_frame_count']==105 and tr['score_frame_indices']==list(range(105)) and tr['decoded_frame_md5']==ip['roles']['extended']['score_frame_md5']
assert tr['score_video']['sha256']==ip['roles']['extended']['score_sha256'] and tr['source_score_sha256']==ip['roles']['source']['score_sha256']
assert rr['passed'] is True and rr['verified_same_data_protocol_and_runtime'] is True and sha(Path(rr['source_tracks']['file']))==s['source_tracks_sha256']
assert v['passed'] is True and v['same_official_runtime'] is True and v['same_tracking_host_gpu_model_torch'] is True and v['score_sha256']==sha(score)
m=old['quantitative_metrics']['motion_fidelity'];assert m['status']=='complete'
for path,digest in m['source_sha256'].items():assert sha(Path(path))==digest,path
assert sha(Path(r['ordinary_video_path']))==old['media_sha256']['ordinary_video_path'] and sha(Path(r['alternative_video_path']))==old['media_sha256']['guided_video_path']
native=m['native'];fixed=m['guided'];extended=s['motion_fidelity'];assert (native,fixed,extended)==(v['ordinary'],v['fixed6_14'],v['extended6_19'])
files=list(dict.fromkeys(m['source_files']+[str(x) for x in [score,inputp,sreport,treport,reuse,ver]]));q={'native':native,'guided':extended,'delta':extended-native,'original_fixed':fixed,'extended_minus_original_fixed':extended-fixed,'higher_is_better':True,'status':'complete','source_files':files,'source_sha256':{p:sha(Path(p)) for p in files},'valid_frames':105,'scope':'同一0358样例的引导区间消融；native为普通编辑，guided为延长6–19步，original_fixed为原6–14步。官方MF不直接等同动作时差。','protocol':m['protocol']}
assert r['quantitative_metrics']['motion_fidelity']['status']=='pending';(A/'PREVIOUS.json').write_bytes(I.read_bytes());r['quantitative_metrics']['motion_fidelity']=q
t=I.with_suffix('.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');t.replace(I)
out={'modified':['r97_short_0358_extended'],'inventory_sha256':sha(I),'items':len(d['items']),'native':native,'extended':extended,'original_fixed':fixed,'delta':extended-native,'extended_minus_original_fixed':extended-fixed,'preserved_visual_conclusion':True};(A/'IMPORT_RECEIPT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
