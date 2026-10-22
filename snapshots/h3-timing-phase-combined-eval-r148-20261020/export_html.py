"""Portable five-case display. Embed one validated four-way video per case."""
import argparse
import base64
from html import escape, unescape
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse

from prepare_comparison import ROOT, bound, read, require


def data_uri(path, mime):
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def controls(video_uri, poster_uri, frames, fps):
    return (
        f'<div class="comparison portable" data-fps="{fps}">'
        '<div class="video-scroll">'
        f'<video muted playsinline preload="metadata" poster="{poster_uri}" src="{video_uri}"></video>'
        '</div><div class="controls"><button class="play">原速播放</button>'
        '<button class="pause">暂停</button><button class="fullscreen">全屏</button>'
        f'<input aria-label="同帧定位" type="range" min="0" max="{frames-1}" step="1" value="0">'
        '<output>第0帧</output></div></div>'
    )


def validate_result(case, presentation, review):
    require(presentation["evaluation_manifest"] == bound(ROOT / "EVALUATION_MANIFEST.json"),
            "Presentation belongs to another manifest")
    require(presentation["valid_frames"] == case["geometry"]["valid_frames"], "Frame domain differs")
    actual = presentation["inputs"]["fixed_phase"]["sha256"]
    require(review["combined_video_sha256"] == actual
            and review["all_valid_frames_inspected"] is True
            and review["valid_frames"] == presentation["valid_frames"], "Complete actual review required")
    require(bound(presentation["video"]["file"]) == presentation["video"], "Comparison video changed")
    return actual


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--preview", action="store_true",
                        help="Permit pending cases, write only inside this evaluation project")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    require(not output.exists(), "Refuse overwriting an existing HTML")
    require(output.is_relative_to(ROOT) or (output.parent == Path.home() / "Downloads"
            and output.name.startswith("时序引导与相位对齐_五组对照_R148_")),
            "Only evaluation files or a uniquely named R148 Downloads artifact may be written")
    require(not args.preview or output.is_relative_to(ROOT), "Preview must remain in evaluation directory")
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    text = (ROOT / "index.html").read_text()
    evidence = []
    ready = 0
    for case in manifest["cases"]:
        sid = case["source_id"]
        match = re.search(rf'<section id="{re.escape(sid)}">.*?</section>', text, flags=re.S)
        require(match is not None, "Case missing from built page")
        section = match.group()
        path = ROOT / "review" / sid / "PRESENTATION.json"
        if not path.exists():
            require(args.preview, "All five validated outputs are required for final export")
            section = re.sub(r'<div class="comparison".*?</div></div>', '<p>此组尚待成片。</p>',
                             section, count=1, flags=re.S)
        else:
            presentation = read(path)
            review_path = path.with_name("REVIEW.json")
            review = read(review_path)
            actual = validate_result(case, presentation, review)
            shots = presentation["screenshots"]
            first = shots[0]
            replacement = controls(data_uri(presentation["video"]["file"], "video/mp4"),
                                   data_uri(first["file"], "image/jpeg"),
                                   presentation["valid_frames"], presentation["fps"])
            section, count = re.subn(r'<div class="comparison".*?</div></div>', replacement,
                                     section, count=1, flags=re.S)
            require(count == 1, "Unexpected comparison HTML structure")
            evidence.append({"source_id": sid, "actual_video_sha256": actual,
                             "presentation": bound(path), "review": bound(review_path),
                             "embedded_comparison": presentation["video"]})
            ready += 1
        reference = case.get("reference_image")
        if reference:
            require(bound(reference["file"])["sha256"] == reference["sha256"], "Reference image changed")
            # Embed the supplied portrait as a small provenance thumbnail, not a new rendering.
            from PIL import Image
            import io
            image = Image.open(reference["file"]).convert("RGB")
            image.thumbnail((160, 160))
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=82)
            uri = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
            section = section.replace("</section>", '<details><summary>人物参考图</summary>'
                f'<img width="{image.width}" height="{image.height}" src="{uri}" alt="历史 Sam 人物参考图">'
                f'<p>沿用历史人物参考图，SHA256：<code>{reference["sha256"]}</code></p></details></section>')
        else:
            section = section.replace("</section>", "<p class=\"meta\">参考条件：源视频；未添加独立人物参考图。</p></section>")
        text = text[:match.start()] + section + text[match.end():]
    # Only representative stills remain in src attributes after replacing the raw videos.
    def embed_image(match):
        path = Path(unquote(urlparse(unescape(match.group(1))).path))
        require(path.suffix.lower() in (".jpg", ".jpeg", ".png"), "Unexpected unembedded media")
        return 'src="' + data_uri(path, "image/png" if path.suffix == ".png" else "image/jpeg") + '"'
    text = re.sub(r'src="(file:[^"]+)"', embed_image, text)
    text = re.sub(r'href="file:[^"]+"', 'href="#evidence"', text)
    text = re.sub(r'<script>.*?</script>', SCRIPT, text, flags=re.S)
    text = text.replace("</style>", """
.portable video{width:100%;aspect-ratio:1920/324;height:auto}
.video-scroll{overflow-x:auto;background:black}.portable:fullscreen .video-scroll{width:100%}
@media(max-width:760px){.portable video{min-width:960px}.portable .controls{min-width:500px}}
</style>""")
    text = text.replace("媒体引用已有文件，不内嵌大视频；请保留这些原文件路径。",
                        "五组四列视频与同帧截图均内嵌本文件，可离线查看与复制。")
    text = text.replace("</main>", '<details id="evidence"><summary>文件与评审证据</summary><pre>' +
                        escape(json.dumps(evidence, ensure_ascii=False, indent=2)) + "</pre></details></main>")
    require('src="file:' not in text and 'poster="file:' not in text, "External local media remains")
    require(text.count('src="data:video/mp4;base64,') == ready, "Embedded video count differs")
    require(args.preview or ready == 5, "Final display requires five completed cases")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    receipt = {"schema": "r148-portable-html-export-v1", "preview": args.preview,
               "html": bound(output), "bytes": output.stat().st_size, "embedded_videos": ready,
               "all_media_embedded": True, "original_speed": 1, "inputs": evidence,
               "manual_report_modified": False}
    (ROOT / "audit" / ("PORTABLE_PREVIEW.json" if args.preview else "PORTABLE_EXPORT.json")).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: receipt[k] for k in ("html", "bytes", "embedded_videos", "preview")}))


SCRIPT = """<script>
document.querySelectorAll('.portable').forEach(group=>{
 const v=group.querySelector('video'),range=group.querySelector('input'),label=group.querySelector('output'),fps=+group.dataset.fps;
 const seek=f=>{v.pause();v.currentTime=f/fps;range.value=f;label.textContent=`第${f}帧 · ${(f/fps).toFixed(3)}秒`};
 group.querySelector('.play').onclick=()=>{v.playbackRate=1;if(v.ended)v.currentTime=0;v.play().catch(()=>{})};
 group.querySelector('.pause').onclick=()=>v.pause();
 group.querySelector('.fullscreen').onclick=()=>group.requestFullscreen?.();
 range.oninput=()=>seek(+range.value);
 const update=()=>{const f=Math.min(+range.max,Math.floor(v.currentTime*fps));range.value=f;label.textContent=`第${f}帧 · ${(f/fps).toFixed(3)}秒`;if(!v.paused)requestAnimationFrame(update)};
 v.onplay=update;v.ontimeupdate=update;
});
</script>"""


if __name__ == "__main__":
    main()
