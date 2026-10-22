#!/usr/bin/env python3
"""Render explicitly bound local evaluation evidence as one self-contained HTML."""
import argparse
import base64
import copy
import hashlib
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = ROOT.parent / "EVALUATION_PLAN.json"
SCHEMA = "r144-showcase-v1"
ROLES = {"source": "参考视频", "native": "普通编辑", "automatic": "自动引导",
         "fixed": "固定引导"}
CASES = {
    "short_0358": ("饮酒 · 添加眼镜", "完整上下文提示词"),
    "long_0039": ("取书 · 书本改为蓝色", "简短编辑提示词（通用保留语句）"),
    "long_0059": ("擦眼 · 添加白色手帕", "完整上下文提示词"),
}
TRANSLATIONS = {
    "bottle lowered": "放下酒瓶",
    "bottle reaches lips / drinking begins": "酒瓶碰唇 / 开始饮酒",
    "bottle leaves lips": "酒瓶离唇",
    "hand_approaches_eye": "手靠近眼部",
    "eye_wiping_contact": "接触眼部擦拭",
    "hand_leaves_face": "手离开脸部",
}
MIME = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bound(path):
    path = Path(path).resolve()
    return {"file": str(path), "sha256": sha(path.read_bytes())}


def read_bound(record):
    require(isinstance(record, dict), "File binding must be an object")
    path = Path(record["file"])
    require(path.is_absolute() and path.is_file(), f"Missing absolute local file: {path}")
    data = path.read_bytes()
    require(sha(data) == record["sha256"], f"SHA256 mismatch: {path}")
    return data


def load_bound(record):
    return json.loads(read_bound(record))


def same_file(left, right):
    return (Path(left["file"]).resolve(), left["sha256"]) == (
        Path(right["file"]).resolve(), right["sha256"])


def evidence(records):
    require(isinstance(records, list) and records, "Nonempty evidence bindings required")
    for record in records:
        read_bound(record)


def interval(value, valid_frames):
    if value is None:
        return None
    require(isinstance(value, list) and len(value) == 2
            and all(type(x) is int for x in value)
            and 0 <= value[0] <= value[1] < valid_frames, f"Invalid frame interval: {value}")
    return value


def delay(source, edited):
    """Signed difference, identical interval arithmetic to event_scores.py."""
    if source is None or edited is None:
        return None
    return {"midpoint": (sum(edited) - sum(source)) / 2,
            "bounds": [edited[0] - source[1], edited[1] - source[0]]}


def normalize_event(event):
    row = {"id": event.get("id", event["name"]),
           "label": TRANSLATIONS.get(event["name"], event["name"])}
    for role, old_role in (("source", "source"), ("native", "native"), ("fixed", "forced")):
        value = event.get(f"{old_role}_frames")
        if value is None and isinstance(event.get(old_role), dict):
            value = event[old_role].get("frames")
        row[role] = value
    row["automatic"] = None
    return row


def draft_manifest(plan_path, history_report=None):
    plan_record = bound(plan_path)
    plan = load_bound(plan_record)
    cases = []
    for case in plan["cases"]:
        sid = case["source_id"]
        title, prompt_type = CASES[sid]
        binding = {"file": case["input_binding"], "sha256": case["input_binding_sha256"]}
        prompt = load_bound(binding)["prompt"]
        cases.append({
            "source_id": sid, "title": title, "prompt_type": prompt_type,
            "prompt": {"text": prompt, "sha256": case["prompt_sha256"], "evidence": binding},
            "inputs": {**{r: case[r] for r in ("source", "native", "fixed")}, "automatic": None},
            "frame_ledger": None, "media": {"automatic": None, "fixed": None},
            "screenshots": [], "control": None,
            "events": {"evidence": [plan_record],
                       "rows": [normalize_event(e) for e in
                                case["events_selected_before_automatic_output"]["events"]]},
            "mf": {"protocol": "IVEBench official MF", "evidence": [plan_record],
                   "values": {"native": case["existing_motion_fidelity"]["native"],
                              "fixed": case["existing_motion_fidelity"]["guided"],
                              "automatic": None}},
            "conclusion": None,
        })
    return {"schema": SCHEMA, "title": "视频编辑中的动作时序",
            "plan": plan_record, "cases": cases,
            "history": ([{"kind": "r138", "report": bound(history_report)}]
                        if history_report else [])}


