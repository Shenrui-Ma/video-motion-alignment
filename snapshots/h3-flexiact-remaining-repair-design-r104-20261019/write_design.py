#!/usr/bin/env python3
"""Write source-grounded prompt proposals after actual image/contact-sheet review."""
import json
import pathlib
import shutil
from prepare_evidence import ROOT, PROJECTS, binding, sha, write

TARGETS = {
 'game_man_4': {
  'description': 'the anime man in <Picture 1>, with short parted black hair, a green cloak, a cropped brown jacket, a light shirt and cravat, dark trousers with pale crossing harness straps, dark boots, and paired hip gear',
  'identity': 'short parted black hair, the male facial structure, green cloak, cropped brown jacket, light shirt and cravat, dark trousers with pale crossing harness straps, dark boots and paired hip gear',
  'scene': 'the plain white backdrop in <Picture 1>',
  'style': 'The target video uses the anime drawing style and plain white environment of <Picture 1>.',
  'appearance_detail': 'The green cloak lies over his shoulders and brown jacket. Its folds follow his body, while the shirt, pale harness straps, boots and hip equipment keep their established appearance and attachment. His short hair and illustrated face remain recognizable as the head turns or tilts.',
  'scene_detail': 'The plain white backdrop stays visible around the figure throughout the shot, with the target image providing the scene appearance. The body is lit and drawn consistently with the illustrated reference. The framing follows the visible movement, while the target character retains the same costume and proportions as his pose changes.',
  'limits': ['斗篷和腰侧装备遮挡部分躯干；姿态测量与衣物运动应分开。', '图像画风是动漫，自动人体检测失败时需人工审核。'],
  'identity_checks': ['短黑发和动漫男性面部保持，源演员长发/脸不能成为输出主体。', '绿披肩、棕夹克、浅色衬衣/领饰、深色裤和浅色交叉绑带保持；可见时检查腰侧装备及长靴。'],
  'scene_checks': ['整段保持目标图的白背景，若转为山地、湖面或原片房间，场景要求未完成。'],
 },
 'movie_man_11': {
  'description': 'the older man in <Picture 1>, with short swept light-blond hair, a broad face, a dark navy suit, white shirt, navy tie with diagonal pale stripes, a small flag-shaped lapel pin, matching dark trousers and black lace-up shoes',
  'identity': 'the light-blond short hair, broad male face, dark navy suit, white shirt, diagonally striped tie, lapel pin, dark trousers and black shoes',
  'scene': 'the outdoor paved path in <Picture 1>, bordered by a green lawn and dark leafy shrubs, with a dark lamp post and large tree trunk on the right',
  'style': 'The target video uses the photographic appearance and outdoor daylight of <Picture 1>.',
  'appearance_detail': 'The jacket, shirt collar and diagonally striped tie move with his torso while retaining their colors and construction. His trousers and black shoes follow the leg motion. Keep the short light hair and facial features consistent during forward bends and turns; the visible head belongs to the same man as in the target image.',
  'scene_detail': 'The paved ground remains beneath the character. The lawn, dark foliage, right-side lamp post and tree trunk preserve the target image environment around the moving figure. Outdoor daylight gives the suit and surrounding scene a consistent photographic appearance. The background remains stable as the body changes pose.',
  'limits': ['深色西装与关节遮挡可能降低自动姿态可见性。', '目标图站立正面、源片低位侧面，姿态和视角变化较大；不可要求逐像素外观一致。'],
  'identity_checks': ['短浅金发、目标男性面部、深蓝西装与白衬衣保持；源女人长辫及运动服残留应单独记失败。', '能看清时检查斜条纹领带、深色裤/黑鞋，低位遮挡不作为身份错误证据。'],
  'scene_checks': ['目标图的室外铺装路面、草地和深色植被成立；固定视野允许保留右侧树干/灯柱。', '源室内板墙/粉垫或源湖面紫垫整体迁入，则目标场景未完成。'],
 },
 'movie_man_4': {
  'description': 'the bare-chested muscular man in <Picture 1>, with short swept dark-brown hair, light facial stubble and fitted dark-blue swim shorts',
  'identity': 'the short swept dark hair, stubbled male face, muscular bare torso and dark-blue swim shorts',
  'scene': 'the blue sea, level distant horizon and pale blue sky shown behind the man in <Picture 1>',
  'style': 'The target video uses the photographic coastal setting and daylight of <Picture 1>.',
  'appearance_detail': 'Keep the exposed shoulders, chest and arms consistent with the target man. His dark-blue swim shorts follow the flexion at the hips. His short swept hair and light stubble remain consistent during the side-facing movement, and the visible torso retains the proportions and skin appearance of the image.',
  'scene_detail': 'The blue water, distant horizon and pale sky from the target image remain the surrounding backdrop. Daylight on his face and exposed torso remains consistent with that image. Use the reference motion to determine the moving lower-body pose and viewing scale; the target image supplies the appearance of the portions it shows.',
  'limits': ['目标图只到大腿附近，膝以下和脚部外观没有参考真值。', '目标图海面背景未显示脚下支撑，完整下蹲需要推断下半身和支撑；不额外指定沙滩、栈桥或鞋型。', '目标图近正面、源下蹲为侧面，精细身份相似度受侧脸大小限制。'],
  'identity_checks': ['目标短发男性脸、裸露肌肉上身、深蓝泳裤稳定；灰夹克/扎发源身份残留记失败。', '仅检查目标图实际可见的身体部位；腿脚的新增细节不作精确身份判定。'],
  'scene_checks': ['蓝海、海平线和天空与目标图同类且连续，不能将湖面木栈桥整套场景继承为目标环境。', '目标图未给地面细节，生成支撑合理性单独评估，不能把某一种地面材质规定为真值。'],
 },
 'movie_man_5': {
  'description': 'the man in <Picture 1>, with short side-parted brown hair, a clean-shaven face, a charcoal-gray suit, light blue shirt, narrow dark tie, black belt and dark shoes',
  'identity': 'the short side-parted brown hair, clean-shaven male face, charcoal-gray suit, light blue shirt, narrow dark tie, black belt and dark shoes',
  'scene': 'the plain white studio background shown in <Picture 1>',
  'style': 'The target video uses the photographic studio appearance and white background of <Picture 1>.',
  'appearance_detail': 'The fitted charcoal jacket and trousers keep their appearance as the knees and hips flex. The light blue collar, narrow dark tie and black belt remain attached naturally. His head retains the short side-parted hairstyle and clean-shaven facial features in the side-facing exercise view.',
  'scene_detail': 'The white studio background remains visible around the moving man for the whole shot, with lighting consistent with the target portrait. Keep the same photographic character and costume through both repetitions. The target image defines appearance and environment, while the source clip supplies the moving pose of the hands and the body.',
  'limits': ['目标图双手插袋，动作源双手胸前；图像站姿/插袋姿态应交给动作视频替换。', '原图含 Adobe Stock 水印和边缘文字，文件原样保留；水印不计作人物身份，是否带入另记。', '此前已使用六段 P1；本次变化是明确外观、白背景及动作角色，不是首次加入格式。'],
  'identity_checks': ['目标短侧分棕发、干净下颌/脸型、炭灰西装、浅蓝衬衣、窄领带保持。', '灰运动夹克、扎发或源运动者面部残留记为身份混合。'],
  'scene_checks': ['白色摄影背景贯穿整片，湖面和木栈桥持续出现记场景失败。'],
 },
}

