"""Build a local, evidence-linked report without changing research artifacts."""
import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def link(path, label=None):
    path = Path(path)
    return f'<a href="{quote(str(path), safe="/")}">{html.escape(label or path.name)}</a>'


def diagnostics():
    rows = []
    selections = [
        ('历史 1312×736：原始 H3', ROOT/'analysis/pose/calibration/05_sam_s1_baseline_00001_.threshold0.3.timing.json'),
        ('历史 1312×736：参考权重 ×3', ROOT/'analysis/pose/calibration/05_sam_s1_weight3_00001_.threshold0.3.timing.json'),
    ]
    names = {
        's05_seed1_native': '新 1024×576：原始 H3（正常对照）',
        's05_seed1_mass': '新 1024×576：固定总参考量，同帧路由',
        's05_full_seed1_native': '新 1312×736：原始 H3 复现',
        's05_full_seed1_native_x0': '新 1312×736：被动读出复现',
        's05_full_seed1_mass_x0': '新 1312×736：固定总参考量，同帧路由',
        's05_full_seed1_hard_x0': '新 1312×736：同帧硬掩码',
        's05_full_seed1_mass_late11_x0': '新 1312×736：仅最后 9 次调用同帧路由',
        's05_full_seed1_mass_late6_x0': '新 1312×736：从第 7 次调用开启同帧路由',
        's05_full_seed1_mass_6to14_x0': '新 1312×736：仅第 7–15 次调用同帧路由',
        's05_full_seed1_hard_late11_x0': '新 1312×736：仅最后 9 次调用同帧硬掩码',
        's05_full_seed1_offset4_x0': '新 1312×736：读取中心 +4 时间格',
        's05_full_seed1_offsetm4_x0': '新 1312×736：读取中心 −4 时间格',
        's05_full_seed1_phase_zero_x0': '新 1312×736：时间位置模块，零偏移',
        's05_full_seed1_phase_plus12_x0': '新 1312×736：参考时间位置 +12 帧',
        's05_full_seed1_phase_minus12_x0': '新 1312×736：参考时间位置 −12 帧',
        's05_full_seed1_phase_minus12_late11_x0': '新 1312×736：最后 9 次调用，时间位置 −12 帧',
        's05_full_seed1_phase_plus4_x0': '新 1312×736：参考时间位置 +4 帧',
        's05_full_seed1_phase_minus4_x0': '新 1312×736：参考时间位置 −4 帧',
    }
    for run, label in names.items():
        selections.append((label, ROOT/f'analysis/pose/pilot/{run}_00001_.threshold0.3.timing.json'))
    for label, path in selections:
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        d = next(x for x in record['diagnostics'] if x['feature'] == 'arm_direction' and x['window'] == [50, 65])
        lag = d.get('reliable_lag_frames')
        lag_text = '无法可靠判定' if lag is None else f'{lag:+d} 帧 / {lag/24:+.3f} 秒'
        error = d['same_frame']['error']
        rows.append('<tr>'+''.join(f'<td>{x}</td>' for x in [html.escape(label),lag_text,
            '未知' if error is None else f'{error:.4f}',
            f"{d['same_frame']['coverage']:.1%}",link(path,'原始测量')])+'</tr>')
    return ''.join(rows)


def transfer_section():
    rows = []
    for prefix, source, window in [('s05_full_seed2', '05，同一素材的新种子', [50, 65]),
                                    ('s07_full_seed1', '07，另一已知失败素材', [54, 69])]:
        features = [('arm_direction', '双臂方向（主指标）')] if prefix.startswith('s05') else [
            ('right_arm_direction', '右臂方向（预定主指标）'),
            ('arm_direction', '双臂方向（辅助；保留未知）')]
        for arm, method in [('native', '原始 H3'), ('mass', '全程同帧路由')]:
            run = f'{prefix}_{arm}_x0'
            for feature, feature_label in features:
                values = []
                for threshold in ('0.3', '0.5'):
                    path = ROOT/f'analysis/pose/pilot/{run}_00001_.threshold{threshold}.timing.json'
                    if not path.exists():
                        values.append('待测')
                        continue
                    data = json.loads(path.read_text())
                    d = next(x for x in data['diagnostics'] if x['feature'] == feature and x['window'] == window)
                    lag = d.get('reliable_lag_frames')
                    values.append(('未知' if lag is None else f'{lag:+d} 帧')+' · '+link(path, '记录'))
                rows.append('<tr>'+''.join(f'<td>{x}</td>' for x in
                            [html.escape(source), str(window), method, feature_label, *values])+'</tr>')
    return ('<h2>固定方法后的复核</h2><p>两条源视频是相关舞蹈，且均来自预先挑出的故障素材。'
            '新种子复现不是新场景；第二素材也不构成跨领域泛化。数值使用各自提前登记的目标窗口。</p>'
            '<div class="scroll"><table><thead><tr><th>素材</th><th>源视频帧窗</th><th>方法</th><th>测量特征</th>'
            '<th>置信阈值 0.3</th><th>置信阈值 0.5</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>')