def bind_review(manifest, sid, ledger_path):
    case = next(c for c in manifest["cases"] if c["source_id"] == sid)
    record = bound(ledger_path)
    ledger = load_bound(record)
    require(ledger["source_id"] == sid, "Review ledger belongs to another case")
    case["frame_ledger"] = record
    case["inputs"]["automatic"] = ledger["automatic_binding"]["automatic"]
    for item in ledger["videos"]:
        role = item["role"]
        require(role in ("automatic", "fixed"), "Unexpected review video role")
        case["media"][role] = {**item, "columns": ["source", "native", role]}


def validate_current(case, planned, plan_record):
    sid = case["source_id"]
    require(case["prompt_type"] == CASES[sid][1], f"Prompt family changed: {sid}")
    prompt = case["prompt"]
    require(sha(prompt["text"].encode()) == prompt["sha256"] == planned["prompt_sha256"],
            "Original prompt SHA mismatch")
    prompt_binding = load_bound(prompt["evidence"])
    require(prompt_binding["source_id"] == sid and prompt_binding["prompt"] == prompt["text"],
            "Prompt evidence mismatch")
    for role in ("source", "native", "fixed"):
        require(same_file(case["inputs"][role], planned[role]), f"Input binding changed: {role}")
    supplied = any(case["media"].values()) or bool(case["screenshots"])
    ledger = None
    if case["frame_ledger"]:
        ledger = load_bound(case["frame_ledger"])
        require(ledger["source_id"] == sid and same_file(ledger["evaluation_plan"], plan_record),
                "Review ledger case/plan mismatch")
        require(ledger["automatic_binding"].get("verified_before_render") is True
                and ledger.get("frames_prepared") is True, "Verified review ledger required")
        require(same_file(case["inputs"]["automatic"], ledger["automatic_binding"]["automatic"]),
                "Automatic input differs from verified review ledger")
        for index, role in enumerate(("source", "native", "fixed", "automatic")):
            require(same_file(case["inputs"][role], ledger["inputs"][index]),
                    f"Review input mismatch: {role}")
        require(ledger["valid_frames"] == planned["geometry"]["valid_frames"]
                and ledger["fps"] == planned["geometry"]["fps"], "Review timebase mismatch")
    require(not supplied or ledger is not None, "Media require prepare_review FRAME_LEDGER.json")
    require(case["inputs"]["automatic"] is None or ledger is not None,
            "Automatic input requires verified review ledger")
    for role, media in case["media"].items():
        require(role in ("automatic", "fixed"), "Unknown media role")
        if media is None:
            continue
        require(media["columns"] == ["source", "native", role], "Unexpected comparison columns")
        require(any(v["role"] == role and same_file(media, v) for v in ledger["videos"]),
                "Video missing from review ledger")
    for still in case["screenshots"]:
        require(any(same_file(still, p) and still["physical_frames"] == p["physical_frames"]
                    for p in ledger["pages"]), "Screenshot/frame indices missing from review ledger")
        require(still["columns"] == ["source", "native", "fixed", "automatic"],
                "Review contact sheet has four columns")
    case["fps"] = planned["geometry"]["fps"]
    case["valid_frames"] = planned["geometry"]["valid_frames"]
    case["seed"] = planned["seed"]
    case["version"] = "R144 · 自动引导"
    require(ledger is not None or (case["control"] is None
            and case["mf"]["values"]["automatic"] is None
            and all(e.get("automatic") is None for e in case["events"]["rows"])),
            "Automatic measurements require a verified finished video")
    validate_measurements(case)
    return case


def validate_measurements(case):
    count = case["valid_frames"]
    evidence(case["events"]["evidence"])
    ids = []
    for row in case["events"]["rows"]:
        ids.append(row["id"])
        for role in ROLES:
            interval(row.get(role), count)
    require(len(ids) == len(set(ids)), "Duplicate event IDs")
    require(case["mf"]["protocol"] == "IVEBench official MF", "Expected official MF protocol")
    evidence(case["mf"]["evidence"])
    for value in case["mf"]["values"].values():
        require(value is None or (type(value) in (int, float) and math.isfinite(value)),
                "MF must be a finite number or null")
    control = case.get("control")
    if control is not None:
        evidence(control["evidence"])
        indices = []
        for decision in control["decisions"]:
            index = decision["step_0based"]
            require(type(index) is int and 0 <= index < 20, "Step must be an integer in 0..19")
            require(type(decision["on"]) is bool, "ON must be a JSON boolean")
            for window in decision["windows"]:
                interval(window, count)
            require(decision["on"] or not decision["windows"], "OFF step has active windows")
            require(not decision["on"] or bool(decision["windows"]), "ON step needs active windows")
            indices.append(index)
        require(len(indices) == len(set(indices)), "Duplicate step index")


