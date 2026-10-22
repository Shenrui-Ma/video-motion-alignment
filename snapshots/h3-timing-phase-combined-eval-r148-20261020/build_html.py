"""Small independent HTML using existing media pointers, never embedded media."""
from html import escape
import json
from pathlib import Path
import subprocess
from prepare_comparison import ROOT, FFMPEG, bound, read, require


def link(path, label):
    return f'<a href="{escape(Path(path).as_uri(), quote=True)}">{escape(label)}</a>'


def interval(value):
    return "待评估" if value is None else f"{value[0]}–{value[1]}"


def event_label(event):
    return {"hand_approaches_eye": "抬手靠近眼部", "eye_wiping_contact": "手帕接触眼部",
            "hand_leaves_face": "手离开面部"}.get(event["label"], event["label"])


def latency_ms(source, target, fps):
    if source is None or target is None:
        return None
    return [(target[0] - source[1]) * 1000 / fps, (target[1] - source[0]) * 1000 / fps]


def duration_frames(start, end):
    if start is None or end is None:
        return None
    return [end[0] - start[1], end[1] - start[0]]


def poster(item, geometry):
    dest = ROOT / "posters"
    dest.mkdir(exist_ok=True)
    out = dest / (item["sha256"] + ".jpg")
    if not out.exists():
        x, y, w, h = geometry["crop_xywh"]
        vf = (f"crop={w}:{h}:{x}:{y},"
              "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2:black")
        subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-threads", "1",
                        "-i", item["file"], "-vf", vf, "-frames:v", "1",
                        "-q:v", "3", "-threads", "1", str(out)], check=True, timeout=30)
    return out.as_uri()