def execution_section():
    """Keep absent, failed, and unexecuted arms visible alongside completed runs."""
    entries = [
        ('s05_seed1_native_bench2', '后端速度诊断；失败记录，不计效果样本', 'primary'),
        ('s05_seed1_native_g2_bench2', '后端速度诊断；不计效果样本', 'primary'),
        ('s05_seed1_native', '低分辨率正常对照', 'primary'),
        ('s05_seed1_mass', '低分辨率干预对照', 'primary'),
        ('s05_full_seed1_native', '历史故障重放；不是新独立种子', 'primary'),
        ('s05_full_seed1_native_x0', '被动读出零影响检查', 'primary'),
        ('s05_full_seed1_mass_x0', '全程同帧路由', 'primary'),
        ('s05_full_seed1_phase_zero_x0', '位置模块零影响检查', 'primary'),
        ('s05_full_seed1_hard_x0', '硬掩码机制对照', 'primary'),
        ('s05_full_seed1_mass_late11_x0', '固定后九次路由', 'primary'),
        ('s05_full_seed1_phase_plus12_x0', '固定正向位置扰动', 'primary'),
        ('s05_full_seed1_phase_minus12_x0', '固定反向位置扰动', 'primary'),
        ('s05_full_seed1_mass_late6_x0', '较早开启路由', 'primary'),
        ('s05_full_seed1_hard_late11_x0', '固定后九次硬掩码', 'primary'),
        ('s05_full_seed1_offset4_x0', '错时参考读取对照', 'primary'),
        ('s05_full_seed1_offsetm4_x0', '错时参考读取对照', 'primary'),
        ('s05_full_seed1_phase_minus12_late11_x0', '晚期位置扰动', 'primary'),
        ('s05_full_seed1_mass_6to14_x0', '等九次调用区间对照', 'primary'),
        ('s05_full_seed2_native_x0', '迁移环境首次尝试：路径校验在采样前失败，随后清理重试', 'transfer_attempt1'),
        ('s05_full_seed2_native_x0', '同素材第二种子；背景保持失败', 'transfer'),
        ('s05_full_seed2_mass_x0', '同素材第二种子；背景保持失败', 'transfer'),
        ('s07_full_seed1_native_x0', '第二已知素材；不是新独立种子', 'transfer'),
        ('s07_full_seed1_mass_x0', '第二素材干预', 'transfer'),
        ('s05_semantic_a0_encode_gate', '条件编码等价门；不生成视频', 'semantic'),
        ('s05_semantic_b_p6_t6', '采样内容与时间标签共同移动', 'semantic'),
        ('s05_semantic_c_p0_t6', '只移动时间标签', 'semantic'),
        ('s05_semantic_d_p6_t0', '只移动采样内容', 'semantic'),
        ('s05_semantic_runtime_native_replay_x0', '语义实验 GPU0 实际原始重放；不计独立样本', 'semantic'),
        ('s05_full_seed1_phase_plus4_x0', '备选较小位置扰动', 'not_submitted'),
        ('s05_full_seed1_phase_minus4_x0', '备选较小位置扰动', 'not_submitted'),
    ]
    roots = {'primary': ROOT, 'transfer': ROOT/'analysis/transfer_runtime_evidence',
             'semantic': ROOT/'analysis/semantic_runtime_evidence',
             'transfer_attempt1': ROOT/'audit/transfer_attempt1'}
    rows = []
    registry = []
    for run, purpose, location in entries:
        evidence = None
        if location == 'not_submitted':
            state = '未提交；不是失败实验'
        else:
            evidence = roots[location]/'logs'/f'{run}_history.json'
            if evidence.exists():
                history = json.loads(evidence.read_text())['status']
                state = '执行成功' if history.get('completed') and history.get('status_str') == 'success' else '执行失败／未成功完成'
            else:
                state = '等待完成或等待历史归档；不能据视频存在判断成功'
                evidence = None
        registry.append({'run':run,'purpose':purpose,'state':state,
                         'history':str(evidence.relative_to(ROOT)) if evidence else None})
        rows.append('<tr>'+''.join(f'<td>{x}</td>' for x in [html.escape(run), html.escape(purpose),
                    html.escape(state), link(evidence,'实际历史') if evidence else '—'])+'</tr>')
    (ROOT/'analysis/execution_inventory.json').write_text(json.dumps(registry, ensure_ascii=False, indent=2)+'\n')
    return ('<h2>全部实验的执行状态</h2><p>执行成功只说明程序完成，不等于效果成功。'
            '方法消融、零影响检查和同种子重放不能当作独立泛化样本。'
            '历史 ×3 视频仅作经过输入核验的复用对照，不计本轮新推理；后处理视频也不计新推理。'
            '周期反例未通过的 latent 读出方案停在合成测试，没有真实视频推理结果。</p>'
            '<div class="scroll"><table><thead><tr><th>运行 ID</th><th>用途／限制</th><th>状态</th><th>证据</th>'
            '</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>')


