"""Offline research report built from frozen experiment evidence and local media."""
from pathlib import Path
from html import escape
import base64, hashlib, json, math, re, subprocess, shutil

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT.parent
OUT = Path('/Users/researcher/Downloads/H3_动作时序研究_研究进展_单文件_20261020.html')
BINDINGS = {}

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def bind(p, digest=None):
    p = Path(p); actual = sha(p)
    assert digest is None or actual == digest, str(p)
    BINDINGS[str(p)] = actual
    return p

def read(p):
    return json.loads(bind(p).read_text())

def uri(p, mime, digest=None):
    p = bind(p, digest)
    return f'data:{mime};base64,' + base64.b64encode(p.read_bytes()).decode()

def tx(x,y,s,size=20,color='#243448',anchor='start',weight='400'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{escape(s)}</text>'

def box(x,y,w,h,title,sub='',fill='#edf2f7',stroke='#c8d2dd',size=20):
    a=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}"/>'
    a+=tx(x+w/2,y+(h/2+7 if not sub else 28),title,size,anchor='middle',weight='600')
    if sub:a+=tx(x+w/2,y+53,sub,16,anchor='middle',color='#526277')
    return a

def arrow(x1,y1,x2,y2,color='#64748b',dash=False):
    return f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{color}" stroke-width="2" fill="none" marker-end="url(#arr)"'+(' stroke-dasharray="6 5"' if dash else '')+'/>'

def svg(w,h,content,label):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}" style="font-family:Arial, PingFang SC, Microsoft YaHei, sans-serif"><defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8" fill="#64748b"/></marker></defs><rect width="100%" height="100%" fill="white"/>{content}</svg>'

def architecture():
    a=tx(24,30,'H3 Ref2VA · 单次去噪前向',24,weight='600')
    a+=box(24,60,242,76,'编辑文本','Text encoder → Token Refiner')
    a+=box(24,158,242,76,'参考视频 / 参考图','VAE → latent → patch tokens')
    a+=box(24,256,242,76,'待生成视频 / 音频','当前噪声 latent → tokens')
    for y in [98,196,294]:a+=arrow(266,y,312,y)
    a+='<path d="M312,98 L312,294" stroke="#64748b" stroke-width="2"/>'+arrow(312,196,348,196)
    a+=box(348,145,246,102,'拼接多模态序列','带模态与时空位置坐标')
    a+=tx(471,221,'text · refs · audio · video',16,anchor='middle')
    a+=arrow(594,196,642,196)
    a+=box(642,74,500,250,'',fill='#f8fafc',size=23)+tx(892,108,'50 个 DiT Block',23,anchor='middle',weight='600')
    a+=box(666,125,170,73,'Q / K / V','QK RMSNorm + RoPE',size=18)
    a+=arrow(836,160,860,160)
    a+=box(860,125,258,73,'Self-attention → O','重分配参考视频的时间权重',fill='#e4f4ee',stroke='#459c81',size=19)
    a+=arrow(989,198,989,233)
    a+=box(666,233,452,65,'输出投影 → 残差 → SwiGLU FFN',size=19)
    a+=arrow(890,324,890,374)
    a+=box(642,374,500,74,'预测 flow velocity → sampler 更新 latent','反复去噪；最后经 VAE decoder 得到视频')
    a+=tx(24,392,'干预接口',21,color='#17765b',weight='600')
    a+=tx(24,424,'Attention 加权求和之后，输出投影之前。',20)
    a+=tx(24,455,'每次改变的信号继续经过后续 DiT Block。',19)
    return svg(1180,490,a,'H3完整推理路径及Attention干预位置')

def operator():
    a=tx(24,29,'同一个输出 query，重新分配参考视频的 Attention 时间权重',23,weight='600')
    a+=box(24,60,254,74,'输出 query：时间 bin τ','联合多模态 self-attention',size=19)
    a+=arrow(278,97,327,97)
    a+=box(327,60,245,74,'加权 Value z','参考视频所有时间的 K / V',fill='#fff4e6',stroke='#d9ab68')
    a+=box(327,157,245,74,'加权 Value zτ','仅时间 bin τ 的参考 K / V',fill='#e4f4ee',stroke='#459c81')
    a+='<path d="M300,97 L300,194 L327,194" fill="none" stroke="#64748b" stroke-width="2" marker-end="url(#arr)"/>'
    a+=arrow(572,97,630,145)+arrow(572,194,630,169)
    a+=box(630,112,230,92,'计算替换量','α × m × (zτ − z)',fill='#e4f4ee',stroke='#459c81')
    a+=arrow(860,158,908,158)
    a+=box(908,112,244,92,'加入原输出 O','得到 O′，再做输出投影')
    a+=tx(24,286,'参考权重总和 m 保持；参考时间概率分布改变',20,weight='600')
    for i,(label,refcolors) in enumerate([('普通编辑',['#b8cde0','#7299c4','#91b5d4','#5d83b0','#afc5dd']),('时序引导',['#e7edf2','#e7edf2','#269777','#e7edf2','#e7edf2'])]):
        y=314+i*76;a+=tx(24,y+27,label,20)
        a+=box(156,y,240,43,'其他 tokens：加权项保留',size=17)
        for j,c in enumerate(refcolors):
            a+=f'<rect x="{424+j*132}" y="{y}" width="124" height="43" fill="{c}" rx="5"/>'
            a+=tx(486+j*132,y+27,f'参考 t{j+1}'+(' = τ' if j==2 else ''),17,anchor='middle')
    a+=tx(24,474,'图示 α = 1；同一时间 bin 内的空间对应由 QK 相似度分配。',18,color='#526277')
    return svg(1180,508,a,'Attention读出替换及参考总权重保持示意')

def timelines():
    a=tx(24,30,'视频时间与去噪进度是两条独立坐标轴',24,weight='600')
    a+=tx(24,75,'视频时间',21,weight='600')+tx(24,105,'第 f 帧：动作何时发生',18)
    x=280; scale=30
    spans=[1,4,4,4,4,1,4,4]
    for i,n in enumerate(spans):
        w=n*scale;a+=f'<rect x="{x}" y="58" width="{w-3}" height="50" fill="{["#dce8f3","#c1d9e8"][i%2]}" rx="4"/>'
        a+=tx(x+(w-3)/2,89,str(n)+'帧',15,anchor='middle');x+=w
    a+=tx(280,139,'position bin：当前实现的时间坐标分组，跨度按 1、4、4、4、4 重复。',18)
    a+=tx(280,169,'视频 latent 是 T′ × H′ × W′ 网格；每个时间 bin 内再展开空间 patch。',18)
    a+=tx(24,228,'去噪进度',21,weight='600')+tx(24,258,'第 k 步：何时施加引导',18)
    for i in range(20):
        x=280+i*41;a+=f'<rect x="{x}" y="211" width="36" height="43" rx="3" fill="{"#229777" if 6<=i<15 else "#e5eaf0"}"/>'
        a+=tx(x+18,239,str(i+1),15,anchor='middle',color='white' if 6<=i<15 else '#455367')
    a+=tx(280,292,'当前固定实验：20 步中的第 7–15 步，在全部有效视频时间上引导。',19)
    a+=tx(280,322,'自动原型：每一步重新估计偏移，决定本步引导哪些视频时间窗口。',19)
    return svg(1180,350,a,'位置bin、视频物理时间与去噪步骤区别')