def historical_r138(record):
    report = load_bound(record)
    require(report["status"] == "FINAL" and report["schema"] == "r138-final-report-handoff-v1",
            "Final R138 handoff required")
    media = {}
    for role, key in (("automatic", "source_native_visible_only"),
                      ("fixed_comparison", "source_fixed_visible_only")):
        item = report["comparison_media"][key]
        columns = ["automatic" if x == "visible_only" else x for x in item["columns"]]
        media[role] = {**item["videos"][0], "columns": columns}
    stills = []
    for item in report["comparison_media"]["source_native_visible_only"]["stills"]:
        stills.append({**item, "physical_frames": [item["physical_frame"]],
                       "columns": ["source", "native", "automatic"]})
    events = [
        {"id": e["id"], "label": e["name"], "source": e["source_frames"],
         "native": e["native_frames"], "fixed": e["fixed_frames"], "automatic": e["auto_frames"]}
        for e in report["events"]
    ]
    case = {
        "source_id": report["source_id"], "title": "机舱 · 人物替换",
        "version": "历史 R138 · 自动引导", "prompt_type": "P1 · 历史完整上下文提示词",
        "prompt": report["actual_prompt"], "seed": report["seed"],
        "fps": report["effective_domain"]["fps"],
        "valid_frames": report["effective_domain"]["valid_frames"],
        "media": media, "screenshots": stills, "conclusion": report["summary"],
        "events": {"rows": events, "evidence": [record]},
        "mf": {"protocol": "IVEBench official MF", "evidence": [record],
               "values": {r: report["official_MF"][old]["value"] for r, old in
                          (("native", "native"), ("fixed", "fixed"), ("automatic", "visible_only"))}},
        "control": {"evidence": [record], "decisions": [
            {"step_0based": d["physical_index_0based"], "on": d["actual_ON"],
             "windows": d["ON_frame_windows"]} for d in report["control"]["decisions_0based"]]},
    }
    require(sha(case["prompt"]["text"].encode()) == case["prompt"]["sha256"], "R138 prompt SHA mismatch")
    validate_measurements(case)
    return case


def prepare(manifest):
    require(manifest["schema"] == SCHEMA, "Unknown showcase schema")
    plan = load_bound(manifest["plan"])
    planned = {c["source_id"]: c for c in plan["cases"]}
    ids = [c["source_id"] for c in manifest["cases"]]
    require(len(ids) == 3 and set(ids) == set(CASES), "Exactly the three R144 cases are required")
    current = [validate_current(copy.deepcopy(c), planned[c["source_id"]], manifest["plan"])
               for c in manifest["cases"]]
    history = []
    for item in manifest.get("history", []):
        require(item["kind"] == "r138", "Only the supplied historical R138 adapter is registered")
        history.append(historical_r138(item["report"]))
    return current, history


def escape(value):
    return html.escape(str(value), quote=True)


def number(value, digits=1):
    return f"{value:.{digits}f}".rstrip("0").rstrip(".") if digits else str(int(value))


def frames(value):
    return "待评估" if value is None else f"{value[0]}–{value[1]}"


def lag_text(source, edited):
    result = delay(source, edited)
    if result is None:
        return "待评估"
    midpoint = result["midpoint"]
    sign = "+" if midpoint > 0 else ""
    lo, hi = result["bounds"]
    return f"{sign}{number(midpoint)} 帧 <small>区间 {number(lo)} 至 {number(hi)}</small>"