def semantic_section():
    arms = [
        ('A', 's05_full_seed1_native_x0', '0 帧', '原标签；需 A0 编码与 GPU0 实际重放核验'),
        ('B', 's05_semantic_b_p6_t6', '+6 帧', '标签移动'),
        ('C', 's05_semantic_c_p0_t6', '0 帧', '标签移动'),
        ('D', 's05_semantic_d_p6_t0', '+6 帧', '原标签'),
    ]
    rows, lags = [], {}
    for letter, run, pixels, labels in arms:
        values, measured = [], []
        for threshold in ('0.3', '0.5'):
            path = ROOT/f'analysis/pose/pilot/{run}_00001_.threshold{threshold}.timing.json'
            if not path.exists():
                values.append('待测')
                measured.append(None)
                continue
            d = next(x for x in json.loads(path.read_text())['diagnostics']
                     if x['feature'] == 'arm_direction' and x['window'] == [50, 65])
            lag = d.get('reliable_lag_frames')
            measured.append(lag)
            values.append(('未知' if lag is None else f'{lag:+d} 帧')+' · '+link(path,'测量'))
        lags[letter] = measured
        rows.append('<tr>'+''.join(f'<td>{x}</td>' for x in [letter,pixels,labels,*values])+'</tr>')
    contrasts = []
    for title, left, right in [('标签效应 C−A','C','A'),('标签效应 B−D','B','D'),
                               ('采样内容效应 D−A','D','A'),('采样内容效应 B−C','B','C')]:
        values = ['未知／待测' if a is None or b is None else f'{a-b:+d} 帧'
                  for a,b in zip(lags[left],lags[right])]
        contrasts.append('<tr>'+''.join(f'<td>{html.escape(x)}</td>' for x in [title,*values])+'</tr>')
    interaction = []
    for index in range(2):
        a, b, c, d = [lags[letter][index] for letter in 'ABCD']
        interaction.append('未知／待测' if any(v is None for v in (a,b,c,d)) else f'{b-d-c+a:+d} 帧')
    contrasts.append('<tr>'+''.join(f'<td>{html.escape(x)}</td>' for x in ['交互 B−D−C+A',*interaction])+'</tr>')
    return ('<h2>语义采样和时间标签的单独作用</h2><p>完整 141 帧 VAE 参考、噪声、文字指令和注意力算法保持不变；'
            '分别改变语义编码器看到的稀疏采样画面 P 与文本时间标签 T。'
            'P 移动 6 帧＝0.25 秒；T 在格式化前增加 0.25 秒，但实际一位小数标签由 0.2→0.5 秒等，'
            '可见数值差为 0.3 秒。因此这不是两条完全等量的物理时钟扰动。</p>'
            '<div class="scroll"><table><thead><tr><th>组</th><th>稀疏画面 P</th><th>文字时间 T</th>'
            '<th>主窗时移：阈值 0.3</th><th>阈值 0.5</th></tr></thead><tbody>'+''.join(rows)+
            '</tbody></table></div><div class="scroll"><table><thead><tr><th>差分</th><th>阈值 0.3</th>'
            '<th>阈值 0.5</th></tr></thead><tbody>'+''.join(contrasts)+'</tbody></table></div>'
            '<p>上述差分是同一已选种子的探索性对照，不是总体效应估计。条件文字会改变语义上下文；'
            '即使时间结果变化，也不能自动归因为 DiT RoPE 时钟错误或新架构。形状、覆盖率、其他窗口和编辑质量另见完整审查。</p>')


def schedule_section():
    variants = [
        ('原始 H3', 'native', '无干预', 0),
        ('同帧路由', 'mass', '第 1–20 次', 20),
        ('同帧硬掩码', 'hard', '第 1–20 次', 20),
        ('同帧路由', 'mass_late6', '第 7–20 次', 14),
        ('同帧路由', 'mass_6to14', '第 7–15 次', 9),
        ('同帧路由', 'mass_late11', '第 12–20 次', 9),
        ('同帧硬掩码', 'hard_late11', '第 12–20 次', 9),
        ('时间位置 −12 帧', 'phase_minus12', '第 1–20 次', 20),
        ('时间位置 −12 帧', 'phase_minus12_late11', '第 12–20 次', 9),
    ]
    rows = []
    for method, suffix, interval, count in variants:
        values = []
        for threshold in ('0.3','0.5'):
            path = ROOT/f'analysis/pose/pilot/s05_full_seed1_{suffix}_x0_00001_.threshold{threshold}.timing.json'
            if not path.exists():
                values.append('待测')
                continue
            d = next(x for x in json.loads(path.read_text())['diagnostics']
                     if x['feature'] == 'arm_direction' and x['window'] == [50,65])
            lag = d.get('reliable_lag_frames')
            values.append('未知' if lag is None else f'{lag:+d} 帧')
        rows.append('<tr>'+''.join(f'<td>{html.escape(str(x))}</td>' for x in [method,interval,count,*values])+'</tr>')
    return ('<h2>固定干预区间：同一故障种子的对照</h2><p>所有组仍执行 20 次模型前向；下表的“次数”只数施加改动的调用。'
            '两列是同一冻结指标在不同姿态置信阈值下的结果，不是置信区间或两次独立实验。'
            '第 7–15 次与第 12–20 次都干预九次，但 sigma 跨度不同，不能称为等剂量。'
            '正文从 1 编号；对应代码与独立审查中的 0-based 6..14／11..19，配置的 step_end 为半开上界 15／20。'
            '这些区间是固定日程；较早区间是在看到晚期失败后追加的探索性对照。</p>'
            '<div class="scroll"><table><thead><tr><th>干预</th><th>模型调用区间（从 1 编号）</th>'
            '<th>干预次数</th><th>主窗时移：阈值 0.3</th><th>阈值 0.5</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>')