def controller():
    a=tx(24,30,'自动原型：每一步观察预测成片，再决定本步是否引导',23,weight='600')
    data=[(24,'当前 noisy latent','k = 0 … 19'),(258,'普通 H3 预测','预测 clean latent → 解码'),(492,'测量可见动作','参考 / 生成：关节方向'),(726,'扫描时间窗口','16 / 32 帧 · stride 4')]
    for x,t,s in data:a+=box(x,64,214,80,t,s,size=19)
    for x in [238,472,706]:a+=arrow(x,105,x+20,105)
    a+=arrow(940,105,1085,105)+arrow(1085,105,1085,218)
    a+=box(788,218,354,87,'判断偏移证据是否持续','误差相对下降 > 50%，连续两步',fill='#e4f4ee',stroke='#459c81')
    a+=arrow(788,261,740,261)
    a+=box(448,218,292,87,'通过 → 重新做 guided 预测','从本步同一 noisy latent 开始')
    a+=arrow(448,261,402,261)
    a+=box(24,218,378,87,'使用选定预测更新一次 latent','未通过 / UNKNOWN → 使用普通预测')
    a+='<path d="M94,218 L94,173 L100,144" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5 5" marker-end="url(#arr)"/>'
    a+=tx(24,354,'停止：下一步重新判断，条件不再满足就停止该步引导；后续再次满足可重新开启。',20)
    a+=tx(24,391,'验证状态：早期两条已实际启停；后续五条未触发。可见手臂测量版本待 GPU 验证。',18,color='#985b23')
    return svg(1180,425,a,'自动观察和决策实际流程及当前验证状态')

def transport():
    a=tx(24,30,'参考视频 latent patch 的 Value 特征对应',23,weight='600')
    for x,label in [(35,'参考视频 bin t − 1'),(415,'参考视频 bin t'),(795,'参考视频 bin t + 1')]:
        a+=box(x,61,320,150,'',fill='#f7f9fc')+tx(x+160,94,label,20,anchor='middle',weight='600')
        for i in range(4):
            a+=f'<rect x="{x+35+i*62}" y="121" width="46" height="46" rx="5" fill="{["#cfdae5","#81baa7","#b6cddd","#cfdae5"][i]}"/>'
    a+=arrow(187,150,569,150,color='#229777')+arrow(948,150,569,150,color='#229777')
    a+=tx(592,246,'输出 query 位于 t：相邻参考 Value 向 t 移动一格',21,anchor='middle')
    a+=tx(24,289,'固定空间位置：沿时间移动时保持 patch 索引。',19)
    a+=tx(24,325,'特征匹配位置：根据相邻帧互为最近邻的 Value 特征，选择接收 patch。',19)
    a+=tx(24,361,'匹配不可靠的位置保持原 Value；本次比较中，两种方案共用接受位置。',19)
    return svg(1180,390,a,'相邻时间Value输运及匹配空间位置示意')

def attention():
    d=read(PROJECTS/'h3-paper-progress-20261017/revision_20261019/attention_readouts_completed.json')
    p=d['panels'][0]; raw=p['raw']; rows=raw['query_records'];cols=raw['reference_temporal_bins']
    a=tx(24,30,'参考视频 Attention：实测时间概率与算子作用',24,weight='600')
    for offset,title,derived in [(90,'实测：普通 QK 的参考时间分布',False),(660,'公式演示：同一输入应用 α = 1',True)]:
        a+=tx(offset,76,title,20,weight='600')
        for i,r in enumerate(rows):
            for j,v in enumerate(r['p_ref_frame']):
                if derived:v=1.0 if j==r['query_latent_bin'] else 0.0
                z=math.log1p(99*min(1,max(0,v)))/math.log(100)
                rgb=tuple(round(248+(b-248)*z) for b in (21,104,89))
                a+=f'<rect x="{offset+j*8.6:.1f}" y="{102+i*8.6:.1f}" width="8.8" height="8.8" fill="rgb{rgb}"/>'
        a+=tx(offset,493,'0',16)+tx(offset+390,493,str(cols-1),16)
        a+=tx(offset+204,522,'参考视频时间 bin →',18,anchor='middle')
        a+=tx(offset-9,116,'0',16,anchor='end')+tx(offset-9,470,str(rows[-1]['query_latent_bin']),16,anchor='end')
    a+=tx(24,560,'纵轴：输出时间 bin。左图取第 26 个 Block、第 6 次前向，8 个 head × 8 个中心邻域位置。',18)
    a+=tx(24,592,'右图由同输入替换公式计算，表示条件权重。两图采用相同的对数色阶，显示 0–1 概率。',18)
    for i in range(100):
        z=i/99;rgb=tuple(round(248+(b-248)*z) for b in (21,104,89));a+=f'<rect x="{420+i*3}" y="620" width="3.2" height="14" fill="rgb{rgb}"/>'
    a+=tx(410,634,'0',14,anchor='end')+tx(732,634,'1',14)
    return svg(1180,654,a,'实际时间Attention与同输入算子演示热力图')


def auto_history(history):
    a=tx(24,30,'自动干预：已完成实验的实际采样步记录',24,weight='600')
    for row,(key,label,result) in enumerate([('R27_bad','开发视频 A','姿态时差：+13 → +2 帧'),('R35_bedside','开发视频 B','姿态时差：+15 → −1 帧')]):
        y=90+row*95; run=history['runs'][key];active=set(run['ON_indices'])
        a+=tx(24,y+27,label,21,weight='600')
        for i in range(20):
            x=202+i*35
            a+=f'<rect x="{x}" y="{y}" width="30" height="39" rx="3" fill="{"#229777" if i in active else "#e5eaf0"}"/>'
            a+=tx(x+15,y+25,str(i+1),14,anchor='middle',color='white' if i in active else '#455367')
        a+=tx(925,y+26,result,17)
    a+=tx(202,60,'采样步（1–20）',18)
    a+=tx(24,279,'A：第 6 步因姿态覆盖不足停止。B：第 12 步因两种置信度下的时差估计冲突停止。',19)
    a+=tx(24,315,'灰色：普通预测更新。绿色：从同一 noisy latent 增加 guided 预测，再更新一次。',18,color='#526277')
    return svg(1180,346,a,'两条实际自动实验的20步启停时间线')