MOTIONS = {
 'crouch': {
  'subject': 'the complete two-repetition squat sequence performed by the person in <Video 1>',
  'source_identity': 'the source performer\'s tied-back hair, gray jacket and black exercise trousers',
  'opening': 'standing in the side-facing orientation of the first source frame, with the arms initially low',
  'action': '''He begins upright, then brings his hands forward as his hips move back and his knees bend. Continue into the first low squat following the source trajectory. His upper body inclines with the hips, and the elbows bend so the hands remain together in front of the upper chest. Follow the first low hold for the same part of the reference motion, including the small adjustments of the torso and hands visible there.
He then extends his knees and hips to rise again. As in the source, the hands remain near the chest during the upright interval. After that interval, he bends into the second squat, follows its low hold, and rises again toward the final pose of the reference clip. Keep the two repetitions and the intervening upright phase in the source order. The feet maintain the reference placement while his weight moves down and up; the body does not change its screen-facing direction between repetitions.''',
  'end': 'The final visible rise continues to the pose shown at the end of the source clip.',
  'phases': [[0,3,'站立，手臂由低位准备'],[4,10,'第一轮下降，手移至胸前'],[11,18,'第一轮低位保持'],[19,24,'第一轮上升'],[25,29,'直立间隔，手仍胸前'],[30,35,'第二轮下降'],[36,42,'第二轮低位保持'],[43,48,'第二轮上升至片尾']],
  'limits': ['源为固定侧面机位，远侧肢体部分重叠。', '两次完整下降/起立清楚，适合次序与阶段判断；手指细节较小。'],
  'checks': ['两轮下降—低位—上升，中间有直立间隔。', '第一轮起立后手仍在胸前，第二轮不能误变成新手势或第三次动作。', '膝/髋/上身协调、脚位置和侧向姿态合理。'],
 },
 'human2animal_1': {
  'subject': 'the complete sequence of low floor-supported body motions performed by the woman in <Video 1>',
  'source_identity': 'the source woman\'s face, long braided hair, lavender top and patterned trousers',
  'opening': 'in the low kneeling, arm-supported pose and side-facing orientation visible at the beginning of the source clip',
  'action': '''At the beginning he supports his upper body with the arms while the lower body remains low. Following the source sequence, he bends the elbows, brings the chest and face close to the supporting surface, and moves the upper body forward through the low phase. The hands, elbows, knees and hips follow the visible coordination and changes of contact in the reference. Maintain the low interval and its gradual transition, so the chest stays close to the ground for the corresponding part of the clip.
He then pushes through the arms, extends the elbows, lifts the chest and raises the head as the back extends. Preserve the sequence from the lowest chest position to the raised chest, with the shoulders passing through the intermediate poses seen in the source. Later, the head lowers and the back rounds while the arms continue supporting the body. Continue the remaining visible rounding through the final reference frame. The same hands and lower-body supports remain physically connected to the body throughout these changes.''',
  'end': 'The shot ends during the rounded-back, lowered-head phase shown at the end of the source.',
  'phases': [[0,4,'跪撑低位开始'],[5,12,'屈肘、胸部下降'],[13,22,'胸脸近地，低位前移'],[23,32,'伸肘并抬胸伸背'],[33,36,'高胸姿态过渡'],[37,48,'低头并拱背']],
  'limits': ['原片小腿/脚部分超出左边缘，不补造完整足部接触标注。', '最低位头发遮挡脸与部分手臂，肘部精细角度不作逐帧真值。'],
  'checks': ['屈肘胸近地先于伸肘抬胸，片尾为拱背低头。', '转折相对时间和胸/肩/头的路径可辨；不能变成片头高撑、片尾俯卧的反序列。', '低位支撑的人体结构和可见手/地接触连续。'],
 },
 'fitness': {
  'subject': 'the complete standing arm-raise and joined-hand lowering sequence performed by the woman in <Video 1>',
  'source_identity': 'the source woman\'s face, long brown hair and lavender sports outfit',
  'opening': 'upright in the three-quarter viewing direction of the source, with both arms initially low beside the torso',
  'action': '''He begins with both arms low and then raises them outward in broad arcs. Follow the source progression through shoulder height and upward into the overhead position. The shoulder rotation, elbow extension and changing wrist orientation follow the performer\'s visible motion. His torso remains upright while the arms rise, and the face keeps the viewing direction shown by the source.
As the arms reach overhead, the hands move toward one another and come together. Preserve the brief overhead phase and the transition from separated hands to joined hands. After this phase, the elbows bend outward and the joined hands descend in front of the head. Continue that descent only through the visible endpoint of the source clip, where the hands remain near the face. The hand path, the spacing between the elbows and the small head and upper-body adjustments follow the source sequence. Keep the complete order of outward raising, overhead joining and lowering, with each intermediate phase occurring at its corresponding source time.''',
  'end': 'The final pose is the joined-hand position near the face visible at the end of the reference clip.',
  'phases': [[0,2,'双臂低位开始'],[3,8,'向侧方上举至肩附近'],[9,18,'继续上举至头顶'],[19,24,'双手逐渐靠拢并合并'],[25,31,'头顶短暂保持'],[32,48,'合掌下落，片尾到脸前']],
  'limits': ['头顶双手部分贴近/超出画面上缘；只能评可见轨迹。', '官方文字写到胸前，实际片尾仍在脸前；新描述按片段终点。', '下半身未入画，原图的靴子/腰装备只有生成画面可见时才验收。'],
  'checks': ['侧举、过头、双手靠拢、合掌下降顺序保持。', '片尾到脸前，不能把“胸前”文字扩展成额外动作。', '肩肘与手臂幅度连贯，头顶出画部分单独记可见性限制。'],
 },
 'human2animal_3': {
  'subject': 'the visible low-support, tucked-leg and rising-inversion sequence performed by the man in <Video 1>',
  'source_identity': 'the source man\'s face, red sleeveless top, black shorts and white sneakers',
  'opening': 'low near the bottom of the frame in the same crouched forward-leaning position as the source performer',
  'action': '''He starts crouched low with the torso leaning forward. Follow the gradual lowering of the head and upper body toward the support region at the bottom of the source frame. His knees remain folded while his weight transfers forward. Keep this low preparation phase for the corresponding part of the motion. The hips then lift, and the feet begin to rise behind the folded knees as the torso rolls into a more inverted position.
Continue the visible progression from compact, tucked legs to progressively raised thighs and shins. The knees remain bent while the feet move upward, and later the legs extend further as shown in the remaining source frames. Preserve the ordered rise of the hips and feet and the changing leg angles through the end of the clip. The upper-body support region stays low in the frame while the legs rise. Follow the visible contacts and body structure within the source image; the hands and head close to its lower border have the same visibility limits in the requested motion.''',
  'end': 'The shot ends during the raised-leg inversion phase visible in the source, with the knees still following its final degree of extension.',
  'phases': [[0,6,'低位蹲撑准备'],[7,17,'继续前倾、头部接近下缘'],[18,24,'重心前移、低位支撑'],[25,32,'屈腿收紧、脚开始上升'],[33,40,'髋与腿继续抬高'],[41,48,'趋向倒立，膝仍保持源中弯曲程度']],
  'limits': ['手和头靠画面下缘，部分出画；无法确认每帧头/手承重分配，不命名严格手倒立或头倒立真值。', '片尾膝尚有弯曲，原 caption 的后续 push-up 不在这49帧中。', '动作极端、衣物装备遮挡，自动姿态可能UNKNOWN。'],
  'checks': ['先低位前倾再屈腿抬升，不能片头先倒立、片尾下降。', '髋/膝/脚上升阶段与源一致，末帧弯膝程度符合可见动作。', '可见肢体无多腿/断肢；边缘遮挡与不可见承重位置单独记未知。'],
 },
 'human2animal_2': {
  'subject': 'the complete cross-legged seated forward-fold sequence performed by the woman in <Video 1>',
  'source_identity': 'the source woman\'s face, tied-back hair, light blue sports top and patterned leggings',
  'opening': 'sitting upright with crossed legs in the orientation shown at the start of the source video',
  'action': '''He begins seated upright with the legs crossed and the hands resting near the knees. Follow the initial pause and the subsequent movement of both hands toward the ground in front of him. The shoulders and torso start to lean forward as the hands advance. Maintain the crossed-leg seated base throughout this progression, with the weight and upper-body orientation following the source.
The hands slide or reach progressively farther forward, the arms extend, and the chest lowers toward the crossed legs and supporting surface. Follow the gradual change from the upright torso to the low forward fold, keeping the head aligned with the source movement. After reaching the low phase, the figure remains folded with the arms extended forward for the rest of the visible clip. Keep the small final settling movement and the extended low hold. The hands remain in front of the body, the hips remain in the seated base, and the motion retains its slow continuous pace from beginning to end.''',
  'end': 'The shot ends in the low seated forward fold with both arms extended ahead, as in the final source frame.',
  'phases': [[0,5,'盘腿坐直，双手近膝'],[6,10,'双手向前移至支撑面'],[11,21,'躯干前倾、手继续前伸'],[22,32,'胸头继续下降'],[33,48,'低位前屈保持与少量下沉']],
  'limits': ['这是一轮缓慢前屈和长保持，不能作为动作密集样例。', '低头后脸不可见，身份验收需要结合开头和全程服装/头发。', '盘腿重叠遮挡，精确左右膝点不一定可靠。'],
  'checks': ['全程保持盘腿坐姿底座，不能换成俯卧撑或跪姿。', '手前移、躯干前屈、低位保持的顺序和持续关系保持。', '只根据可见头/肩/手运动判断时序，遮挡阶段不强制给精确延迟。'],
 },
}