def event_table(case):
    rows = []
    for row in case["events"]["rows"]:
        cells = [f'<th scope="row">{escape(row["label"])}</th>',
                 f'<td>{frames(row.get("source"))}</td>']
        for role in ("native", "fixed", "automatic"):
            cells.append(f'<td>{lag_text(row.get("source"), row.get(role))}'
                         f'<small>事件帧 {frames(row.get(role))}</small></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return ('<div class="table-scroll"><table><thead><tr><th>可见事件</th><th>参考事件帧</th>'
            '<th>普通编辑帧差</th><th>固定引导帧差</th><th>自动引导帧差</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table></div>'
            f'<p class="note">帧差为事件区间中点差；正值表示延后。{case["fps"]} fps，物理帧从 0 编号。</p>')


def control_html(case):
    decisions = {d["step_0based"]: d for d in (case.get("control") or {}).get("decisions", [])}
    cells = []
    for index in range(20):
        decision = decisions.get(index)
        state = "待评估" if decision is None else ("ON" if decision["on"] else "OFF")
        windows = "" if decision is None else "，窗口 " + ("、".join(
            frames(w) for w in decision["windows"]) or "无")
        css = "pending" if decision is None else ("on" if decision["on"] else "off")
        cells.append(f'<span class="step {css}" title="{index}：{state}{windows}">'
                     f'<b>{index}</b>{state}</span>')
    active = [d for d in decisions.values() if d["on"]]
    details = "；".join(f'步骤 {d["step_0based"]}：'
                       + ("、".join(frames(w) for w in d["windows"]) or "窗口待评估") for d in active)
    if not decisions:
        details = "实际开关记录待评估"
    elif len(decisions) == 20 and not active:
        details = "20 个步骤均为 OFF"
    elif len(decisions) < 20:
        details = (details + "；" if details else "") + "其余步骤待评估"
    return '<div class="steps">' + "".join(cells) + f'</div><p class="note">{escape(details)}</p>'


CSS = """
:root{color-scheme:dark;--bg:#101316;--panel:#191e23;--line:#323a42;--text:#eff2f4;--muted:#aeb8c2;--accent:#9de0ca}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 system-ui,-apple-system,"PingFang SC",sans-serif}
main{max-width:1920px;margin:auto;padding:38px 36px 60px}h1{font-size:34px;margin:0 0 10px}h2{font-size:26px;margin:0}h3{font-size:17px;margin:24px 0 10px}
p{margin:8px 0}.intro,.note,small,.meta{color:var(--muted)}.intro{max-width:1000px}.note{font-size:13px}.section-title{margin:42px 0 16px;border-bottom:1px solid var(--line);padding-bottom:12px}
.case{padding:24px;background:var(--panel);border:1px solid var(--line);border-radius:14px;margin-bottom:28px}.case-head{display:flex;gap:20px;align-items:start;justify-content:space-between}.badge{font-size:13px;color:var(--accent);white-space:nowrap;border:1px solid #46695f;border-radius:30px;padding:5px 12px}.meta{font-size:14px;margin:6px 0 18px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 10px}button{font:inherit;color:var(--text);background:#242c32;border:1px solid #45515c;border-radius:7px;padding:7px 14px;cursor:pointer}button[aria-pressed=true]{background:#21443a;border-color:var(--accent);color:#c8ffec}button:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}.column-labels{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;background:#050505;text-align:center;font-size:14px;padding:10px 0;border-bottom:1px solid #222}
.video-shell{background:#000;border-radius:6px;overflow:hidden}video{display:block;width:100%;height:auto;max-height:76vh;background:#000}.empty{display:flex;justify-content:center;align-items:center;min-height:220px;color:#a5adb5;background:#000}.view[hidden]{display:none}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}.stat{padding:13px 16px;border:1px solid var(--line);border-radius:8px}.stat b{display:block;font-size:24px;font-weight:600;font-variant-numeric:tabular-nums}.stat span{font-size:13px;color:var(--muted)}.stat.auto{border-color:#53786b}.conclusion{border-left:3px solid var(--accent);padding:7px 14px;margin:18px 0}
details{margin-top:12px}summary{cursor:pointer;color:var(--muted)}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.5;background:#111519;padding:16px;border-radius:6px}.table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:12px 10px;vertical-align:top}thead th{color:var(--muted);font-weight:500}tbody th{max-width:290px;font-weight:500}small{display:block;font-size:12px}.steps{display:grid;grid-template-columns:repeat(20,minmax(0,1fr));gap:5px}.step{display:flex;flex-direction:column;text-align:center;border-radius:5px;padding:7px 0;font-size:11px;border:1px solid #454d55}.step b{font-size:13px}.step.on{background:#28594a;color:#caffeb;border-color:#95d6bf}.step.off{background:#252d34;color:#d1dae2}.step.pending{color:#89939d;border-style:dashed}
.stills{display:grid;gap:18px}figure{margin:0}figure img{display:block;width:100%;height:auto;background:black}figcaption{font-size:13px;color:var(--muted);margin:6px 0}.history-note{color:var(--muted);font-size:14px}.evidence{font-size:12px;overflow-wrap:anywhere}footer{font-size:13px;color:var(--muted);margin-top:28px}
@media(max-width:800px){main{padding:22px 12px}h1{font-size:27px}h2{font-size:22px}.case{padding:14px}.case-head{display:block}.badge{display:inline-block;margin:8px 0}.steps{grid-template-columns:repeat(10,minmax(0,1fr))}.stats{gap:5px}.stat{padding:9px}.stat b{font-size:20px}.empty{min-height:150px}}
"""
JS = """
document.querySelectorAll('.case').forEach(card=>{
  card.querySelectorAll('button[data-view]').forEach(button=>button.addEventListener('click',()=>{
    const current=card.querySelector('.view:not([hidden]) video');
    const time=current?current.currentTime:0;
    const playing=current&&!current.paused;
    card.querySelectorAll('video').forEach(v=>v.pause());
    card.querySelectorAll('.view').forEach(view=>view.hidden=view.dataset.view!==button.dataset.view);
    card.querySelectorAll('button[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    const next=card.querySelector('.view:not([hidden]) video');
    if(next){
      const restore=()=>{next.currentTime=Math.min(time,Number.isFinite(next.duration)?next.duration:time);if(playing)next.play().catch(()=>{});};
      if(next.readyState>=1)restore();else next.addEventListener('loadedmetadata',restore,{once:true});
    }
  }));
});
document.querySelectorAll('video').forEach(v=>v.addEventListener('play',()=>{
  document.querySelectorAll('video').forEach(other=>{if(other!==v)other.pause();});
}));
"""