def prior_art_section():
    rows = [
        ('同帧参考读取', [('Vidu S2-Editing','https://arxiv.org/html/2609.11638v1'),
                       ('Wan-Animate-2','https://arxiv.org/html/2608.06009v2')],
         '已有对应帧参考交互。移植同帧 mask 到 H3 并不自动成为新路由架构。'),
        ('参考注意力加权', [('DIAL','https://arxiv.org/html/2609.11507v1')],
         '参考 logits 偏置及局部引导有直接先例；本轮保组总量的路由也能写成归一化 logits 偏置。DIAL Phase I 是最后约 80% 的步，不是走完 80% 才开启。'),
        ('位置编码与运动控制', [('DiTFlow','https://arxiv.org/html/2412.07776v2'),
                           ('RoPECraft','https://arxiv.org/html/2505.13344v1')],
         '运动驱动的位置变量干预已有先例。仅把变量限制为参考分支的时间位移，不足以确立独立贡献。'),
        ('动态启停／中间状态反馈', [('TempoControl','https://arxiv.org/html/2510.02226v3'),
                               ('MotionEcho','https://arxiv.org/html/2506.19348v2'),
                               ('Smart-Insertion-V','https://arxiv.org/html/2605.23891v1')],
         '自适应激活、停止以及中间预测结合感知反馈都有近邻。本轮固定日程实验还不是在线控制器。'),
        ('无需生成教师的运动引导', [('FlowMotion','https://arxiv.org/html/2603.06289v1')],
         '已有基于预测端点／运动差异的推理优化。flow-matching velocity 不能直接当作图像光流。'),
        ('稀疏语义与密集 latent 坐标', [('Baton','https://arxiv.org/html/2605.25195v1')],
         '已有按压缩率映射语义 token 与密集 latent 的相对时空坐标；P/T 敏感性不自动证明坐标错误。'),
    ]
    body = []
    for topic, sources, boundary in rows:
        refs = '、'.join(f'<a href="{html.escape(url, quote=True)}">{html.escape(name)}</a>' for name,url in sources)
        body.append(f'<tr><td>{html.escape(topic)}</td><td>{refs}</td><td>{html.escape(boundary)}</td></tr>')
    return ('<h2>最直接的创新障碍</h2><p>下表摘出影响本轮判断的近邻；完整原文、代码位置、数学反例与检索限制见文献审查。'
            '本轮没有复现这些论文的全部官方方法；“×3 增权”“同帧硬掩码”等是明确命名的适配对照，不能冒充完整 DIAL 或其他方法复现。'
            '没有找到完全同名实现，也不能推出无人研究过。</p><div class="scroll"><table><thead><tr>'
            '<th>候选思路</th><th>原始来源</th><th>本轮贡献边界</th></tr></thead><tbody>'+''.join(body)+'</tbody></table></div>')


def video(path, title, caption):
    if not path.exists():
        return ''
    return (f'<article><h3>{html.escape(title)}</h3><video controls preload="metadata" '
            f'src="{quote(str(path), safe="/")}"></video><p>{html.escape(caption)}</p>'
            f'<p>{link(path,"下载横向对比视频")}</p></article>')