ORDER = ['fitness__game_man_4', 'human2animal_1__movie_man_11',
         'crouch__movie_man_5', 'human2animal_2__movie_man_11',
         'crouch__movie_man_4', 'human2animal_3__game_man_4']

def prompt_for(source, target):
    t, m = TARGETS[target], MOTIONS[source]
    detail = f'''{t['style']} The character retains the target identity and clothing throughout the continuous action.
[Shot 1] The camera shows <Subject 1> {m['opening']}, within <Subject 2>. His appearance is defined by {t['identity']}. {t['appearance_detail']} The target portrait supplies his appearance while <Subject 3> supplies the changing posture.
{m['action']}
{t['scene_detail']} Preserve the reference clip's continuous view, screen-facing direction and overall framing through the action. The duration of each visible preparation, movement, pause and transition follows <Video 1>. Keep the same character recognizable across the sequence as the torso and limbs change pose. {m['end']}'''
    return f'''subject_definitions:
<Subject 1> is {t['description']}. His identity, clothing and visual style come from <Picture 1>.
<Subject 2> is {t['scene']}.
<Subject 3> is {m['subject']}. This label supplies motion only; {m['source_identity']} are replaced by <Subject 1>.
<Video 1> supplies the continuous shot structure, body orientation, motion order and physical timing for the target sequence.

summary:
[reference generation] Generate <Subject 1> performing <Subject 3> in <Subject 2>, following the complete visible motion sequence and timing of <Video 1>. The target image determines the character and environment.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - preserve {t['identity']} from <Picture 1> throughout the visible motion.
<Subject 2> (appears in [Shot 1]): fully_preserved - retain the environment and visual appearance defined by <Picture 1> throughout the shot.
<Subject 3> (appears in [Shot 1]): attribute_transfer - transfer the complete visible action to <Subject 1>, including orientation, limb coordination, visible contacts, direction, range, order and timing.
<Video 1> (continuous shot and motion timing): fully_preserved - follow the reference clip's continuous view and complete temporal progression within the motion role defined above.

detailed_description:
{detail}

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
'''