def render(manifest, embed=True):
    current, history = prepare(manifest)
    assets = {}

    def asset(record):
        path = Path(record["file"])
        require(path.suffix.lower() in MIME, f"Unsupported media: {path}")
        key = (str(path), record["sha256"])
        if key not in assets:
            data = read_bound(record)
            assets[key] = ("data:" + MIME[path.suffix.lower()] + ";base64,"
                           + base64.b64encode(data).decode()) if embed else ""
        return assets[key]

    def card(case):
        tabs, views = [], []
        media = case["media"]
        for index, (role, item) in enumerate(media.items()):
            columns = item["columns"] if item else ["source", "native", role]
            label = " / ".join(ROLES[r] for r in columns)
            tabs.append(f'<button type="button" data-view="{escape(role)}" '
                        f'aria-pressed="{str(index == 0).lower()}">{escape(label)}</button>')
            labels = "".join(f"<span>{ROLES[r]}</span>" for r in columns)
            content = (f'<video controls playsinline preload="metadata" '
                       f'aria-label="{escape(case["title"] + " · " + label)}" src="{asset(item)}"></video>'
                       if item else '<div class="empty">成片待评估</div>')
            views.append(f'<div class="view" data-view="{escape(role)}"'
                         + (" hidden" if index else "") + '><div class="video-shell">'
                         + f'<div class="column-labels">{labels}</div>{content}</div></div>')
        stats = []
        for role in ("native", "fixed", "automatic"):
            value = case["mf"]["values"].get(role)
            formatted = "待评估" if value is None else f"{value:.4f}"
            stats.append(f'<div class="stat {"auto" if role == "automatic" else ""}">'
                         f'<span>{ROLES[role]} · 官方 MF ↑</span><b>{formatted}</b></div>')
        stills = []
        for item in case["screenshots"]:
            label = " / ".join(ROLES[r] for r in item["columns"])
            indices = "、".join(str(f) for f in item["physical_frames"])
            caption = item.get("caption") or f"物理帧 {indices} · {label}"
            stills.append(f'<figure><img loading="lazy" src="{asset(item)}" '
                          f'alt="{escape(caption)}"><figcaption>{escape(caption)}</figcaption></figure>')
        still_html = ('<div class="stills">' + "".join(stills) + "</div>"
                      if stills else '<p class="note">同帧截图待评估</p>')
        record_names = []
        for group in (case["events"], case["mf"], case.get("control")):
            if group:
                record_names.extend(f'{r["file"]} · SHA256 {r["sha256"]}' for r in group["evidence"])
        provenance = "<br>".join(escape(s) for s in dict.fromkeys(record_names))
        return (f'<article class="case" id="{escape(case["source_id"])}">'
                f'<div class="case-head"><h2>{escape(case["title"])}</h2>'
                f'<span class="badge">{escape(case["version"])}</span></div>'
                f'<p class="meta">{escape(case["prompt_type"])} · {case["valid_frames"]} 有效帧 · '
                f'{case["fps"]} fps · seed {case["seed"]}</p>'
                + '<div class="tabs">' + "".join(tabs) + "</div>" + "".join(views)
                + '<div class="stats">' + "".join(stats) + "</div>"
                + f'<p class="conclusion">{escape(case.get("conclusion") or "自动引导结果待评估")}</p>'
                + '<h3>动作时序</h3>' + event_table(case)
                + '<h3>自动引导的实际开关 · 步骤 0–19</h3>' + control_html(case)
                + '<h3>同帧对照</h3>' + still_html
                + '<details><summary>原始提示词</summary><pre>'
                + escape(case["prompt"]["text"]) + '</pre></details>'
                + '<details><summary>数据记录</summary><p class="evidence">'
                + provenance + '</p></details></article>')

    current_html = "".join(card(c) for c in current)
    history_html = ""
    if history:
        history_html = ('<h2 class="section-title">历史机舱对照</h2>'
                        '<p class="history-note">R138 自动引导使用 P1 历史完整上下文提示词；'
                        '本节固定对照为同提示词的历史固定版。R141b 固定引导使用简短提示词，单独登记。</p>'
                        + "".join(card(c) for c in history))
    page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(manifest["title"])}</title><style>{CSS}</style></head><body><main>'
            f'<h1>{escape(manifest["title"])}</h1>'
            '<p class="intro">同帧观看参考视频、普通编辑与自动引导。切换固定引导对照，'
            '结合事件帧差、实际开关步骤与官方 Motion Fidelity 评估结果。</p>'
            '<h2 class="section-title">本次三例 · R144</h2>' + current_html + history_html
            + '<footer>视频与截图已嵌入本文件，可离线查看。MF 越高越好；各例按各自有效帧域评估。</footer>'
            f'</main><script>{JS}</script></body></html>')
    return page, {"cases": len(current), "historical_cases": len(history),
                  "embedded_assets": len(assets), "manifest_sha256": sha(
                      json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode())}