def evidence_tree(obj):
    if isinstance(obj,dict):
        if 'sha256' in obj and ('file' in obj or 'path' in obj):
            file=obj.get('file',obj.get('path'))
            if isinstance(file,str) and file.startswith('/'):bind(file,obj['sha256'])
        else:
            for v in obj.values():evidence_tree(v)
    elif isinstance(obj,list):
        for v in obj:evidence_tree(v)

def main():
    bind(PROJECTS/'h3-timing-architecture-r2-20261016/audit/reference_mass_control_prior_art_20261020/REVIEW.json','98a7056d9d2eeb590b54955c3bc183d4f8e2588af78cb7c054435d3898a34f7a')
    bind(PROJECTS/'h3-timing-architecture-r2-20261016/audit/reference_mass_control_prior_art_20261020/REFDROP_NOTE.json','7a3479ef9e4f5abf3a091dbc65495232d13ca2b5c17e2666d61a326b06fc4468')
    bind(PROJECTS/'h3-ive-handkerchief-full-context-metrics-r126-20261020/audit/visible_arm_feasibility_20261020/REVIEW.json','b53c4979e455505e3ce27037cb448bbf48e3a0c1977c9c24e6e82fc6ba0614ee')
    bind(PROJECTS/'h3-pose-content-boundary-review-20261020/R126_REPLAY_RESULT.json','0c484e5da6d80a5284bfbe3d64e09509758dfd8bbed6d8aa77cb759d76ae0e37')
    bind(PROJECTS/'h3-oxygen-online-metrics-r133-20261020/audit/on_window_content_coverage/RESULT.json','b0f9609c401ea0e0cf3dfba1525fc0c324c3a7936412fa066392db4be9f246ad')
    protocol=read(bind(PROJECTS/'h3-benchmark-all-results-showcase-20261018/audit/progress_protocol_snapshot_20261020_v12.json','dc8517c97d7667dedbd8ac508df0da343f3abdacb2b694c29409fb4085bc7213'))
    current=read(bind(PROJECTS/'h3-benchmark-all-results-showcase-20261018/audit/progress_protocol_snapshot_20261020_v14.json','97755aec6952b65608a11fdee28e66e3683eea127ab729c2d8a2c56bf5b14990'))
    protocol['totals']=current['totals']
    for benchmark,task_key in [('FlexiAct','unique_source_reference_image_pairs'),('IVEBench','unique_official_edit_tasks')]:
        for key in ['independent_source_videos','result_versions']:
            protocol['counts'][benchmark][key]=current['counts'][benchmark][key]
        protocol['counts'][benchmark][task_key]=current['counts'][benchmark]['unique_task_combinations']
    protocol['latest_archive_snapshot']=current
    audit=protocol['latest_task_pair_audit'];bind(audit['path'],audit['sha256'])
    materials=read(PROJECTS/'h3-oxygen-seed-replication-metrics-r113-host41-20261019/audit/paper_materials_20261020/MATERIALS.json')
    provenance=read(PROJECTS/'h3-oxygen-seed-replication-metrics-r113-host41-20261019/audit/paper_materials_20261020/PROMPT_AND_METRIC_PROVENANCE.json')
    for impl in provenance['metric_implementations'].values():
        for key in ('code','function_binding','vendor'):
            if key in impl:evidence_tree(impl[key])
    history=read(PROJECTS/'h3-timing-architecture-r2-20261016/audit/automatic_history_actual_20261020/EVIDENCE.json')
    evidence_tree(history['implementation_identical_R27_R35'])
    for run in history['runs'].values():evidence_tree(run['evidence'])
    auto=read(PROJECTS/'h3-timing-architecture-r2-20261016/audit/automatic_controller_actual_code_20261020/EVIDENCE.json')
    for file,h in auto['files'].items():bind(file,h)
    for e in auto['R55_actual']:bind(e['file'],e['sha256'])
    (ROOT/'evidence/protocol_snapshot.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
    (ROOT/'evidence/materials.json').write_text(json.dumps(materials,ensure_ascii=False,indent=2))
    (ROOT/'evidence/prompt_metric_provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2))
    (ROOT/'evidence/automatic_history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2))
    text=(ROOT/'template.html').read_text()
    assert protocol['totals']['result_versions']==112
    counts=protocol['counts']
    rows=[]
    for name,task_key,pair_key in [('FlexiAct','unique_source_reference_image_pairs','actual_guidance_unique_tasks'),('IVEBench','unique_official_edit_tasks','actual_guidance_unique_sources')]:
        c=counts[name]
        rows.append(f'<tr><td>{name}</td><td>{c["independent_source_videos"]}</td><td>{c[task_key]}</td><td>{c["result_versions"]}</td><td>{c[pair_key]}</td></tr>')
    scale='<table><thead><tr><th>数据</th><th>独立源视频</th><th>任务组合</th><th>归档版本</th><th>已有实际干预配对的任务</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
    scale+='<p class="note">当前归档：112 版本、50 条独立源视频、59 个任务组合。同源不同种子计作复测。FlexiAct 的 11 个组合来自官方 CSV，6 个为公开素材重组。下列配对统计针对固定区间引导；新增的 1 次自动干预实验在 3.5 节单独报告。</p>'
    scale+='<p>按每个任务的最新实际配对归档，IVEBench 有 25 个配对完成目标编辑并保留原场景：3 个来源出现局部时序改善，16 个未观察到清楚变化；其余 6 个中，2 个遗漏动作未恢复，另 4 个分别为第二次动作进一步提前、结构变体表现不同、动作时刻难以判定、减少额外动作。另有 2 个配对部分完成编辑、2 个编辑失败。FlexiAct 的 13 个配对中，1 个完整达成任务，6 个部分达成、3 个失败、3 个验收待明确。</p>'
    assert protocol['latest_task_pair_summary']['ivebench']['strict_task_pass_pair_timing']['IMPROVED']==3
    text=text.replace('@@STUDY_COUNTS@@',scale)
    latest=read(bind(PROJECTS/'h3-ive-new-source-mf-host41-20261020/audit/RESULTS_VERIFIED.json','c325e4e7f53ab85a00d6befc8eb15546e273672fcfa79fdd0b63ef7efe460879'))
    for result in latest['results']:bind(result['result_file'],result['result_sha256'])
    new_scores={(r['case'],r['role']):r['score'] for r in latest['results']}
    text=text.replace('@@RECENT_RESULTS@@',f'<p><b>新素材检查。</b>公园人物替换完成，但普通版与引导版都遗漏撑地、后仰动作，MF 为 {new_scores["long_0161","native"]:.6f} → {new_scores["long_0161","guided"]:.6f}。砧板改色的普通版动作已同步（MF {new_scores["long_0031","native"]:.6f}），因此跳过引导。西装改色重构了姿态和机位（MF {new_scores["long_0163","native"]:.6f}），进入基础编辑失败记录。这三条新来源均保留成片和评分。</p>')
    followup=read(PROJECTS/'h3-ive-followup-mf-host41-20261020/audit/RESULTS_VERIFIED.json')
    for result in followup['results']:bind(result['result_file'],result['result_sha256'])
    scores_next={(r['case'],r['role']):r['score'] for r in followup['results']}
    bind(PROJECTS/'h3-ive-prompt-envelope-metrics-r123-20261020/variants/long0034_full_context/audit/full_frame_review/long_0034/paired/INDEPENDENT_REVIEW.json','1f2a2db0d57cb27b1ca194f780b79e0d48a900ebe4cf37f9aa22f688cea026d5')
    bind(PROJECTS/'h3-ive-book-color-metrics-r128-20261020/audit/full_frame_review/short_0362/native/REVIEW.json','e96fa81ccf898cb6c1a1a7f4edf3a339adcc0055dde6829d2923e7d189b71bec')
    extra=f'<p>新增砧板的配对均完成编辑：第一次撤刀仍晚约 4 帧，第二次从提前约 8 帧变为提前约 10 帧；MF 却从 {scores_next["long_0034","native"]:.6f} 升至 {scores_next["long_0034","guided"]:.6f}。因此这条结果归为时序未改善。另一条书封改红色的普通编辑已经同步，MF 为 {scores_next["short_0362","native"]:.6f}，跳过引导。</p>'
    text=text.replace('<h3>3.3　时序干预效果</h3>',extra+'<h3>3.3　时序干预效果</h3>')
    bind(PROJECTS/'h3-timing-ive-aligned-media-clock-r129-20261020/audit/ROOT_PRELAUNCH_REVIEW.json','bb19495a39a3ba12bb4da46232958ca33e943e7c201f8d4c9bf5bfb2209876a5')
    bind(PROJECTS/'h3-timing-ive-aligned-media-clock-r129-20261020/design/R129_EVALUATION_PLAN.json','22581953992b8970db78a712924bde889f68d51ce1e3fb8395b58d20cd4c8a89')
    bind(PROJECTS/'h3-timing-architecture-r2-20261016/audit/aligned_rope_existing_check_20261020/videocof_followup/REVIEW.json','359e32c44961aaa682b1f00a3ec608a2c84956bcaeadb2243afe4b14d21ca71b')
    text=text.replace('@@ALIGNED_ROPE@@',bind(ROOT/'assets/aligned_rope.svg').read_text())
    aligned=PROJECTS/'h3-ive-aligned-media-clock-metrics-r129-20261020'
    aligned_review=read(bind(aligned/'audit/full106_review/REVIEW.json','dfa984974a43f7b5dac4d1e42930963dadd2cf2c99cd52a41eac300508b051b8'))
    assert aligned_review['all_valid_frames_inspected'] and len(aligned_review['examined_frames'])==106
    assert aligned_review['task_acceptance']['aligned']['status']=='TASK_FAIL_COPY_SOURCE'
    evidence_tree(aligned_review['evidence'])
    aligned_presentation=read(aligned/'showcase/source_native_aligned/PRESENTATION.json')
    for item in aligned_presentation['inputs']:evidence_tree(item)
    aligned_picture=uri(ROOT/'assets/r129_frame081.png','image/png')
    aligned_video=aligned_presentation['videos'][0]
    newest_mf=read(bind(PROJECTS/'h3-ive-bird-aligned-mf-host41-20261020/audit/RESULTS_VERIFIED.json','8e3856e6a05300cd84fe21dc386a7ece955b684eb0547b9525ec37b5261b470f'))
    for result in newest_mf['results']:bind(result['result_file'],result['result_sha256'])
    newest_scores={(r['case'],r['role']):r['score'] for r in newest_mf['results']}
    aligned_panel='<article class="result" id="positional-control"><div class="resulthead"><h3>结构对照：整体 RoPE 对齐与编辑完成度</h3><span>IVEBench · long_0039</span></div>'
    aligned_panel+='<div class="inputnote"><p><b>方法：</b>第 2.5 节整体时间坐标对齐，作用于全部去噪步。</p><p><b>输入：</b>与第 3 组相同的参考视频、提示词和实际初始噪声；角色参考图：无。</p><p><b>编辑指令：</b>Adjust the color of book to blue</p></div>'
    aligned_panel+=f'<figure><img loading="lazy" src="{aligned_picture}" alt="参考、普通编辑和整体RoPE对齐的第81帧"><figcaption class="imagecaption">第 81 帧，3.375 秒。整体对齐版已抬起书本，书封仍为原来的橙棕色；普通编辑完成蓝色修改，抬书动作延后。</figcaption></figure>'
    aligned_panel+=f'<video controls playsinline preload="none" poster="{aligned_picture}" src="{uri(aligned/"showcase/source_native_aligned"/aligned_video["file"],"video/mp4",aligned_video["sha256"])}"></video>'
    aligned_panel+='<div class="controls"><button type="button" data-rate="1">1×</button><button type="button" data-rate="0.5">0.5×</button><button type="button" data-restart>从头播放</button></div>'
    aligned_panel+='<div class="imagecaption">五个动作和四段相邻动作间隔均接近参考，蓝色书封编辑失败。该配置过度保留了源视频内容；下方控制将相位对齐限制在辅助参考分支，并保留原参考概率总和。'
    aligned_panel+=f'<p><b>IVEBench MF：</b>普通编辑 0.877733，整体 RoPE 对齐 {newest_scores["long_0039","aligned"]:.6f}。轨迹分数随动作接近参考而上升，编辑完成度为失败。这项结果说明编辑验收与 MF 需要分别报告。</p></div></article>'
    text=text.replace('@@POSITIONAL_CONTROL_RESULT@@',aligned_panel)
    origin=PROJECTS/'h3-timing-ive-reference-origin-r132-20261020'
    origin_review=read(bind(origin/'audit/ROOT_PRELAUNCH_REVIEW.json','71e0cf595671c0298f908e0fd3d87354f247a43db7df18f2335772ea3dc30e48'))
    bind(origin/'deploy_manifest.json',origin_review['producer_seal_sha256'])
    assert origin_review['approved'] and origin_review['tests']['passed']==23
    text=text.replace('@@REFERENCE_BRANCH_STATUS@@','成片中蓝色书封编辑成功，五个动作的时刻均与普通编辑相同。这一配置尚未改善该样例的时序；完整对照见实验部分。')
    text=text.replace('@@REFERENCE_BRANCH@@',bind(ROOT/'assets/reference_branch.svg').read_text())
    context_mf_dir=PROJECTS/'h3-ive-reference-phase-mf-host41-20261020'
    context_mf=read(context_mf_dir/'audit/RESULTS_VERIFIED.json')
    qualified=read(bind(context_mf_dir/'audit/QUALIFIED_RESULTS.json','867bca098ac1493f1b4ec544bbf24bd442e4ed12fe80e5442ae7885123639907'))
    for result in context_mf['results']:bind(result['result_file'],result['result_sha256'])
    context_scores={(r['case'],r['role']):r['score'] for r in context_mf['results']}
    phase=PROJECTS/'h3-ive-reference-origin-metrics-r132-20261020'
    phase_review=read(bind(phase/'audit/full106_exploratory_review/REVIEW.json','fa54e682af82b44a5d9e5e30db56c2c80fb26fa7b0b2dd6146c1cd1fa44b99cd'))
    assert phase_review['all_frames_inspected'] and len(phase_review['inspected_frame_indices'])==106
    assert phase_review['task']['status']=='PASS_CORE_EDIT'
    assert not phase_review['paired_input_exact'] and phase_review['exploratory']
    assert all(e['reference_origin']['frames']==e['R122_native']['frames'] for e in phase_review['events'])
    bind(origin/'audit/input_pixel_difference_cpu/SUMMARY.json','935de471c0e18aca13a3ea3ee7bce1e904c5fb51a23ad2fb66fc48aaea7ffa94')
    evidence_tree(phase_review['original_failed_gate'])
    evidence_tree(phase_review['actual_release'])
    phase_media=read(phase/'showcase_exploratory/source_native_reference_origin/PRESENTATION.json')
    for item in phase_media['inputs']:evidence_tree(item)
    phase_picture=uri(ROOT/'assets/r132_frame081.png','image/png')
    phase_video=phase_media['videos'][0]
    phase_panel='<article class="result" id="reference-phase-control"><div class="resulthead"><h3>结构对照：辅助参考 Attention 的时间相位对齐</h3><span>IVEBench · long_0039</span></div>'
    phase_panel+='<div class="inputnote"><p><b>方法：</b>第 2.6 节辅助参考分支相位对齐，预设第 7–15 步启用。</p><p><b>编辑指令：</b>Adjust the color of book to blue；角色参考图：无。</p><p>沿用第 3 组的源文件、实际提示词和初始噪声。历史普通编辑与本次推理的输入 RGB 存在跨环境解码差异，因此本组列为探索性结构对照。</p></div>'
    phase_panel+=f'<figure><img loading="lazy" src="{phase_picture}" alt="第81帧参考视频、普通编辑、辅助参考分支相位引导"><figcaption class="imagecaption">第 81 帧，3.375 秒。两种编辑都保留蓝色书封，参考视频已经立起书本，两种编辑仍未跟上。</figcaption></figure>'
    phase_panel+=f'<video controls playsinline preload="none" poster="{phase_picture}" src="{uri(phase/"showcase_exploratory/source_native_reference_origin"/phase_video["file"],"video/mp4",phase_video["sha256"])}"></video>'
    phase_panel+='<div class="controls"><button type="button" data-rate="1">1×</button><button type="button" data-rate="0.5">0.5×</button><button type="button" data-restart>从头播放</button></div>'
    phase_panel+=f'<div class="imagecaption">全 106 帧检查显示，五个动作的时间区间均与普通编辑相同。IVEBench MF：普通编辑 0.877733，参考分支相位引导 {context_scores["long_0039","reference_origin"]:.6f}。该配置完成了编辑，动作延后仍然存在。</div></article>'
    text=text.replace('@@REFERENCE_PHASE_RESULT@@',phase_panel)
    context_note=f'<p>手帕改白色的两版均完成编辑：抬手和接触时刻同步，撤回动作均晚约 16 帧；MF 为 {context_scores["long_0059","native"]:.6f} → {context_scores["long_0059","guided"]:.6f}。老虎替换为狮子的普通编辑已保持张嘴、闭嘴的时间，MF 为 {context_scores["short_0177","native"]:.6f}，跳过引导。</p>'
    bird_review=read(bind(PROJECTS/'h3-ive-prompt-envelope-metrics-r123-20261020/variants/long0122_full_context/audit/full_frame_review/long_0122/paired/INDEPENDENT_REVIEW.json','fa0bab56f82353d9864474026ba50c5c15147cf428bd8a12f330dacfdc78e87e'))
    bird_note=f'<p>巨嘴鸟替换的两版均完成主体编辑，开头两项遗漏动作均未恢复，后半段梳羽保持同步；MF 为 {newest_scores["long_0122","native"]:.6f} → {newest_scores["long_0122","guided"]:.6f}。</p>'
    text=text.replace('<p><b>新素材检查。</b>','<details><summary>查看新素材的编辑与时序检查</summary><p><b>新素材检查。</b>')
    text=text.replace('<h3>3.3　时序干预效果</h3>',bird_note+context_note+'</details><h3>3.3　时序干预效果</h3>')
    figures=[('ARCH',architecture),('OPERATOR',operator),('TIME',timelines),('AUTO',controller),('TRANSPORT',transport),('ATTENTION',attention),('AUTO_HISTORY',lambda:auto_history(history))]
    for name,func in figures:
        figure=func();(ROOT/'assets'/f'{name.lower()}.svg').write_text(figure)
        text=text.replace('@@'+name+'@@',figure)
    for name,key in [('FLEX','FlexiAct'),('IVE','IVEBench')]:
        e=protocol['examples'][key]
        text=text.replace('@@'+name+'_SOURCE@@',uri(e['reference_video_path'],'video/mp4',e['media_sha256']['reference_video_path']))
        if e['reference_image_used']:text=text.replace('@@FLEX_IMAGE@@',uri(e['reference_image_path'],'image/jpeg',e['media_sha256']['reference_image_path']))
    records={r['label']:r for r in provenance['samples']}
    event_dir=PROJECTS/'h3-timing-architecture-r2-20261016/audit/event_time_summary_20261020'
    event_summary=read(bind(event_dir/'RESULT.json','43acba83fa59ca5018374c2fc223ba605860006dfdea440e0e3955031f1e6cf7'))
    bind(event_dir/'summarize.py')
    event_runs={r['run']:r for r in event_summary['runs']}
    for run in event_runs.values():
        bind(run['annotation']['file'],run['annotation']['sha256'])
        assert run['fps']==24 and len(run['events'])==3
    cases=[(1,materials['items'][0],records['R73'],'角色替换：男人改为年长女子','前两个动作由约 15 帧延后回到参考区间，后续阶段也有改善。'),(2,materials['items'][2],records['R89'],'外观编辑：给男人添加眼镜','前两段动作略提前，后段仍约晚 10–17 帧。')]
    mfpanels=[]
    for index,item,record,title,observation in cases:
        assert record['native_and_guided_prompt_equal'] and not record['reference_image_used']
        evidence_tree(record['evidence_graphs']);evidence_tree(record['score_evidence'])
        picture=uri(item['image']['file'],'image/jpeg',item['image']['sha256'])
        panel=f'<article class="result" id="case{index}"><div class="resulthead"><h3>{title}</h3><span>IVEBench · {record["source_id"]}</span></div>'
        panel+=f'<div class="inputnote"><p><b>方法：</b>时间 Attention 重分配，预设第 7–15 步启用。</p><p><b>输入：</b>1 条参考视频；角色参考图：无。</p><p><b>提示词中的任务句：</b>{escape(record["official_edit_prompt"])}</p>'
        panel+=f'<details><summary>查看实际完整提示词（历史六段改写，普通／干预相同）</summary><pre>{escape(record["actual_prompt"])}</pre></details></div>'
        panel+=f'<figure><img loading="lazy" src="{picture}" alt="{escape(title)}同帧对比截图"><figcaption class="imagecaption">同一时刻截图。左：参考视频；中：普通编辑；右：时序干预。</figcaption></figure>'
        panel+=f'<video controls playsinline preload="none" poster="{picture}" src="{uri(item["video"]["file"],"video/mp4",item["video"]["sha256"])}"></video>'
        panel+='<div class="controls"><button type="button" data-rate="1">1×</button><button type="button" data-rate="0.5">0.5×</button><button type="button" data-restart>从头播放</button></div>'
        panel+=f'<div class="imagecaption">对比视频：三列按相同物理时间播放。{observation}</div></article>'
        text=text.replace(f'@@RESULT{index}@@',panel)
        scores=record['scores']
        interpretation=('局部动作更接近参考，MF 微降 0.000265，基本持平。整体轨迹分数与这处动作时间的变化方向不同。' if index==1 else 'MF 上升 0.007412，前段动作略有改善；后段仍明显延后。分数上升与整段动作对齐程度分别记录。')
        card=f'<article class="mfcase"><h3>{title} · IVEBench MF</h3><img loading="lazy" src="{picture}" alt="对应MF的同帧对比截图"><div class="imagecaption">参考视频／普通编辑／时序干预；对应上方第 {index} 组视频。</div>'
        card+=f'<div class="scores"><span>普通编辑 <b>{scores["native"]:.6f}</b></span><span>时序干预 <b>{scores["guided"]:.6f}</b></span><span>变化 <b>{scores["delta"]:+.6f}</b></span></div><p>{interpretation}</p></article>'
        event_lag=event_runs[record['label']]['mean_absolute_event_lag_ms']
        event_range=lambda key: '–'.join(f'{v:.0f}' for v in event_lag[key])
        event_text=f'<p><b>三个可见动作的平均绝对时差：</b>普通编辑 {event_range("native")} ms，时序干预 {event_range("guided")} ms。范围来自逐帧标注的动作发生区间；三个动作分别等权统计。</p>'
        card=card.replace('</article>',event_text+'</article>')
        mfpanels.append(card)
    recent=read(ROOT/'audit/event_time_update_20261020/RESULT.json')
    evidence_tree(recent['helper']);evidence_tree(recent['script'])
    for run in recent['runs']:evidence_tree(run['annotation'])
    mf=read(bind(PROJECTS/'h3-ive-context-mf-host41-20261020/audit/RESULTS_VERIFIED.json','a6054c8a77b8c56b80f29b6309fa3c425e61ad4511637994789d0698f08825f0'))
    scores={(r['case'],r['role']):r['score'] for r in mf['results']}
    for r in mf['results']:bind(r['result_file'],r['result_sha256'])
    book=PROJECTS/'h3-ive-generic-retention-metrics-r122-20261020'
    review=read(book/'audit/full_frame_review/long_0039/paired/REVIEW.json')
    bind(book/'audit/full_frame_review/long_0039/paired/ROOT_PAIRED_SPOT_CHECK.json')
    presentation=read(book/'showcase_pairs/long_0039/PRESENTATION.json')
    evidence_tree(presentation['gate']);evidence_tree(presentation['collection'])
    for item in presentation['inputs']:evidence_tree(item)
    assert review['all_valid_frames_inspected'] and len(review['examined_frames'])==106
    assert all(v['status']=='PASS_CORE_EDIT' for v in review['task_acceptance'].values())
    picture=uri(book/'showcase_pairs/long_0039/key_frame_081.png','image/png','d93fa234dc37fa726f1850a29522f7c32c55ce9603e876c25fe5219837c2840e')
    video=presentation['videos'][0]
    prompt=bind(PROJECTS/'h3-timing-ive-generic-retention-r122-20261020/configs/prompts/long_0039.txt').read_text()
    panel='<article class="result" id="case3"><div class="resulthead"><h3>外观编辑：书本改为蓝色</h3><span>IVEBench · long_0039</span></div>'
    panel+='<div class="inputnote"><p><b>方法：</b>时间 Attention 重分配，预设第 7–15 步启用。</p><p><b>输入：</b>参考视频的前 4.4 秒；角色参考图：无。</p><p><b>官方编辑指令：</b>Adjust the color of book to blue</p>'
    panel+=f'<details><summary>查看实际完整提示词（参考定义、编辑原句、通用保留要求）</summary><pre>{escape(prompt)}</pre></details></div>'
    panel+=f'<figure><img loading="lazy" src="{picture}" alt="书本改色第81帧三元对照"><figcaption class="imagecaption">第 81 帧，3.375 秒。左：参考；中：普通编辑；右：时序引导。引导版的书本已经立起，普通版仍接近平放。</figcaption></figure>'
    panel+=f'<video controls playsinline preload="none" poster="{picture}" src="{uri(book/"showcase_pairs/long_0039"/video["file"],"video/mp4",video["sha256"])}"></video>'
    panel+='<div class="controls"><button type="button" data-rate="1">1×</button><button type="button" data-rate="0.5">0.5×</button><button type="button" data-restart>从头播放</button></div>'
    panel+='<div class="imagecaption">两版均完成书本改色，保留办公室和拿书动作。引导后起书约提前 8 帧，抬离支撑约提前 7 帧，翻开约提前 5 帧；触书时刻相近，最初伸手过程拉长。</div></article>'
    text=text.replace('@@RESULT3@@',panel)
    n,g=scores['long_0039','native'],scores['long_0039','forced']
    times=next(r for r in recent['runs'] if r['run']=='R122')['mean_absolute_event_lag_ms']
    fmt=lambda key:'–'.join(f'{v:.0f}' for v in times[key])
    card=f'<article class="mfcase"><h3>外观编辑：书本改为蓝色 · IVEBench MF</h3><img loading="lazy" src="{picture}" alt="书本改色对应MF的同帧对比"><div class="imagecaption">对应上方第 3 组视频。</div><div class="scores"><span>普通编辑 <b>{n:.6f}</b></span><span>时序干预 <b>{g:.6f}</b></span><span>变化 <b>{g-n:+.6f}</b></span></div>'
    card+=f'<p><b>五个可见动作的平均绝对时差：</b>普通编辑 {fmt("native")} ms，时序干预 {fmt("guided")} ms。动作区间逐帧标注，五个动作等权统计。</p>'
    card+='<p>局部动作时间更接近参考，全图 MF 下降。同时，手离开键盘至接触书本由 12–17 帧延长到 25–30 帧。后续评测同时记录转折时刻、阶段持续时间和场景保持。</p></article>'
    mfpanels.append(card)
    text=text.replace('@@MFCASES@@',''.join(mfpanels))
    sensitivity_dir=PROJECTS/'h3-ive-r121-mf-host41-20261020/audit/known_lag_sensitivity_20261020'
    sensitivity=read(bind(sensitivity_dir/'RESULT.json','1b87f980f48b066269d2f667e90a61b1c0ee7130894d0e888a1d682c175e67a9'))
    bind(sensitivity_dir/'check.py',sensitivity['script']['sha256'])
    assert sensitivity['passed'] and sensitivity['original_tracks_unchanged'] and not sensitivity['CUDA_initialized']
    for source in sensitivity['sources']:
        scores=[r['official_MF'] for r in sensitivity['results'] if r['source_id']==source['source_id']]
        assert len(scores)==5 and scores[0]==1 and all(a>b for a,b in zip(scores,scores[1:]))
    text=text.replace('@@MF_SENSITIVITY@@','<p><b>已知时延检查。</b>将两条参考视频的原始跟踪轨迹分别延后 4、8、12、16 帧，沿用官方 MF 计算。两条曲线均随延迟增大而下降：从自比较的 1.000 降至 16 帧延迟时的 0.864、0.880。MF 能响应纯时间偏移；真实编辑还会改变空间轨迹、可见性及轨迹配对。该检查使用缓存轨迹构造控制变量，正式成片评测继续保留全图 MF 和动作时间记录。</p>')
    region_dir=PROJECTS/'h3-ive-r113-seed-replication-mf-host41-20261020/audit/match_group_diagnostic_20261020'
    region=read(bind(region_dir/'RESULT.json','d206a83eb91f43dec19739e51f55508de209722bb0166e25079ee0efdfca601d'))
    labels=read(bind(region_dir/'SOURCE_GROUPS.json',region['source_labels']['sha256']))
    bind(region_dir/'check.py',region['script']['sha256'])
    bind(labels['source_point_binding']['file'],labels['source_point_binding']['sha256'])
    groups=region['source_frame0_groups']
    assert region['passed'] and not region['CUDA_initialized']
    assert sum(v['source_points'] for v in groups.values())==100
    assert all(v['assignment_changed']==0 for v in groups.values())
    delta=region['official_scores']['guided']-region['official_scores']['native']
    assert abs(sum(v['global_MF_contribution_delta'] for v in groups.values())-delta)<1e-12
    region_html='<p><b>区域贡献分解。</b>机舱角色替换的另一随机种子中，全图 MF 从 0.807350 降至 0.795975。按参考首帧的点位分组，目标成人的平均轨迹相似度从 0.792388 升至 0.796221；机舱、座椅和儿童区域的下降拉低了总分。两版使用的 100 个轨迹配对索引相同。这说明需要同时记录目标动作时间和周围场景的保持情况。</p>'
    region_html+='<details><summary>查看这次重测的区域分解与源图点位</summary><p>下表基于同一组官方轨迹与匹配结果，按源视频首帧人工标注区域。组内均值为该组轨迹的相似度平均；最后一列为该组对全图 MF 差值的贡献，各组贡献之和等于 −0.011375。</p><div class="scroll"><table><thead><tr><th>首帧区域</th><th>点数</th><th>普通编辑均值</th><th>引导编辑均值</th><th>对全图差值的贡献</th></tr></thead><tbody>'
    for key,label in [('edited_adult','目标成人'),('child','儿童'),('cabin_and_seats','机舱与座椅'),('other_passengers','其他乘客'),('uncertain_or_boundary','边界及不确定区域')]:
        row=groups[key];n=row['source_points']
        region_html+=f'<tr><td>{label}</td><td>{n}</td><td>{row["global_MF_contribution_native"]*100/n:.6f}</td><td>{row["global_MF_contribution_guided"]*100/n:.6f}</td><td>{row["global_MF_contribution_delta"]:+.6f}</td></tr>'
    region_html+='</tbody></table></div>'
    region_html+=f'<img style="display:block;width:100%;height:auto" loading="lazy" src="{uri(region_dir/"source_frame0_point_ids.png","image/png",labels["preview_sha256"])}" alt="源视频首帧的100个轨迹查询点与编号"><p class="note">源视频首帧与点位编号。区域标签描述轨迹的起点；后续运动、遮挡和跟踪漂移另外核对。该重测的随机种子为 2026101703。</p></details>'
    text=text.replace('@@MF_REGIONS@@',region_html)
    phase_dir=PROJECTS/'h3-timing-architecture-r2-20261016/audit/event_phase_duration_20261020'
    phase=read(bind(phase_dir/'RESULT.json','a0d4d66d2dbf27ec141b89e5ea84dfa699fe979366f424b002d1cce2ed8f2185'))
    bind(phase_dir/'summarize.py',phase['script_sha256'])
    bind(phase_dir.parent/'event_phase_duration_independent_check_20261020/REVIEW.json','0a9dd9b1d3420626beb4854c5b959d762982a637886c2e3098293c911b38e168')
    labels={'R73':'机舱角色替换','R89':'饮酒者加眼镜','R113_2026101702':'机舱角色替换，种子 1702','R113_2026101703':'机舱角色替换，种子 1703','R122':'书封改蓝色','R123_full':'饮酒者加眼镜，完整 Context-IR'}
    phase_html='<p><b>动作阶段时长。</b>对六次已标注实验，计算每两个相邻动作之间的持续时间，再与参考视频比较。整体平移会改变动作发生时刻，但保持阶段时长。机舱原样例两项都改善；书封改色中，较早伸手与仍偏晚接触书本共同拉长了伸手阶段。方法迭代同时检查这两类时间误差。</p>'
    phase_html+='<details><summary>查看六次实验的阶段时长误差</summary><div class="scroll"><table><thead><tr><th>实验</th><th>阶段数</th><th>普通编辑</th><th>时序干预</th></tr></thead><tbody>'
    for run in phase['runs']:
        bind(run['annotation']['file'],run['annotation']['sha256'])
        values=run['mean_absolute_midpoint_duration_error_frames']
        phase_html+=f'<tr><td>{labels.get(run["run"],run["run"])}</td><td>{len(run["phases"])}</td><td>{values["native"]:g} 帧</td><td>{values["guided"]:g} 帧</td></tr>'
    phase_html+='</tbody></table></div><p class="note">数值为相邻动作间隔的平均绝对误差，按逐帧标注区间的中点计算；24 fps，越小越接近参考节奏。原始标注区间另行保留。六次实验来自三个独立源视频。</p></details>'
    text=text.replace('@@PHASE_DURATION@@',phase_html)
    text=text.replace('@@METRIC_ORIGIN@@','<b>IVEBench 样例采用 IVEBench 官方 MF；FlexiAct 样例采用 FlexiAct 官方 MF。</b>两者实现分别来自各自作者仓库：前者结合轨迹位置与速度，后者主要比较逐步位移方向的相似度。取帧和跟踪设置也分别记录，分数按 benchmark 分开报告。本节三个具体案例均使用 IVEBench 的实现。')
    prompt_review=read(PROJECTS/'h3-ive-official-positive-recheck-metrics-r121-20261020/audit/full_frame_review/short_0358/native/INDEPENDENT_REVIEW.json')
    assert prompt_review['task_acceptance']['native']['status']=='FAIL'
    prompt_consumer=PROJECTS/'h3-ive-prompt-envelope-metrics-r123-20261020/variants'
    generic=read(prompt_consumer/'generic_retention/audit/full_frame_review/short_0358/native/INDEPENDENT_REVIEW.json')
    full=read(bind(prompt_consumer/'full_context/audit/full_frame_review/short_0358/native/INDEPENDENT_REVIEW.json','316861610296415d3de6c848de49ffc8060df2b447434f3f25f123d90c752b8c'))
    assert generic['task_verdict']=='PARTIAL_EDIT_SCOPE' and full['task_verdict']=='PASS'
    assert len(full['frames_reviewed'])==105 and all(full['task_dimensions'].values())
    bind(PROJECTS/'h3-timing-architecture-r2-20261016/audit/h3_official_prompt_envelope_20261020/EVIDENCE.json')
    full_pair=read(prompt_consumer/'full_context/audit/full_frame_review/short_0358/paired/INDEPENDENT_REVIEW.json')
    assert full_pair['source_id']=='short_0358'
    text=text.replace('@@PROMPT_FORMAT_UPDATE@@','<p><b>提示格式检查。</b>在加眼镜样例中，简短编辑句生成了单人近景，并把饮酒改成戴眼镜；加入通用保留要求后，双人场景和饮酒动作恢复，但两人都戴了眼镜。完整 Context-IR 明确目标人物与保留人物后，仅饮酒者增加眼镜，原动作链保留。三版分别完整检查了 105 个有效帧。本轮固定模型输入适配，再比较同提示词的普通编辑和时序引导。完整格式下，引导使瓶口到嘴约提前 3 帧，离嘴约提前 1–2 帧，后段仍延后；对应 MF 从 0.891758 降至 0.881065。这是同一来源的复测。<a href="https://github.com/MiniMax-AI/MiniMax-H3#h3-context-ir">[H3 输入格式]</a></p>')
    online=read(bind(PROJECTS/'h3-oxygen-online-recovery-metrics-r138-20261020/audit/REPORT_HANDOFF.json','7520fb7bd7f2193fa9a0bbce8fd77db83ab0ffc60f3302ad5f582e914bd30432'))
    evidence_tree(online)
    media=online['comparison_media']['source_native_visible_only']
    still=media['stills'][0];video=media['videos'][0]
    picture=uri(still['file'],'image/jpeg',still['sha256'])
    panel='<article class="result" id="automatic-result"><div class="resulthead"><h3>自动时序干预：角色替换</h3><span>IVEBench · short_0252</span></div>'
    panel+='<div class="inputnote"><p><b>方法：</b>每个去噪步根据预测视频的手臂方向估计动作时差，自动选择视频时间窗并决定是否执行时间 Attention 重分配。目标成人的画面范围预先指定。</p><p><b>输入：</b>1 条参考视频，无角色参考图。编辑指令：Replace the man with an elderly woman。</p>'
    panel+=f'<details><summary>实际提示词：沿用既有正例的结构化改写</summary><pre>{escape(online["actual_prompt"]["text"])}</pre></details></div>'
    panel+=f'<figure><img loading="lazy" src="{picture}" alt="参考、普通编辑、自动干预第50帧对照"><figcaption class="imagecaption">第 50 帧，2.083 秒。左：参考视频；中：普通编辑；右：自动时序引导。参考与自动版已握住面罩，普通编辑仍在抬手。</figcaption></figure>'
    panel+=f'<video controls playsinline preload="none" poster="{picture}" src="{uri(video["file"],"video/mp4",video["sha256"])}"></video>'
    panel+='<div class="controls"><button type="button" data-rate="1">1×</button><button type="button" data-rate="0.5">0.5×</button><button type="button" data-restart>从头播放</button></div>'
    panel+='<p class="imagecaption">完整 98 帧对照，24 fps。自动版完成角色替换并保留儿童、机舱及动作链。普通编辑、固定引导、自动引导沿用相同提示词和初始噪声。</p><div class="scroll"><table><thead><tr><th>动作</th><th>参考</th><th>普通编辑</th><th>固定引导</th><th>自动引导</th></tr></thead><tbody>'
    for label,event in zip(['抬手','握住面罩','提带到脸侧'],online['events']):
        values=['–'.join(map(str,event[k])) for k in ['source_frames','native_frames','fixed_frames','auto_frames']]
        panel+='<tr><td>'+label+'</td>'+''.join('<td>'+v+'</td>' for v in values)+'</tr>'
    panel+='</tbody></table></div><p class="note">表内数值为动作发生的帧区间。自动版的三个动作与参考区间重叠，效果接近固定引导。</p>'
    panel+='<p><b>实际控制：</b>20 个去噪步中，第 2、4、5、11、15、18、19 步执行引导。前 3 次针对主要动作段；该段估计时差从约 +15 帧降到 −2 至 −1 帧后停止引导。后 4 次落在近静止片段，暴露出静态姿态差被误判为时差的问题。对已有 20 步预测轨迹进行 CPU 重放：先复现全部原决策，再加入方向特征去均值后的相对匹配增益条件，保留前 3 次主动作引导，排除后 4 次静止片段引导。该过滤条件的闭环成片复测待完成。</p>'
    bind(PROJECTS/'h3-source-temporal-observability-20261020/full_replay/FINAL_HANDOFF.json','9390cf235f8905dc05938c1afcce195cd8f4e105150095dd826b0aace8b02dc9')
    scores=online['official_MF']
    panel+=f'<p><b>IVEBench MF：</b>普通编辑 {scores["native"]["value"]:.6f}；固定引导 {scores["fixed"]["value"]:.6f}；自动引导 {scores["visible_only"]["value"]:.6f}。局部动作时间改善，全图 MF 略低于普通编辑。本次沿用同一正例来源，独立改善来源仍为 3 条。</p></article>'
    text=text.replace('@@AUTO_CURRENT@@',panel)
    assert '@@' not in text
    import os
    staged=ROOT/'index.next.html';staged.write_text(text);os.replace(staged,ROOT/'index.html')
    staged_output=OUT.with_name(OUT.name+'.next')
    if staged_output.exists():staged_output.unlink()
    os.link(ROOT/'index.html',staged_output);os.replace(staged_output,OUT)
    receipt={'output':str(OUT),'sha256':sha(OUT),'bytes':OUT.stat().st_size,'evidence':BINDINGS,'media_count':len(re.findall(r'<video\b',text)),'inline_svg_count':len(re.findall(r'<svg\b',text))}
    (ROOT/'evidence/BUILD_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in receipt.items() if k!='evidence'},ensure_ascii=False))

if __name__=='__main__':main()
