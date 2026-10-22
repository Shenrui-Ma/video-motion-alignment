import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
SW = Path('/Users/researcher/DevProjects/h3-short-event-switching-20261013')
FA = Path('/Users/researcher/DevProjects/h3-fast-motion-followup-20261013')
rows=[]
def row(case, name, source, a1, b1, a2, b2, note):
    rows.append(dict(case=case, landmark=name, source=source, A_s1=a1, B_s1=b1, A_s2=a2, B_s2=b2, note=note))

# Ranges are approximate inclusive frame ranges, not calibrated joint tracks.
row('05','低垂手腕侧步阶段','0–43','0–58','0–58','0–58（首0–9另有入场手势）','0–58','开始阶段被拉长，不能说从第0帧起就恒定偏移15帧。')
row('05','向外指','45–49','60–64','60–64','60–64','60–64','约晚15帧。')
row('05','所选上脸手势完整事件','50–65','65–80','65–80','65–81','65–81','动作存在；约晚15–16帧。不能将源f56与输出f56不一致直接称为整片遗漏。')
row('05','所选上脸手势核心','53–61','68–76','68–76','69–77','69–76','可确认广义手脸关系；精确V手指形态不确定。')
row('05','手臂放开/收腿','66–71','81–86','81–86','82–86','82–86','约晚15–16帧。')
row('05','双臂交叉上举','72–90','87–105','87–105','87–106','87–107','大动作也晚约15帧，所选事件不是单独延误。')
row('05','侧展/侧倾/伸腿及尾部','90–140','105–140（未到源尾部返回）','105–140（侧倾压缩，130–140出现返回/反侧）','106–140（未到源尾部返回）','107–140（未到源尾部返回）','末段不是完整等速平移，尤其B_s1侧倾幅度/时长变了。')

row('06','初始低手侧步','0–约35','0–48','低手阶段夹入20–38上脸动作','0–29，然后手指预动作30–35','0–29，然后手指预动作30–35','宽松阶段边界；B_s1额外早动作不是恢复原时间。')
row('06','首个短眼旁插入','39–44（核心41–42）','未见对应眼旁关系；53–58为胸肩旁低手动作','20–38额外提前拉长上脸；53–58仍是低手','未见对应眼旁关系；36–41胸肩旁低手','同A_s2','低手替代与源事件的关联是推断；不能将后续长V姿势当作首个短插入。')
row('06','首短插入之后的向外指','约43–50','59–63','59–63','42–46','42–46','seed1晚约半秒；seed2近原时刻。源指向与插入离开期有重叠。')
row('06','后续独立长眼旁+弯腿姿势','54–68','69–85','70–85','52–67','52–67','seed1晚15–16帧；seed2约早1–2帧，在边界误差范围内。')
row('06','后续双手上举阶段','约73–94（跨上举到展开）','90–104','90–104','74–94','74–94','源f77与seed2 f77都上举；seed1 f77仍处眼旁+弯腿。')
row('06','宽幅展开及侧倾','约95–140','108–140','108–140','95–140','95–140','源f96与seed2 f96均展开；seed1 f96仍上举。不能称两seed全部慢。')

row('07','早期侧步和前向低臂','8–35','近8–35','近8–35','近8–35','8–22近源；23–46插入长上脸','四者f12近源；B_s2 f30却额外举手到眼旁。')
row('07','目标之前双臂扫举','36–53','42–53，另重复56–67','42–53，另重复56–67','约40–53','约56–70（前面被新增手势占用）','重复/新增动作使中段时序改变，不是所有动作等比例放慢。')
row('07','所选上脸+弯腿完整事件','54–69','70–85','70–85','54–69','71–86','seed1 A/B与B_s2晚；A_s2近源。')
row('07','所选上脸核心','60–62','76–78','76–78','59–61','77–79','相对源约+16,+16,-1,+17帧；±2帧边界误差，不宣称-1精确提前。')
row('07','目标后的独立上举','约78–87','未清晰复现独立单元','94–103','近78–87（广义74–91阶段）','约96–104（广义92–106阶段）','A_s1目标释放后进入展开/倾身，不能给缺失/合并单元强行匹配帧区间。')
row('07','末尾向前伸腿','约122–130','近122–130','近122–130','近122–130','近122–130','全部f126姿态接近源；明确反证整片恒定+16帧。精确起止未重新逐帧标定。')

