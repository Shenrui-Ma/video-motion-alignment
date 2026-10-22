from pathlib import Path
import json,subprocess
root=Path('/Users/researcher/DevProjects/h3-four-pair-evidence-review-20261015/sam07')
base=Path('/Users/researcher/DevProjects/h3-sam-real-dance-batch-20261015')
files={'source':base/'inputs/07_real_ary_v.mp4','baseline':base/'outputs/07_sam_s1_baseline_00001_.mp4','weight3':base/'outputs/07_sam_s1_weight3_00001_.mp4'}
meta={k:json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_frames,duration','-of','json',str(v)]))['streams'][0] for k,v in files.items()}
report={
 'case':'Sam07 bedside dance','fps':24,'method':'Nonblind AI inspection of decoded frames; no human annotation, no flow/pose metric, no real-time playback claim.',
 'source_paths':{k:str(v) for k,v in files.items()},'metadata':meta,
 'coverage':{'coarse_full_clip_frames':list(range(0,141,10)),'target_dense_frames':list(range(45,91,3)),'refined_contiguous_frames':list(range(58,66))+list(range(73,81)),'all_frames_decoded_but_not_all_inspected':True},
 'landmarks':[
 {'name':'Hand near mouth/face while rear leg remains bent upward','source_frames':[60,61],'baseline_frames':[75,77],'weight3_frames':[59,60],'uncertainty_frames':2,'interpretation':'Baseline has the compound action, around 15–16 frames late (~0.63 s); 3x roughly restores original timing, perhaps ~1 frame early. This is delayed action, not confirmed action omission.'},
 {'name':'Hand leaves near-mouth position upward while rear leg stays raised','source_frames':[62,63],'baseline_frames':[78,79],'weight3_frames':[61,62],'uncertainty_frames':2,'interpretation':'Adjacent transition supports same local temporal displacement; not an isolated lucky matching frame.'},
 {'name':'Rear bent leg lowering phase','source_frames':[64,69],'baseline_frames':[79,84],'weight3_frames':[63,69],'uncertainty_frames':3,'interpretation':'Coarse/dense evidence agrees that baseline leg phase is late; 3x aligns sequence more closely.'}
 ],
 'findings':[
 'Both baseline and 3x preserve the target compound action somewhere in the full clip; baseline delays it instead of eliminating it.',
 'The 3x run has substantially closer same-time pose correspondence in the manually targeted 54–69 window and the immediate release transition.',
 'This is not simply uniform slowing of every action: early0–45 coarse correspondence is much closer; target delay is local; later both outputs diverge from source leg-swing timing around120–140.',
 '3x is not perfect: near-mouth phase begins roughly1 frame early; around78–81 the following arm lift is somewhat advanced/modified relative to source; later untargeted motion errors remain.',
 'No general identity, face, hand-anatomy or overall aesthetic score was conducted. Different bodies and clothing also prevent raw pixel matching from measuring pure motion.'
 ],
 'scope_of_support':'Supports a pilot hypothesis that reference reweighting can control local event timing under a fixed paired run; does not show event omission rescue, robust success rate, causal attention bottleneck identification, general training-free method or novelty.',
 'evidence_files':['coarse_1.jpg','coarse_2.jpg','target_1.jpg','target_2.jpg','refine_58.jpg','refine_62.jpg','refine_73.jpg','refine_77.jpg']
}
(root/'motion_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
(root/'REPORT.txt').write_text('Sam07 床边舞：非盲逐帧抽样检查\n\n结论：目标动作未被整体删掉，普通版约延后15–16帧（0.63秒），3倍版把该局部动作恢复到接近参考时间。\n\n源视频嘴边手势＋后勾腿：60–61帧；普通版75–77帧；三倍版59–60帧（边界约±2帧，三倍版可能早约1帧）。接着手离开嘴边上举：源62–63，普通78–79，三倍61–62。腿放下过程也支持同一局部延后，而不是只挑了一张碰巧匹配的图。\n\n此结果更支持短时动作的时间定位/局部一致性问题，不支持“动作被删除后又找回来”的表述。三倍版在后续78–81帧手臂上举仍有轻微提前/姿态差异；约120–140帧两版均有与源不一致的踢腿时间，不能说整体完全修复。\n\n检查范围：全片0–140每10帧；45–90每3帧；58–65和73–80逐帧。所有141帧已解码但未全逐帧看完。非盲AI视觉检查，没有人工盲标或统计检验，没有真实播放检查，没有系统性画质评分。\n')
print(json.dumps(meta,ensure_ascii=False))