def main():
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    roles = manifest["roles"]
    timing_path = ROOT / "audit/COMPLETED_SAMPLER_TIMING.json"
    timing = {t["source_id"]: t for t in read(timing_path)["items"]} if timing_path.exists() else {}
    cards = []
    built = []
    for c in manifest["cases"]:
        sid, g = c["source_id"], c["geometry"]
        presentation = ROOT / "review" / sid / "PRESENTATION.json"
        media = dict(c["media"])
        events, mf = c["events"], dict(c["official_MF"])
        screenshots = []
        verdict = "组合版待实际成片与完整评审"
        new_ready = False
        appearance = ""
        execution_note = ""
        if presentation.exists():
            result = read(presentation)
            require(result["evaluation_manifest"] == bound(ROOT / "EVALUATION_MANIFEST.json"),
                    "Presentation uses another manifest; rebind before rebuilding")
            output = result["inputs"]["fixed_phase"]
            require(bound(output["file"])["sha256"] == output["sha256"], "Rendered input changed")
            media["fixed_phase"] = output
            screenshots = result["screenshots"]
            new_ready = True
            verdict = "组合版执行证据已验，完整人工评审待填写"
            review_path = presentation.with_name("REVIEW.json")
            if review_path.exists():
                review = read(review_path)
                require(review["combined_video_sha256"] == output["sha256"], "Review media differs")
                require(review["all_valid_frames_inspected"] is True
                        and review["valid_frames"] == g["valid_frames"], "Review coverage incomplete")
                events = review["events"]
                verdict = review["task_verdict_zh"] + "；" + review["timing_conclusion_zh"]
                visual = review.get("appearance_comparison")
                if visual:
                    appearance = "<p>" + escape(" ".join(visual[k] for k in
                        ("identity_zh", "pose_zh", "ghosting_zh"))) + "</p>"
            if result["validated_execution"].get("validation_mode") == "independent_final_decode_recovery":
                execution_note = "<p class=\"meta\">书本的20步采样在重启前完成；使用已核验的最终 latent 单独恢复解码，新增 DiT 前向为0，原中断记录保留。</p>"
            sample = timing.get(sid)
            if sample and sample.get("actual_video_sha256") == output["sha256"]:
                seconds = sample["sampler_elapsed_seconds_logged"]
                execution_note += (f'<p class="meta">组合版采样：{seconds // 60}分{seconds % 60:02d}秒，'
                    f'日志均值 {sample["mean_seconds_per_step_logged"]:.2f} 秒/步。'
                    '包含采样回调与审计开销，载入和最终解码另计。</p>')
            mf_path = presentation.with_name("OFFICIAL_MF.json")
            if mf_path.exists():
                score = read(mf_path)
                require(score["actual_generated_video_sha256"] == output["sha256"], "MF media differs")
                require(score["valid_frames"] == g["valid_frames"] and score["fps"] == g["fps"]
                        and score["crop_xywh"] == g["crop_xywh"], "MF frame domain differs")
                mf["fixed_phase"] = score
        for role in ("native", "fixed", "fixed_phase"):
            score_path = ROOT / "scores" / sid / (role + ".json")
            if score_path.exists():
                score = read(score_path)
                require(role in media and score["actual_generated_video_sha256"] == media[role]["sha256"],
                        "Display MF video differs")
                require(score["source_full_sha256"] == c["media"]["source"]["sha256"]
                        and score["valid_frames"] == g["valid_frames"] and score["fps"] == g["fps"]
                        and score["crop_xywh"] == g["crop_xywh"], "Display MF domain differs")
                require(bound(score["result"]["file"]) == score["result"]
                        and bound(score["final_release"]["file"]) == score["final_release"],
                        "Display MF receipt changed")
                mf[role] = score
        figures = []
        for role in roles:
            item = media.get(role)
            if item:
                panel = f'<video muted playsinline preload="metadata" poster="{escape(poster(item, g), quote=True)}" src="{escape(Path(item["file"]).as_uri(), quote=True)}"></video>'
            else:
                panel = '<div class="pending">等待已验证组合版成片</div>'
            figures.append(f'<figure>{panel}<figcaption>{escape(manifest["method_labels"][role])}</figcaption></figure>')
        tables = []
        for e in events:
            tables.append("<tr><th>" + escape(event_label(e)) + "</th>" +
                          "".join("<td>" + interval(e.get(role)) + "</td>" for role in roles) + "</tr>")
        event_section = ('<table><thead><tr><th>动作事件（0-based 帧）</th>' +
                         "".join("<th>" + escape(manifest["method_labels"][r]) + "</th>" for r in roles) +
                         "</tr></thead><tbody>" + "".join(tables) + "</tbody></table>") if tables else ""
        if events:
            lag_rows, phase_rows = [], []
            for e in events:
                cells = []
                for role in ("native", "fixed", "fixed_phase"):
                    lag = latency_ms(e.get("source"), e.get(role), g["fps"])
                    cells.append("待评估 / 缺失" if lag is None else f"{lag[0]:+.0f}～{lag[1]:+.0f}")
                lag_rows.append("<tr><th>" + escape(event_label(e)) + "</th>" +
                                "".join("<td>" + text + "</td>" for text in cells) + "</tr>")
            for start, end in zip(events, events[1:]):
                values = [duration_frames(start.get(role), end.get(role)) for role in roles]
                phase_rows.append("<tr><th>" + escape(event_label(start) + " → " + event_label(end)) +
                                  "</th>" + "".join("<td>" + interval(v) + "</td>" for v in values) + "</tr>")
            event_section += ('<details><summary>动作时差与阶段持续时间</summary>'
                              '<p>时差单位为毫秒，正值表示晚于参考。范围由既有事件标注区间相减得到；阶段持续时间为相邻事件之差。</p>'
                              '<table><tr><th>事件时差（ms）</th><th>普通编辑</th><th>时序引导</th><th>时序引导＋相位对齐</th></tr>' +
                              "".join(lag_rows) + '</table><table><tr><th>阶段持续时间（帧）</th>' +
                              "".join("<th>" + escape(manifest["method_labels"][r]) + "</th>" for r in roles) +
                              "</tr>" + "".join(phase_rows) + "</table></details>")
        diagnostics = c.get("historical_window_diagnostics")
        if diagnostics:
            final_diagnostics = {}
            diagnostic_path = ROOT / "sam_final_pose/RESULT.json"
            if diagnostic_path.exists():
                diagnostic = read(diagnostic_path)
                require(diagnostic["source_id"] == sid
                        and diagnostic["final_video"] == media.get("fixed_phase")
                        and bound(diagnostic["final_pose"]["file"]) == diagnostic["final_pose"],
                        "Final pose diagnostic video differs")
                for item in diagnostic["measurements"]:
                    final_diagnostics[(tuple(item["window"]), str(item["confidence"]))] = item["reliable_lag_frames"]
            rows = []
            for w in diagnostics["windows"]:
                cells = [interval(w["window"])]
                for role in ("native", "fixed"):
                    values = w[role]
                    cells.append(" / ".join("缺测" if values[t] is None else str(values[t]) for t in ("0.3", "0.5")))
                cells.append(" / ".join(
                    "缺测" if final_diagnostics[(tuple(w["window"]), t)] is None
                    else str(final_diagnostics[(tuple(w["window"]), t)])
                    for t in ("0.3", "0.5")) if final_diagnostics else "待离线评估")
                rows.append("<tr>" + "".join("<td>" + escape(v) + "</td>" for v in cells) + "</tr>")
            event_section += ('<p>沿用历史手臂方向评估窗口；下表为已有离线 lag（帧，置信度 0.3 / 0.5），不是动作起止区间。</p>'
                              '<table><tr><th>窗口</th><th>普通编辑</th><th>时序引导</th><th>时序引导＋相位对齐</th></tr>' +
                              "".join(rows) + "</table>")
        score_cells = []
        for role in ("native", "fixed", "fixed_phase"):
            value = mf.get(role)
            score_cells.append("<td>" + (f"{value['score']:.6f}" if value else "未测 / 待评估") + "</td>")
        score_table = ('<table><tr><th>官方 MF</th><th>普通编辑</th><th>时序引导</th><th>时序引导＋相位对齐</th></tr>'
                       "<tr><th>完整有效帧域</th>" + "".join(score_cells) + "</tr></table>")
        thumbs = ""
        if screenshots:
            # Select existing event/window centers, without inventing new event boundaries.
            centers = sorted({round(sum(e[r]) / 2) for e in events for r in roles if e.get(r)})
            if diagnostics:
                centers = sorted(set(centers + [sum(w["window"]) // 2 for w in diagnostics["windows"]]))
            by_frame = {s["physical_frame"]: s for s in screenshots}
            chosen = [by_frame[n] for n in centers if n in by_frame] or screenshots
            if len(chosen) > 8:
                chosen = [chosen[round(i * (len(chosen) - 1) / 7)] for i in range(8)]
            thumbs = '<div class="shots">' + "".join(
                f'<a href="{escape(Path(s["file"]).as_uri(), quote=True)}"><img loading="lazy" src="{escape(Path(s["file"]).as_uri(), quote=True)}" alt="第{s["physical_frame"]}帧四列对照"><span>第{s["physical_frame"]}帧</span></a>' for s in chosen) + "</div>"
        source_label = c.get("prompt_source_label", "历史已完成任务的实际提交图；原文逐字复用")
        info = f'<p class="meta">{g["valid_frames"]} 个有效帧 · {g["fps"]} fps · seed {c["seed"]} · {escape(verdict)}</p>'
        prompt = (f'<details><summary>提示词及来源</summary><p>{escape(source_label)}</p>'
                  f'<pre>{escape(c["prompt"])}</pre><p>SHA256: <code>{escape(c["prompt_sha256"])}</code></p>'
                  + link(c["historical_runs"]["fixed"]["graph"]["file"], "实际旧引导图") + "</details>")
        evidence = "<p>" + link(c["historical_review"]["file"], "历史评审") + " · " + link(ROOT / "EVALUATION_MANIFEST.json", "绑定清单") + "</p>"
        if presentation.exists():
            evidence += "<p>" + link(presentation, "新成片完整帧目录与执行证据") + " · " + link(result["video"]["file"], "原速四列合成视频") + "</p>"
        cards.append(f'<section id="{escape(sid)}"><h2>{escape(c["title"])}</h2>{info}'
                     f'<div class="comparison" data-duration="{g["valid_frames"]/g["fps"]}" data-fps="{g["fps"]}">'
                     '<div class="four">' + "".join(figures) + '</div><div class="controls">'
                     '<button class="play">原速同步播放</button><button class="pause">暂停</button><button class="fullscreen">全屏</button>'
                     f'<input aria-label="同帧定位" type="range" min="0" max="{g["valid_frames"]-1}" step="1" value="0">'
                     '<output>第0帧</output></div></div>' + thumbs + appearance + score_table + event_section
                     + execution_note + prompt + evidence + "</section>")
        built.append({"source_id": sid, "new_output_present": new_ready})
    text = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>时序引导与相位对齐：五组同帧对照</title><style>
*{box-sizing:border-box}body{font:16px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;margin:0;background:#f2f4f7;color:#172033}
main{max-width:1540px;margin:auto;padding:28px}h1{font-size:28px}h2{font-size:22px}section{background:white;border:1px solid #dbe1e8;border-radius:12px;margin:26px 0;padding:20px}
.meta{color:#526073}.four{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:2px;background:black}
figure{margin:0;min-width:0;background:#000;color:#fff}video,.pending{width:100%;aspect-ratio:16/9;display:block;object-fit:contain;background:#000}.pending{display:flex;align-items:center;justify-content:center;color:#abb7c7;font-size:14px}
figcaption{background:#000;text-align:center;padding:12px 4px;font-size:16px;white-space:nowrap}
.controls{display:flex;align-items:center;gap:10px;padding:12px 0}.controls input{flex:1;min-width:40px}button{padding:7px 12px;border:1px solid #aab5c5;border-radius:6px;background:white;color:#172033;cursor:pointer}
.comparison:fullscreen{background:#101319;padding:20px;display:flex;justify-content:center;flex-direction:column;color:white}.comparison:fullscreen .four{width:100%}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px}td,th{border:1px solid #dce2ea;padding:8px;text-align:left}th{background:#f6f8fa}pre{white-space:pre-wrap;background:#f4f6f9;padding:14px;font-size:13px}code{overflow-wrap:anywhere}
.shots{display:flex;gap:8px;overflow-x:auto;margin:12px 0}.shots a{flex:0 0 300px;font-size:12px}.shots img{width:100%;display:block}a{color:#225e9e}.note{background:#eaf1f7;padding:16px;border-left:4px solid #4681b3}
@media(max-width:760px){main{padding:12px}section{padding:10px}.four{min-width:800px}.comparison{overflow:auto}table{font-size:11px}figcaption{font-size:14px}}
</style><main><h1>时序引导与相位对齐：五组同帧对照</h1>
<p class="note">普通编辑使用原 H3；时序引导复用各例已完成的固定时间窗与第 6–14 步参数。时序引导先限定参考视频的物理时间区间；组合版在同一额外参考注意力分支中修正 Q 的时间原点相位，改变该区间内的内容选择，原联合注意力保持不变。额外动作时间收益按实际事件区间评估，姿态与外观变化单独记录。四列并列历史对照与本轮 R148 组合输出。</p>
""" + "".join(cards) + """<p>本页独立于用户手改研究报告。媒体引用已有文件，不内嵌大视频；请保留这些原文件路径。历史离线指标直接复用，新组合版完成后只做最终离线评价。</p></main>
<script>
document.querySelectorAll('.comparison').forEach(group=>{
 const videos=[...group.querySelectorAll('video')],source=videos[0],range=group.querySelector('input'),label=group.querySelector('output'),fps=Number(group.dataset.fps),duration=Number(group.dataset.duration);
 if(!source)return;
 const pause=()=>videos.forEach(v=>v.pause());
 const seek=frame=>{const t=frame/fps;videos.forEach(v=>{v.currentTime=t;v.playbackRate=1});range.value=frame;label.textContent=`第${frame}帧 · ${t.toFixed(3)}秒`};
 group.querySelector('.play').onclick=async()=>{
  pause();if(source.currentTime>=duration-1/fps)seek(0);
  const t=source.currentTime;
  await Promise.all(videos.map(v=>new Promise(resolve=>{
   v.preload='auto';v.currentTime=t;v.playbackRate=1;
   if(v.readyState>=3)resolve();else v.addEventListener('canplay',resolve,{once:true});
  })));
  await Promise.all(videos.map(v=>v.play().catch(()=>{})));
 };
 group.querySelector('.pause').onclick=pause;range.oninput=()=>{pause();seek(Number(range.value))};
 group.querySelector('.fullscreen').onclick=()=>group.requestFullscreen?.();
 const sync=()=>{if(source.currentTime>=duration){pause();seek(Number(range.max));return}const f=Math.min(Number(range.max),Math.floor(source.currentTime*fps));range.value=f;label.textContent=`第${f}帧 · ${(f/fps).toFixed(3)}秒`;if(!source.paused)videos.slice(1).forEach(v=>{if(Math.abs(v.currentTime-source.currentTime)>0.5/fps)v.currentTime=source.currentTime})};
 source.ontimeupdate=sync;
 const tick=()=>{sync();if(!source.paused)requestAnimationFrame(tick)};
 source.onplay=()=>requestAnimationFrame(tick);
});
</script></html>"""
    out = ROOT / "index.html"
    out.write_text(text)
    receipt = {"schema": "r148-independent-html-build-v1", "manifest": bound(ROOT / "EVALUATION_MANIFEST.json"),
               "html": bound(out), "cases": built, "embedded_media": False, "manual_report_modified": False}
    (ROOT / "HTML_BUILD.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt["html"]))


if __name__ == "__main__":
    main()