def x0_section():
    rows = []
    for run, label in [('s05_full_seed1_native_x0', '原始 H3'),
                       ('s05_full_seed1_mass_x0', '同帧路由')]:
        for stem, call, remaining in [('x0_step005', '6 / 20', 14), ('x0_step010', '11 / 20', 9),
                                      ('x0_step015', '16 / 20', 4), ('x0_step019', '20 / 20', 0),
                                      ('sampler_final', '最终采样结果', 0)]:
            path = ROOT/f'analysis/pose/x0/{run}/{stem}.observability.json'
            if not path.exists():
                continue
            gate = json.loads(path.read_text())['observability']['50:65']
            values = gate['direction_lags_by_threshold']
            phase = ' / '.join('未知' if x is None else f'{x:+d}' for x in values)
            status = {'phase_available_for_manual_review': '偏差可测，尚需验证可纠正',
                      'near_zero_no_intervention': '接近对齐，无需干预',
                      'unknown_or_confounded': '未知／存在混淆，不能据此干预'}[gate['status']]
            rows.append('<tr>'+''.join(f'<td>{html.escape(str(x))}</td>' for x in
                        (label, call, remaining, phase, status))+'</tr>')
    if not rows:
        return ''
    picture = ROOT/'review/x0_native/native_x0_video_frame_055.png'
    image_html = (f'<a href="{quote(str(picture),safe="/")}"><img style="width:100%" '
                  f'src="{quote(str(picture),safe="/")}" alt="视频第55帧在不同去噪预测中的原帧对照"></a>') if picture.exists() else ''
    plot = ROOT/'review/control_observation.png'
    plot_html = (f'<p><a href="{quote(str(plot),safe="/")}"><img style="width:100%" '
                 f'src="{quote(str(plot),safe="/")}" alt="固定干预起点与冻结检测规则的离散观测"></a></p>') if plot.exists() else ''
    return ('<h2>偏差在什么时候可测？</h2><p>目标仍为源视频第 50–65 帧；表中的次数是模型去噪调用次数，'
            '不是视频帧号。两个数分别对应姿态置信阈值 0.3／0.5；门控还检查方向与腕位置的一致性。</p>'
            '<div class="scroll"><table><thead><tr><th>实验</th><th>已完成模型调用</th><th>剩余调用</th>'
            '<th>方向时移（帧）</th><th>冻结规则判断</th></tr></thead><tbody>'+''.join(rows)+
            '</tbody></table></div><p>“未知”不代表动作丢失或图像模糊。首次采样通过规则的快照，不等于偏差首次出现；'
            '未保存的中间步骤没有证据。可测偏差也不证明余下步骤有能力修复。较早快照的部分左臂／身体读数已可用，因此主规则未知也不等于模型没有时间信息。</p>'+plot_html+image_html)