def main():
    evidence = json.loads((ROOT / 'EVIDENCE.json').read_text())
    selection_path = PROJECTS / 'h3-timing-flexiact-expanded-r66-20261018/configs/source_selection/SELECTED_8_MANIFEST.json'
    selection = json.loads(selection_path.read_text())
    r74_path = PROJECTS / 'h3-timing-flexiact-official-six-r74-20261018/design/PAIR_DEFINITIONS.json'
    r74 = json.loads(r74_path.read_text())
    reviews = {'schema': 'r104-source-only-visual-review-v1',
               'viewed_actual_images': True, 'generated_outputs_used_for_action_definition': False,
               'source_review': {}, 'target_review': {},
               'intervals_are': 'Descriptive broad phases after all49 inspection, not independently annotated event ground truth; boundary uncertainty at least one original 8fps frame (125ms). These intervals are evaluation notes only, absent from prompts.'}
    for source, info in evidence['source_review_artifacts'].items():
        reviews['source_review'][source] = {**info, 'view_status': 'all49_viewed',
          'phase_ranges_original_frames_inclusive': [
            {'frames': [a,b], 'pts_seconds': [a/8,b/8], 'description': d}
            for a,b,d in MOTIONS[source]['phases']], 'limitations': MOTIONS[source]['limits']}
    acceptance = {'schema': 'r104-basic-task-acceptance-v1', 'items': []}
    for item in evidence['items']:
        source, target, case_id = item['source_id'], item['target_id'], item['case_id']
        t, m = TARGETS[target], MOTIONS[source]
        p = ROOT / 'prompts' / f'{case_id}_P1.txt'
        p.write_text(prompt_for(source, target))
        item['candidate_prompt'] = binding(p)
        item['candidate_prompt_version'] = 'P1-explicit-reference-roles-r104-v1'
        item['candidate_status'] = 'CPU_PROPOSAL_NO_INFERENCE'
        item['scientific_change'] = 'Prompt bundle only in a future rerun; existing input bytes/seed/geometry to be retained. No new runtime or graph created here.'
        item['environment_requirement_provenance'] = {
          'official_val_caption_explicitly_requires_target_background': False,
          'official_readme_relation': 'Animate the target image; actions transferred from reference video, allowing layout/viewpoint differences.',
          'previous_actual_task': 'Every prior prompt explicitly requests preservation of the target-image scene; retained for this repair.',
          'scope': 'Existing H3 task requirement; not claimed as a verbatim official CSV instruction.' if item['official_pair_exact'] else 'Custom human crosspair task requirement; official validation for this source uses animal targets.',
          'target_scene_observed': t['scene'],
        }
        if source == 'crouch' and target == 'movie_man_4':
            prv = json.loads(pathlib.Path(item['provenance']['file']).read_text())['official_pair']
            item['official_assets'] = {'source': prv['source'], 'target': prv['target'], 'evidence': item['provenance']}
        elif target == 'movie_man_5':
            definition = next(x for x in r74['pairs'] if x['pair_key'] == case_id)
            item['official_assets'] = {'source': definition['source_asset'], 'target': definition['target_asset'], 'evidence': binding(r74_path)}
        else:
            definition = next(x for x in selection['pairs'] if x['action'] == source and x['target']['official_path'].endswith(target + '.jpg'))
            item['official_assets'] = {'source': definition['source'], 'target': definition['target'], 'evidence': binding(selection_path)}
        for k, actual in [('source', 'source_original'), ('target', 'target_image')]:
            asset = item['official_assets'][k]
            expected = asset.get('official_lfs_sha256', asset.get('lfs_sha256'))
            assert expected == item[actual]['sha256'], (case_id, k)
        conflicts = []
        if source == 'crouch':
            conflicts.append('Official target caption describes resistance-machine exercise; source crop caption and all49 actual frames show two squat repetitions. Original CSV retained; proposed prompt uses actual squat sequence.')
        if source == 'fitness':
            conflicts.append('Official target/source captions say hands lower to chest; actual clip ends with hands near face. Candidate describes only actual endpoint.')
        if source == 'human2animal_1':
            conflicts.append('Official source caption mentions multiple camera angles and furniture; current original49 shows a fixed close view with board wall and no visible chair/table. Candidate does not invent cuts or furniture.')
        if source == 'human2animal_3':
            conflicts.append('Official caption includes push-up position; actual49 ends while legs rise into inversion. Candidate preserves visible sequence and does not add a later push-up.')
        item['metadata_conflicts_retained'] = conflicts
        acceptance['items'].append({
          'case_id': case_id, 'identity': t['identity_checks'], 'scene': t['scene_checks'],
          'motion': m['checks'], 'limitations': t['limits'] + m['limits'],
          'future_review': 'Review all147 valid output frames plus the49 original action times. Decide identity/scene/action-order separately before timing. Keep failures in results. Guidance may be considered only after root accepts the basic task.',
          'timing_precision': 'Original8fps gives125ms temporal sampling; repeated24fps frames do not create finer ground-truth time.',
          'proposed_launch_rank': ORDER.index(case_id) + 1,
        })
        if target not in reviews['target_review']:
            reviews['target_review'][target] = {'image': item['target_image'], 'view_status': 'full_original_image_viewed',
              'appearance': t['description'], 'environment': t['scene'], 'limitations': t['limits']}
    write('EVIDENCE.json', evidence)
    write('SOURCE_TARGET_REVIEW.json', reviews)
    write('ACCEPTANCE.json', acceptance)
    r98 = PROJECTS / 'h3-timing-flexiact-character-repair-r98-20261019/configs/scientific_contract.json'
    r98j = json.loads(r98.read_text())
    (ROOT / 'metadata/R98_SUCCESSFUL_PROMPT.txt').write_text(r98j['cases'][0]['prompt'])
    write('PROPOSED_ORDER.json', {'case_order': ORDER, 'order_is_proposal_not_submitted_queue': True,
      'reason': [
        'fitness/game4已有身份基本成功，主要修复白背景；同目标图在R98已成功，原动作阶段清楚。',
        'human1/movie11与R98使用同一动作源，测试已有效的来源分工能否迁移至另一个完整人体目标。',
        'crouch/movie5目标完整且白背景明确；原P1已经失败，本次具体化身份和环境，不能归因于首次采用六段格式。',
        'human2/movie11的盘腿底座和前屈次序容易验收，但动作慢、后段保持，时序研究信息量有限。',
        'crouch/movie4目标下半身截断且海景缺少脚下地面，需要更多几何推断，适合作较难修复。',
        'human3/game4的极端倒置和下缘遮挡最强，宜最后；先验收动作顺序与身体结构。'],
      'registered_seed': 2026101701, 'future_geometry': {'width':1152,'height':768,'total_frames':158,'valid_frames':147,'fps':24},
      'future_generation': 'One Native per case initially; keep original assets and existing20Euler sampler recipe. No GPU package created.',
      'successful_reference_prompt': binding(ROOT / 'metadata/R98_SUCCESSFUL_PROMPT.txt'),
      'successful_reference_contract': binding(r98),
      'attribution': 'Older outputs are historical failures. Any future host/runtime change prevents attributing old-versus-new differences uniquely to prompting.'})
    print('Wrote six proposals, actual source/target review and acceptance criteria.')

if __name__ == '__main__':
    main()