for idx,name in [(0,'开始交叉步/下俯'),(1,'第一段支撑转腿'),(2,'第二段支撑转腿'),(3,'低位退出'),(4,'起身'),(5,'末尾小跳和落地'),(6,'落地后站稳')]:
    d1=json.loads((FA/'analysis/04_fast_motion_s1_independent_visual.json').read_text())
    d2=json.loads((FA/'analysis/04_fast_motion_s2_independent_visual.json').read_text())
    rr=[d1['arms']['A']['phase_rows'][idx],d1['arms']['B']['phase_rows'][idx],d2['arms']['A']['phase_rows'][idx],d2['arms']['B']['phase_rows'][idx]]
    def fmt(v):
        if v is None:return '完整动作未在0–106观察到'
        if isinstance(v[0],list):return ';'.join(fmt(x) for x in v)+'（重复/延长，不是同一个周期的唯一匹配）'
        return f'{v[0]}–{v[1]}'
    row('04',name,fmt(rr[0]['source_frames_inclusive']),*[fmt(x['observed_generated_frames_approx']) for x in rr],
        '；'.join(f'{lab}: {r["occurrence"]}' for lab,r in zip(['A1','B1','A2','B2'],rr)))

notes={
 '05':'四条均有显著的多动作中段延迟：指向、上脸、放开、上举大多晚15–16帧（约0.63–0.67秒）。开头阶段被拉长；末段又受截断或压缩。因此可说这一素材有系统性节奏拖后，不能归结为每帧从头到尾恒定平移。',
 '06':'seed1中央多动作晚约15–16帧；seed2大动作近源时间，但首次短眼旁关系仍未保留。seed2直接反证“只是统一慢放造成所有不一致”。B_s1新增提前且较长的上脸动作改变次数/上下文。',
 '07':'seed1 A/B目标晚16帧，B_s2晚17帧且新增早期长手势；A_s2目标、后续上举、末尾伸腿均近源。A_s1/B_s1/B_s2末尾伸腿重新接近源时刻，中间不能用一个固定偏移或统一速度倍率解释。A_s1还缺少清楚的目标后独立上举单元。',
 '04':'A_s1/B_s2中部姿态顺序改变，但末尾小跳与落地近源；B_s1所查阶段大致近源；A_s2地板动作重复/延长、退出和起身晚约14–15帧，107帧内未出现完整末尾小跳落地。整体“全部慢”不成立。'
}
source_reports=[SW/'analysis/vae_gate/source_observations.json',SW/'analysis/generated/05_real_megumi_v_review.json',SW/'analysis/generated/06_anime_eye_insert_review.json',SW/'analysis/generated/07_real_ary_v_review.json',FA/'analysis/04_fast_motion_s1_independent_visual.json',FA/'analysis/04_fast_motion_s2_independent_visual.json']
manifest=json.loads((HERE/'render_manifest.json').read_text())
report={
 'status':'complete_readonly_landmark_audit',
 'created_at':datetime.now().astimezone().isoformat(),
 'scope':'4 original sources; 16 formal outputs; 12 switching +4 fast-motion. No benchmark outputs admitted.',
 'frame_convention':'0-based inclusive frames, source time frame/24 seconds. Approximate visual intervals; usual uncertainty ±2 frames (04 ±3); near-range/cross-phase windows are descriptive, not precise phase boundary estimates.',
 'method':'Read prior all-frame reviews, then independently decode 8 same-frame landmarks from each of 20 raw input/output MP4s (160 frames total), uniformly scale entire frame to352x198 and inspect8 sheets. Also inspect source06 frames60–119 and raw07 B_s2 existing allframe sheets48–95 for context. No display masking/cropping/time warp/interpolation used. No new inference, SSH, GPU or server operations.',
 'review_bias':'Condition-visible AI visual inspection; consulted prior reports. Independent confirmation of selected original-frame evidence, NOT an independent blind or second exhaustive all-frame annotation.',
 'all_outputs_uniformly_slow_or_late':False,
 'single_constant_offset_explains_all_outputs':False,
 'single_global_playback_rate_explains_observed_errors':False,
 'pipeline_cause_status':'Visual audit alone cannot determine model vs conditioning implementation cause. It shows errors already present in original decoded outputs, and rules out only the explanation that every mismatch is a uniform global respeed/offset. Code, FPS and timestamp audit belongs to parent/other audit lane.',
 'conclusions':notes,
 'landmarks':rows,
 'most_discriminative_evidence':[
   '07 f61 source and A_s2 show upper-face+back-bent-leg; A_s1/B_s1/B_s2 instead bilateral arm sweep. At f126 all four and source show corresponding forward-leg extension.',
   '06 f61 and f77: source and seed2 show respectively long eye pose and overhead; seed1 remains in preceding phases. Same source, same-length outputs, differing temporal behavior.',
   '04 f48 source forward-lean support but A_s1/A_s2/B_s2 chest-up split; f60 relation reverses. At f96 A_s1/B_s1/B_s2 return to source airborne closing hop; A_s2 still low exit.',
   '05 f56 source hand near eye but all outputs low wrists; f72 outputs finally show hand-eye pose while source is already lowering/repositioning. Multiple adjacent phase landmarks follow+15–16 frames.'
 ],
 'new_raw_evidence':manifest,
 'consulted_reports':[{ 'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in source_reports],
 'limits':['No calibrated pose tracking, optical-flow fit or timing significance test.','No motion speed scalar estimated from repeated similar poses; no unstable pixel-correlation/DTW alignment.','Different actions were not counted as matching just because the hand was high. Unmatched and altered-order events explicitly labeled.','No mechanism, universal failure rate or new scientific contribution established.']
}
(OUT/'landmark_audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
with (HERE/'landmark_table.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
lines=['原始视频动作时间线复核（2026-10-13）','', '结论：部分案例确实出现明显延迟，但16条输出不支持全部统一变慢、统一帧率错误或单一固定偏移。', '', '方法：原档只读；直接从4源视频及16正式输出各抽8个同帧地标（共160原始帧），检查8张五列全画面证据。查阅此前全帧报告，并对06源f60–119、07 B_s2 f48–95补看既有原档全帧图。没有使用展示遮黑/裁切版。不是新盲评，也没有重新独立逐帧标定全部视频。','']
for case,note in notes.items():lines += [case+': '+note,'']
lines+=['帧号均从0开始；物理时刻=帧号/24秒。区间含首尾；通常±2帧、街舞±3帧；“近”区间只表示大动作时段，不能据此宣称1帧级差异。','', '| case | 动作 | source | A_s1 | B_s1 | A_s2 | B_s2 | 说明 |','|---|---|---|---|---|---|---|---|']
for r in rows:lines.append('| '+' | '.join(str(r[k]) for k in r)+' |')
lines+=['','因果边界：当前只能确认不一致存在于原始生成文件，不是后加黑边/拼图造成。不能凭视觉复核就断言ComfyUI任何节点绝无错误，也不能反过来认定模型错误；时间戳、FPS、token坐标和推理图需与另一审计结果合并。','', '最清楚反例图：',str(HERE/'07_real_ary_v_raw_landmarks_p1.jpg'),str(HERE/'07_real_ary_v_raw_landmarks_p2.jpg'),str(HERE/'06_anime_eye_insert_raw_landmarks_p2.jpg'),str(HERE/'04_fast_motion_raw_landmarks_p2.jpg')]
(OUT/'landmark_audit.txt').write_text('\n'.join(lines)+'\n')
assert len(rows)>=4*4
assert len(manifest['inputs'])==20
assert all(Path(x['path']).is_file() for x in manifest['pages'])
print(json.dumps({'report':str(OUT/'landmark_audit.json'),'landmark_rows':len(rows),'raw_inputs':len(manifest['inputs']),'evidence_pages':len(manifest['pages'])}))