def build():
    status_path = ROOT/'progress.json'
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    videos = [
        ('old_calibration_s05.mp4','历史故障与三倍加权', '参考视频 / 原始编辑 / 三倍参考加权。保留原帧对应，不移动时间轴。'),
        ('s05_1024_mass_control.mp4','低分辨率正常样例', '原始编辑本身已正确完成动作。本组只能检查干预是否破坏正常样例，不能当作修复故障的证据。'),
        ('s05_full_mass.mp4','原分辨率：同帧路由', '原始 H3 与固定总参考量的同帧路由。完整原片与量化记录另行保留。'),
        ('s05_full_mass_complete.mp4','完整 5.875 秒：原始 H3 与同帧路由', '与上一条短片使用同一组素材，展示完整 141 帧，便于检查目标窗口之外的动作；不是新增推理或独立样本。'),
        ('s05_full_hard.mp4','原分辨率：硬掩码对照', '同帧路由与简单掩码的差别，需要同时检查参考注意力总量。'),
        ('s05_full_mass_late11.mp4','仅最后 9 次调用干预', '第 11 次调用的中间预测已能测出延后；此后才启动同帧路由。这是按已知观测选择的固定日程，不是在线反馈。'),
        ('s05_full_mass_late6.mp4','从第 7 次调用开始干预', '较早开启的可控性试验；选择这个起点不等于已经实现可靠在线检测。'),
        ('s05_full_mass_6to14.mp4','仅第 7–15 次调用：等调用次数对照', '与第 12–20 次调用均干预九次；真实 sigma 跨度不同。这是区间对照，不能称为等强度或完整响应曲线。'),
        ('s05_full_hard_late11.mp4','最后 9 次调用：硬掩码', '屏蔽非对应时刻的参考 key，改变参考与其他 token 的混合比例。它不等于增强参考注意力总量。'),
        ('s05_full_offset4.mp4','原分辨率：读取中心 +4 时间格', '只改变读取的参考片段。H3 的时间格宽度不等，+4 格对应约 13 或 16 视频帧；主检验是对应时刻的读取是否有优势。'),
        ('s05_full_offsetm4.mp4','原分辨率：读取中心 −4 时间格', '目标 query 窗口保持不变，移动参考 key 窗口。错时读取仅破坏姿态，也不能当作可控的动作时间平移。'),
        ('s05_phase_plus12.mp4','参考分支的时间位置 +12 帧', '只改变选中 query 对参考视频分支的时间旋转，保留该层原有参考概率总和；正号不预设生成动作一定提前。'),
        ('s05_phase_minus12.mp4','参考分支的时间位置 −12 帧', '与零偏移、+12 帧共同检验是否存在有符号的动作时刻响应；其他条件保持相同。'),
        ('s05_phase_minus12_late11.mp4','最后 9 次调用：参考时间位置 −12 帧', '在全程 −12 帧出现单向改善后选择的探索性复核。它是固定日程，不是根据本次中间结果自动触发的控制器。'),
        ('s05_phase_plus4.mp4','参考分支的时间位置 +4 帧', '预先约定的较小扰动复核。保留较大扰动结果，不按效果挑选展示。'),
        ('s05_phase_minus4.mp4','参考分支的时间位置 −4 帧', '与 +4 和零偏移共同检查有符号响应。'),
        ('s05_seed2_mass.mp4','同一素材的新种子：原始与同帧路由', '目标动作时间改善，但原始与干预结果都把大片白色背景改成黑色，均未通过背景保持要求。黑色区域来自生成视频，未裁除。'),
        ('s07_seed1_mass.mp4','第二素材：原始与同帧路由', '该素材与第一素材属于相关舞蹈，不能视作独立领域泛化。'),
        ('s05_semantic_b.mp4','语义诊断 B：同时移动画面和标签', '完整 VAE 参考不动；稀疏语义采样位置与时间标签同时改变。'),
        ('s05_semantic_c.mp4','语义诊断 C：只移动标签', '完整 VAE 参考与稀疏语义画面不动；仅时间数字标签改变。'),
        ('s05_semantic_d.mp4','语义诊断 D：只移动语义采样画面', '完整 VAE 参考与原时间标签不动；仅稀疏语义画面采样位置改变。'),
        ('s05_posthoc_retime.mp4','廉价后处理对照', '姿态对齐得到单调时间映射，直接重复或丢帧；这不是新模型推理结果，也不是独立的指标提升证据。'),
    ]
    cards = ''.join(video(ROOT/'review'/f, t, c) for f,t,c in videos)
    docs = [
        ('review/RESULTS.txt','先读：本轮结论、收益、失败与下一步边界'),
        ('review/RESEARCH_LOG.txt','完整决策日志与失败记录'),
        ('literature/framework_adaptation.txt','ScientistTwo / IdeaScientist：本轮借鉴范围'),
        ('literature/innovation_assessment.txt','创新边界与必须面对的工作'),
        ('literature/claim_review_checklist.txt','独立科学审查：哪些结论有证据、哪些不能声称'),
        ('literature/final_claim_review.txt','独立最终创新审查与停止判据'),
        ('analysis/pose/ROUND_FINAL_REVIEW.md','完整科学结果与全部未知／失败区间'),
        ('analysis/METHODS_AND_REPRODUCTION.txt','方法公式、真实调用链与复现配置'),
        ('literature/phase_controller_collision.txt','相位反馈候选的文献碰撞审查'),
        ('literature/phase_feedback_second_audit.txt','相位反馈候选：第二轮定向检索'),
        ('analysis/pose/CALIBRATION_REPORT.md','姿态测量校准、VAE 对照与不可靠区间'),
        ('analysis/x0_readout_design.txt','中间 x0 的真实调用链与数值域'),
        ('analysis/native_attention_readout_caution.json','注意力重心不能直接代表动作延迟的反例'),
        ('analysis/replication/archived_pair_reuse_audit.json','历史对照复用的严格核验'),
        ('configs/preregistered_experiments.json','实验变量、对照和预先判据'),
        ('configs/x0_capture_protocol.json','中间状态读出方案'),
        ('analysis/pose/x0/NATIVE_X0_OBSERVABILITY_REPORT.md','原始 H3 中间状态：时间偏差何时可测'),
        ('analysis/pose/x0/NATIVE_MASS_TRAJECTORY_COMPARISON.md','原始与全程同帧路由：中间动作时间轨迹'),
        ('analysis/pose/pilot/native_x0_passive_rgb_equality.json','被动记录器：141 帧输出完全相同的核验'),
        ('analysis/pose/pilot/phase_zero_rgb_equality.json','零位置偏移：最终 141 帧完全相同的核验'),
        ('analysis/native_reference_time_coordinates.txt','H3 实际时间坐标：原点间隔不等于动作延迟'),
        ('analysis/pose/pilot/FULL_MASS_1312_REVIEW.md','同帧路由：单例改善、共同有效关节对照与限制'),
        ('analysis/pose/pilot/FULL_HARD_1312_REVIEW.md','关键对照：普通同帧掩码也能修复，不能主张守恒必要'),
        ('configs/late11_mass_protocol.json','晚期干预：结果生成前登记的检验方案'),
        ('audit/late11_preintervention_tensor_equality.json','晚期开启前的两组中间张量与原始逐位相同'),
        ('analysis/pose/pilot/LATE11_REVIEW.md','最后九次调用干预未修复：量化及帧检查'),
        ('analysis/pose/pilot/LATE6_REVIEW.md','从第七次调用起干预：主窗延后降到一帧'),
        ('analysis/pose/pilot/EQUAL9_REVIEW.md','同样九次调用：较早区间改善，较晚区间未修复'),
        ('audit/early9_actual_operator_gate.json','早九次干预的实际 450 次调用核验'),
        ('audit/early9_native_prefix_tensor_equality.json','早九次开启前与原始轨迹逐位一致'),
        ('audit/early9_late6_prefix_tensor_equality.json','早九次与持续较早干预的共同前缀逐位一致'),
        ('analysis/pose/pilot/LATE_HARD_REVIEW.md','晚期开启硬掩码的对照'),
        ('audit/late6_preintervention_tensor_equality.json','较早干预开启前：中间张量逐位相同'),
        ('analysis/pose/pilot/PHASE_PLUS12_REVIEW.md','时间位置 +12：算子生效，但主窗仍延后'),
        ('analysis/pose/pilot/PHASE_PAIR_REVIEW.md','时间位置正负偏移：单向改善与控制能力限制'),
        ('analysis/pose/pilot/PHASE_LATE11_REVIEW.md','晚期位置干预：主窗仍延后十三帧'),
        ('audit/phase_minus12_late11_preintervention_tensor_equality.json','晚期位置干预开始前：视频／音频快照逐位相同'),
        ('audit/phase_minus12_late11_actual_operator_gate.json','晚期位置干预的真实 450 次层调用核验'),
        ('analysis/pose/pilot/OFFSET_PLUS4_REVIEW.md','读错参考时刻 +4 格：形状与覆盖率问题'),
        ('analysis/pose/pilot/OFFSET_MINUS4_REVIEW.md','读错参考时刻 −4 格：主要延迟仍保留'),
        ('analysis/pose/offset_specificity/summary.json','正确／错时读取：共同支持检验与完整门失败'),
        ('analysis/pose/pilot/TRANSFER05_SEED2_NATIVE_REVIEW.md','第二种子的原始延后复核'),
        ('audit/transfer_attempt1/logs/controller_state.json','迁移环境首次启动失败：采样前的路径校验错误'),
        ('audit/transfer_attempt1/processes/cleanup.json','首次失败后的进程清理记录'),
        ('analysis/pose/pilot/TRANSFER05_SEED2_PAIR_REVIEW.md','第二种子：动作时间改善，但两组背景保持均失败'),
        ('analysis/pose/pilot/TRANSFER07_PAIR_REVIEW.md','第二素材：预定右臂时序改善，保留其他区间与质量限制'),
        ('configs/mass_equal_call_budget_protocol.json','九次调用放在不同区间：新增探索性消融'),
        ('literature/semantic_sampling_hypothesis.txt','语义采样与时间标签：下一轮诊断的依据'),
        ('configs/semantic_clock_diagnostic_protocol.json','语义采样／时间标签 2×2：生成前冻结的检验规则'),
        ('analysis/pose/semantic_factorial/full_factorial_complete/REVIEW.md','完整语义四格结果：联合响应、两个一致主效应门失败'),
        ('literature/semantic_clock_implementation_review.txt','语义时钟诊断：独立科学与运行时审查'),
        ('configs/semantic_runtime_native_replay_protocol.json','同一 GPU0 进程的真实原始重放核验'),
        ('analysis/semantic_native_replay_review.txt','GPU0 原始重放配置的独立审查'),
        ('analysis/semantic_native_replay_checker_review.txt','实际重放核验程序的独立审查'),
        ('analysis/replication/semantic_gpu0_native_replay_gate.json','GPU0 与 GPU2：实际输入、轨迹和最终画面一致性核验'),
        ('literature/interim_claim_audit.txt','阶段性创新主张审查'),
        ('literature/observability_control_gap_candidates.txt','检测与可控时段：反证、候选与已有先例'),
        ('analysis/online_phase_feedback_feasibility.txt','在线反馈接入点与真实代价，尚未实装'),
        ('literature/semantic_address_prior_art.txt','稀疏语义与密集参考坐标：直接先例与创新限制'),
        ('literature/semantic_motion_conflict_audit.txt','语义／运动冲突：先例与有限因果消融的边界'),
        ('literature/semantic_phase_robustness_prior_art.txt','抽样鲁棒性：TokenFlow、NOVA 等近邻与有限检索结论'),
        ('analysis/semantic_span_identifiability.txt','Qwen 来源位置能否隔离：真实混合边界'),
        ('analysis/semantic_runtime_evidence/audit/all_four_actual_encoded_acceptance.json','四组实际条件、视觉块、噪声和布局等价／单变量核验'),
        ('analysis/residual_branch_go_nogo.txt','残差分支不推进：当前缺少支持它的损害证据'),
        ('analysis/report_export_review.txt','报告与便携导出的独立审核'),
        ('analysis/final_media_inventory.txt','全部 20 条媒体的来源、时基、caption 与格式检查'),
        ('analysis/pose/CPU_FINAL_COMPLETION.json','CPU 评估消费者全部完成、冻结指标未改变'),
        ('analysis/final_resource_release.json','最终实时进程与 GPU 释放检查'),
        ('analysis/latent_phase_probe/REPORT.txt','早期 latent 自相似读出：周期反例否证，停止后续测试'),
        ('analysis/sigma_time_semantics.txt','调用次数与真实视频／音频噪声时间'),
        ('analysis/reference_origin_hypothesis_audit.txt','时间原点对齐的直接先例与诊断边界'),
        ('literature/architecture_novelty_gate.txt','架构区别能否成立：进一步文献审查与否决条件'),
        ('literature/phase_rope_code_review.txt','参考分支时间位置干预：独立实现审查'),
        ('audit/phase_rope_gpu_smoke.json','参考分支时间位置干预：GPU 数值验证'),
        ('analysis/retiming/OLD_SAM05_REVIEW.md','后处理时间映射的重复／丢帧代价'),
    ]
    doclist = ''.join('<li>'+link(ROOT/p,title)+'</li>' for p,title in docs if (ROOT/p).exists())
    report = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 动作时间研究 · 实验记录</title>