def output_path(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT), f"Outputs must stay inside {ROOT}")
    require(not path.exists(), f"Output already exists; choose a new name: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--init", type=Path, help="Write an explicit draft manifest; missing results stay null")
    source.add_argument("--manifest", type=Path)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--history-report", type=Path, help="Include the supplied final R138 handoff")
    parser.add_argument("--bind-review", metavar="SOURCE_ID=FRAME_LEDGER", action="append", default=[])
    parser.add_argument("--save-manifest", type=Path, help="Write newly bound manifest to a fresh path")
    parser.add_argument("--output", type=Path, default=ROOT / "index.html")
    parser.add_argument("--check", action="store_true", help="Validate evidence/assets without writing HTML")
    args = parser.parse_args()
    if args.init:
        require(not args.bind_review and not args.save_manifest, "Initialize before binding review media")
        manifest = draft_manifest(args.plan, args.history_report)
        path = output_path(args.init)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"manifest": str(path), "sha256": bound(path)["sha256"]}))
        return
    require(args.history_report is None, "--history-report is used with --init")
    manifest = json.loads(args.manifest.read_text())
    for assignment in args.bind_review:
        sid, path = assignment.split("=", 1)
        bind_review(manifest, sid, path)
    require(not args.bind_review or args.save_manifest, "--bind-review requires --save-manifest")
    page, result = render(manifest, embed=not args.check)
    if args.save_manifest:
        target = output_path(args.save_manifest)
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        result["saved_manifest"] = str(target)
    if not args.check:
        target = output_path(args.output)
        target.write_text(page)
        result.update({"html": str(target), "bytes": target.stat().st_size,
                       "html_sha256": bound(target)["sha256"]})
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
