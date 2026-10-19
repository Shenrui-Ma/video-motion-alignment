"""Bind independent final-pose evidence; do not change frozen observer outputs."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT.parent/'h3-timing-autoresearch-20261016'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,s):
 if not v:raise RuntimeError(s)
def write(name,v):
 with (HERE/name).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def main():
 results=json.loads((HERE/'RESULTS.json').read_text());p=json.loads((HERE/'PROTOCOL.json').read_text());conditionpath=HERE/'inputs/audit/r7_s05_normal_native_x0_conditioning.json';c=json.loads(conditionpath.read_text())
 pair=c['pair_snapshot'];require(pair['verified'] is True,'actual pair gate unverified')
 actualrefs=[x['clean_latent'] for x in pair['actual']['references'] if x['kind']=='video']
 require(actualrefs==[results['reference']],'observer ref not actual model ref')
 gatepath=ROOT/'analysis/pose/replication/native_replay_local_gate.json';gate=json.loads(gatepath.read_text())
 require(gate['passed'] and all(gate['checks'].values()) and gate['matching_rgb_frame_count']==141,'final exact replay gate failed')
 for path,digest in gate['input_provenance_sha256'].items():require(sha(path)==digest,'replay provenance changed '+path)
 for video in gate['videos']:require(sha(video['path'])==video['sha256'],'replay video changed')
 cp=ROOT/'analysis/pose/pilot/r7_s05_normal_native_x0_provenance/conditioning.json'
 require(sha(cp)==sha(conditionpath),'critic/evaluator actualconditioning files differ')
 labels={}
 for threshold in (0.3,0.5):
  path=OLD/f'analysis/pose/pilot/s05_seed1_native_00001_.threshold{threshold}.timing.json';v=json.loads(path.read_text())
  require(v['edited']['sha256']==gate['videos'][0]['sha256'],'pose edited video not replay baseline')
  rows=[x for x in v['diagnostics'] if x['feature']=='arm_direction'];require([x['window'] for x in rows]==p['windows_inclusive'],'pose windows changed')
  labels[str(threshold)]={'path':str(path),'sha256':sha(path),'edited_video_sha256':v['edited']['sha256'],'source':v['source'],'rows':[{'window':x['window'],'status':x['status'],'flags':x.get('flags'),'reliable_lag_frames':x.get('reliable_lag_frames'),'same_frame_coverage':x['same_frame']['coverage']} for x in rows]}
 final=[]
 for i,w in enumerate(results['rows'][-1]['windows']):
  lag=w['best']['lag_frames'] if w['accepted'] else None
  q={k:v['rows'][i] for k,v in labels.items()}
  final.append({'window':w['window_inclusive'],'gap5_accepted':w['accepted'],'gap5_lag_frames':lag,'independent_final_pose':q,'within_two_by_threshold':{k:abs(lag-v['reliable_lag_frames'])<=2 if lag is not None and v['reliable_lag_frames'] is not None else None for k,v in q.items()}})
 comparison={'schema':'r7-gap5-independent-final-pose-binding-v1','observer_results_sha256':sha(HERE/'RESULTS.json'),'actual_model_reference_verified':True,'final_replay_gate_path':str(gatepath),'final_replay_gate_sha256':sha(gatepath),'final_replay_input_provenance_sha256':gate['input_provenance_sha256'],'final_pose_provenance':labels,'windows':final,'early_pose_status':'unknown; root plans separate VAEdecode and criticpose, no final labels imputed','selection':'normal case selected using prior R1 outcome; not independent unseen','unsaved_callback_decisions':'not reconstructed'}
 write('POSE_COMPARISON.json',comparison)
 checks={'all_remote_file_hashes_bound':all(sha(HERE/'inputs'/f['relative'])==f['sha256'] for f in json.loads((HERE/'download_manifest.json').read_text())['files']),'actual_reference_matches_model_pair_snapshot':True,'nine_snapshots_eighteen_stream_hashes':len(results['input_checks'])==9,'full_four_windows_retained':all([w['window_inclusive'] for w in r['windows']]==p['windows_inclusive'] for r in results['rows']),'all49_curves_retained':all([v['lag_frames'] for v in w['curve']]==list(range(-24,25)) for r in results['rows'] for w in r['windows']),'all36_accepted_no_boundary_clamp':all(w['accepted'] and w['best']['clamped_frames']==0 and abs(w['best']['lag_frames'])<24 for r in results['rows'] for w in r['windows']),'first_index5_does_not_trigger':results['first_index5_would_trigger_forward6'] is False,'all_saved_main_windows_off_aligned':all(r['hypothetical_main_window_decision_class']=='OFF_ALIGNED' for r in results['rows']),'exact_final_replay_all141rgb':gate['passed'] is True,'all7_known_final_posecells_within2':sum(v is not None for row in final for v in row['within_two_by_threshold'].values())==7 and all(v is True for row in final for v in row['within_two_by_threshold'].values() if v is not None),'early_pose_unknown_preserved':all('unknown' in r['independent_early_pose'] for r in results['rows'][:-1]),'CUDA_not_initialized':results['CUDA_initialized'] is False}
 write('QA.json',{'passed':all(checks.values()),'checks':checks})
 lines=['R7 正常回放：冻结 gap5 全画面观察器检查','',
'该按先前正常成片选择的阴性对照，没有在已保存时刻触发正延后纠偏。index5（第6次模型调用）的主窗为0帧，原规则会让下一次index6（第7次调用）保持关闭；主窗后续已保存读数仅为0或−1帧。','',
'这是同一源视频/身份/种子在1024×576几何的已知正常样例，不是独立未见场景。此处运行的是原生生成加被动保存，未运行反馈控制器。','',
'输入门：实际reference latent [1,24,42,36,64] raw SHA 1cab59a56a35676b48afc317baff0cc7903ab0f606831b415ee2fe8b194e979d，与本次conditioning中native VAE输出及pair_snapshot.actual.references唯一video值一致。9份快照18个视频/音频tensor均与capture manifest raw SHA一致，13项下载文件均经远程文件SHA验证。仅下载93,512,553字节已有小tensor及metadata，无preparedRGB。','',
'方法：冻结gap5 signed cosine，全24通道×36×64空间展开；42 bins的原不等宽名义时间，跨5bin等于17物理视频帧；四窗/±24帧搜索/拒判阈值全部不变，无缩放、无移植ROI。协议在本次实际latent读数前冻结。','',
'列顺序为源视频帧窗50–65、69–81、80–92、99–111。lag单位是物理视频帧；index为去噪模型调用的零起始序号。']
 for row in results['rows']:
  name='sampler_final' if row['snapshot_kind']=='sampler_final' else f"index{row['denoising_index_zero_based']} / 第{row['model_call_one_based']}次调用"
  lines.append(name+': '+' / '.join(f"{w['best']['lag_frames']:+d}" for w in row['windows'])+'；主窗 '+row['hypothetical_main_window_decision_class'])
 lines += ['', '36/36窗口通过原拒判门，未知拒判0、搜索边界0、端点clamp0。所有49点曲线在RESULTS.json。通过这类退化/歧义门不等于已校准的统计置信度。',
'', '独立最终证据：critic核验本次相对旧R1正常视频的全部实际condition/noise、native20×50调用、141/141解码RGB与帧时基精确一致。由此可复用旧finalpose：threshold0.3为[-1,-1,0,-1]；threshold0.5为[-1,unknown,0,-1]。本观察器final为[-1,0,-1,-1]，7个已知阈值×窗口单元全部在±2帧内；unknown保留。',
'', '早期独立姿态标签当前未知。不能因为最终正常，就把index5直接标成正确或错误；后续应以root单独解码和critic姿态评估为准。本报告只证明已存native早期读数未触发ON。index11–14、16–18未存，因此不补造完整20次反馈mask，不声称整条闭环始终关闭。',
'', f"CPU单线程评估 {results['elapsed_seconds']:.3f} 秒，CUDA未初始化。未做新生成、编码、姿态估计或任何远程写入。", '', '下一步标签若到齐，只新增早期独立pose绑定文件；原PROTOCOL和RESULTS保持不改。']
 (HERE/'SUMMARY.txt').write_text('\n'.join(lines)+'\n')
 manifest={str(f.relative_to(HERE)):{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(HERE.rglob('*')) if f.is_file() and f != HERE/'manifest.json'}
 write('manifest.json',{'schema':'r7-native-gap5-observer-manifest-v1','files':manifest,'qa_passed':all(checks.values())})
 print('QA',all(checks.values()),'checks',len(checks),'manifestSHA',sha(HERE/'manifest.json'))
if __name__=='__main__':main()