<style>body{{background:#101215;color:#e7e9ec;font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;margin:0}}main{{max-width:1240px;margin:auto;padding:32px 24px}}h1{{font-size:30px}}h2{{margin-top:36px}}a{{color:#91c5ff}}article,.note{{background:#191d23;border:1px solid #303844;border-radius:10px;padding:20px;margin:18px 0}}video{{display:block;width:100%;background:#000}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:12px;border-bottom:1px solid #38404b;text-align:left}}.scroll{{overflow-x:auto}}.small{{font-size:13px;color:#b4beca}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}li{{margin:7px 0}}</style>
<main><h1>H3 动作时间研究：文献、实验与反例</h1>
<p class="small">完成本轮后的更新：{datetime.now().astimezone().isoformat(timespec='seconds')}。24 次正式完整推理包含重放与消融，不是 24 个独立样本；另有速度诊断和编码门。20 条横向对比已归档，推理及 CPU 评估进程已退出。</p>
<p class="small">计数口径：22 条量化指标条件，加上原 full-native 重放与 semantic GPU0 native 重放，共 24 次正式视频推理；后两条用于一致性核验，不另算指标条件。20 条展示中有一条同素材完整版，展示数量也不代表独立样本数。</p>
<div class="note"><strong>本轮结论：</strong>局部动作时间错位可以在这些样例中通过 training-free 干预明显缓解；但尚未证明新的架构贡献，也未实现自动闭环。首个故障样例延后约 13 帧，动作后来出现，因此不宜统一叫“短动作消失”。简单同帧硬掩码与保留参考总量的路由都能修复该主窗，不能把后者的守恒形式说成必要机制。</div>
<p>最有用的新对照是<strong>同样九次干预放在不同区间</strong>：第 7–15 次调用的结果为 +1/+1 帧，第 12–20 次为 +11/+12 帧。次数不足以解释差别，但 sigma 跨度和轨迹历史仍不同；没有证明精确临界时刻。三个固定晚期执行器均未充分修复，不等于一切晚期方法都无效。主检测规则在早期为未知时，部分左臂／身体信号已经可用。</p>
<p>语义输入四格结果为原始／联合移动／只改时间文字／只改采样画面 = 13／5／13／13 帧。它保留一个条件性交互线索，两个预登记的一致主效应门均失败；标签量化与完整上下文改变限制因果解释。GPU0 原始重放的五份视频／音频张量及 141 帧 RGB 与 GPU2 基线完全一致。</p>
<p>样本来自两个预选的相关舞蹈片段和同一替换身份；新种子也存在明显背景失败，第二素材存在目标前窗口代价。故本轮不估计问题发生率，不宣称跨领域泛化，也不宣称击败完整 DIAL 等方法。继续对这一个发现样例搜参数会增加选择偏差；应先独立复核机制再决定新组件。</p>
<h2>同一目标窗口的探索性测量</h2><p>源视频第 50–65 帧；正数表示编辑动作更晚。误差为归一化二维手臂方向距离，越低越好。它不是动作语义或人脸身份的完整质量指标。不同分辨率分别成组比较，不能跨分辨率归因。</p>
<div class="scroll"><table><thead><tr><th>实验</th><th>可靠局部时移</th><th>同帧手臂误差</th><th>有效覆盖率</th><th>证据</th></tr></thead><tbody>{diagnostics()}</tbody></table></div>
<p class="small">阈值 0.3；0.5 敏感性分析和完整误差曲线保存于 analysis/pose。没有可靠时移的样例保留为未知，不删除。指标不构成显著性检验。</p>
{schedule_section()}
{x0_section()}
{transfer_section()}
<p>第二素材在目标前 0–51 帧的共同有效关节误差由约 0.164 升到 0.204。目标时序改善伴随这一窗口外代价，不能只展示主窗。</p>
{semantic_section()}
<h2>可直接观看的对比</h2>{cards}
{execution_section()}
{prior_art_section()}
<h2>原始结果与方法证据</h2><ul>{doclist}</ul>
<p>{link(ROOT/'outputs','本轮原始视频目录')} · {link(ROOT/'configs','所有推理配置')} · {link(ROOT/'audit','输入、噪声与算子审计')}</p>
<details><summary>机器可读进度</summary><pre>{html.escape(json.dumps(status,ensure_ascii=False,indent=2))}</pre></details>
<p class="small">相关视频属于 AI 角色替换实验；展示不代表被替换人物真实参与该活动。当前本地页面含绝对路径，发送单独 HTML 不会自动带走素材；正式归档时需使用打包版本。</p></main></html>'''
    output = ROOT/'review/index.html'
    output.write_text(report)
    print(output)


if __name__ == '__main__':
    build()
