#!/usr/bin/env python3
"""Assemble exactly four verified, normal-speed triptychs without re-encoding.

Source experiment roots are strictly read-only. Until all four comparisons are
ready, only this task's status files are written; Downloads is never staged with
partial or substituted media. Requires Python stdlib and existing ffprobe.
"""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DELIVERY = Path("/Users/researcher/Downloads/H3_四组短动作对照_Musk_Sam_20261015")
ZIP_PATH = DELIVERY.with_suffix(".zip")
BASE = Path("/Users/researcher/DevProjects")
CAPTIONS = ["1.参考视频", "2.编辑后视频", "3.编辑＋短时动作三倍加权后视频"]
SPECS = [
    {"id": "01_Musk05", "title": "Musk · 室内书记舞（05）", "root": "h3-musk-real-dance-pair-20261014",
     "video": "comparison_frames_040-100.mp4", "preview": "caption_style_frame_056.png", "preview_frame": 56,
     "control": "pair_verification.json", "case": None, "runs": ["05_musk_s1_baseline", "05_musk_s1_weight3"],
     "formal_count": 2, "host": "192.0.2.1", "review_scope": "Existing extensive non-blind frame review of this one pair."},
    {"id": "02_Musk07", "title": "Musk · 床边书记舞（07）", "root": "h3-musk-bedside-pair-20261014",
     "video": "comparison_short.mp4", "preview": "comparison_preview_frame_061.png", "preview_frame": 61,
     "control": "pair_verification.json", "case": None, "runs": ["07_musk_s1_baseline", "07_musk_s1_weight3"],
     "formal_count": 2, "host": "192.0.2.1", "review_scope": "Limited preview/file spot checks only; no comprehensive visual or efficacy assessment."},
    {"id": "03_Sam05", "title": "Sam · 室内书记舞（05）", "root": "h3-sam-real-dance-batch-20261015",
     "video": "05_sam_short_triptych.mp4", "preview": "05_sam_preview_frame_056.png", "preview_frame": 56,
     "control": "batch_verification.json", "case": "05", "runs": ["05_sam_s1_baseline", "05_sam_s1_weight3"],
     "formal_count": 4, "host": "192.0.2.1", "review_scope": "Limited preview/file spot checks only; no comprehensive visual or efficacy assessment."},
    {"id": "04_Sam07", "title": "Sam · 床边书记舞（07）", "root": "h3-sam-real-dance-batch-20261015",
     "video": "07_sam_short_triptych.mp4", "preview": "07_sam_preview_frame_061.png", "preview_frame": 61,
     "control": "batch_verification.json", "case": "07", "runs": ["07_sam_s1_baseline", "07_sam_s1_weight3"],
     "formal_count": 4, "host": "192.0.2.1", "review_scope": "Limited preview/file spot checks only; no comprehensive visual or efficacy assessment."},
]
README = """四组短动作对照：Musk / Sam

本包只有4段正常速度横向三栏短视频与4张对应预览。人物替换画面均为AI编辑实验，不是真人表演记录。

顺序
01_Musk05.mp4：Musk，室内书记舞05。
02_Musk07.mp4：Musk，床边书记舞07。
03_Sam05.mp4：Sam，室内书记舞05。
04_Sam07.mp4：Sam，床边书记舞07。

每段均为1968×416、61帧、24fps，约2.541667秒；取各完整原始三路视频的零起始40–100帧。三列保持相同帧号，完整画幅等比例显示。装配阶段仅逐字节复制，不重编码、不独立移动时间、不插帧。底栏沿用“角色替换 / 1.参考视频 / 2.编辑后视频 / 3.编辑＋短时动作三倍加权后视频”，视频内不新增时间或帧号。完整帧索引和SHA-256保留在manifest.json中。

检查与结论范围
本包仅展示短时间窗，不能据此判断某动作在完整输出中完全缺失；完整141帧原始视频仍保存在各实验归档中。
各来源控制报告必须为pass，渲染清单必须ready，文件哈希、帧数、几何和时间戳必须通过，才会装配四段。
Musk05已有详细的非盲AI逐帧评审：该固定种子配对中，两版均有目标动作，三倍版时序更接近源片但部分阶段略早；精确手指形状改善未确立。这一观察只属于该组，不能推广至另外三组。
Musk07和两组Sam按用户要求只安排有限的预览抽查和文件检查，不含完整逐帧视觉评审；不据此宣称加权有效、全部身份一致或整体画质良好。抽查是否完成以各来源的renderer QA记录为准，未记录者不能视为已经完成。
Musk05在.41运行，其余三组在.9运行。每组内对照由各自控制报告核验；跨组机器与运行环境不同，不能把跨组差异仅归因于人物或场景。

打开index.html观看。CREDITS.txt记录照片及两段舞蹈来源。manifest.json记录全部内容文件的SHA-256与字节数，SHA256SUMS也覆盖manifest.json；装配核验与ZIP哈希保存在装配任务目录的assembly_verification.json。
"""
CREDITS = """人物参考照片
Elon Musk portrait — Debbie Rowe / The Royal Society，Wikimedia Commons，CC BY-SA 3.0。
https://commons.wikimedia.org/wiki/File:Elon_Musk_Royal_Society.jpg
https://creativecommons.org/licenses/by-sa/3.0/

Sam Altman November 2022 — Village Global，2022-11-17，Wikimedia Commons，CC BY 2.0。
https://commons.wikimedia.org/wiki/File:Sam_Altman_November_2022.jpg
https://www.flickr.com/photos/villageglobal/52530764101/
https://creativecommons.org/licenses/by/2.0/

舞蹈来源
05：Megumi 原上传，已有实验输入取37.0–42.875秒。
https://www.youtube.com/watch?v=3vd5c8XMP9c
07：Ary Vilchis，Kaguya Sama Love is War Fujiwara Chika Dance Cover，已有实验输入取34.5–40.375秒。
https://www.youtube.com/watch?v=oPnUDTAG0_0
已有来源记录未确立舞蹈视频的宽松再许可。

Musk/Sam人物画面均为基于上述参考的AI身份编辑实验，不是真人跳舞记录。四段展示视频由各实验已完成的对照文件逐字节复制；本装配器未修改照片、视频内容或中文底栏。
"""


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text())


def signature(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def probe(path, frames, size):
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("Existing ffprobe is required; no dependency installation is attempted")
    result = subprocess.run(
        [executable, "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_frames",
         "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames,duration:frame=best_effort_timestamp_time",
         "-of", "json", str(path)], check=True, capture_output=True, text=True, timeout=180)
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    info = {"width": stream["width"], "height": stream["height"], "frames": int(stream["nb_read_frames"]),
            "fps": str(Fraction(stream["avg_frame_rate"])), "duration": float(stream["duration"])}
    if (info["width"], info["height"], info["frames"], info["fps"]) != (*size, frames, "24"):
        raise ValueError("Unexpected video size/frame count/FPS: " + str(path))
    if abs(info["duration"] - frames / 24) > 1e-5:
        raise ValueError("Duration differs from frame count / 24")
    times = [float(frame["best_effort_timestamp_time"]) for frame in data["frames"]]
    if len(times) != frames or any(abs(time - index / 24) > 1e-5 for index, time in enumerate(times)):
        raise ValueError("Video is not on the exact same-index 24 FPS grid")
    return info


def png_size(path):
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("Preview must be an existing PNG")
    return list(struct.unpack(">II", header[16:24]))


def inspect_case(spec):
    source_root = BASE / spec["root"]
    control_path = source_root / "analysis" / spec["control"]
    renderer_path = source_root / "review/manifest.json"
    video = source_root / "review" / spec["video"]
    preview = source_root / "review" / spec["preview"]
    required = [control_path, renderer_path, video, preview, source_root / "configs/plan.json"]
    missing = [str(path) for path in required if not path.is_file()]
    result = {"id": spec["id"], "title": spec["title"], "status": "pending", "problems": missing}
    if missing:
        return result
    control, renderer, plan = load(control_path), load(renderer_path), load(required[-1])
    pending = []
    if control.get("status") != "pass":
        pending.append("Control report status is " + str(control.get("status")))
    if renderer.get("status") != "ready":
        pending.append("Renderer manifest status is " + str(renderer.get("status")))
    case = renderer.get("cases", {}).get(spec["case"], {}) if spec["case"] else renderer
    if case.get("status") != "ready":
        pending.append("Case render is not ready")
    if pending:
        result["problems"] = pending
        return result
    if control.get("errors") or control.get("missing") or control.get("formal_count_passed") != spec["formal_count"]:
        raise ValueError("Control pass is incomplete or contradicts errors/missing/formal count")
    if not set(spec["runs"]).issubset(control.get("formal_run_ids", [])):
        raise ValueError("Control report does not cover the requested formal pair")
    if plan.get("actual_host") != spec["host"]:
        raise ValueError("Runtime host differs from the declared cross-case provenance")
    style = renderer.get("caption_style", {})
    if style.get("legend") != "角色替换" or style.get("column_captions") != CAPTIONS or style.get("visible_frame_time_text") is not False:
        raise ValueError("Chinese footer metadata differs from the exact approved captions")
    record = case["videos"][spec["video"]]
    if record.get("source_frames_inclusive") != [40, 100]:
        raise ValueError("Video is not the requested source-frame interval 40–100")
    tracked = {str(path): {"sha256": sha(path), "signature": signature(path)} for path in required}
    if tracked[str(video)]["sha256"] != record["sha256"]:
        raise ValueError("Video hash differs from its ready renderer manifest")
    info = probe(video, 61, (1968, 416))
    if png_size(preview) != [1968, 416]:
        raise ValueError("Preview geometry differs from the triptych")
    preview_record = case.get("preview")
    if preview_record:
        if preview_record.get("file") != spec["preview"] or preview_record.get("source_frame") != spec["preview_frame"]:
            raise ValueError("Preview frame identity differs from the requested source frame")
        if tracked[str(preview)]["sha256"] != preview_record["sha256"]:
            raise ValueError("Preview hash differs from its renderer manifest")
    else:
        # The sealed Musk05 renderer predates the dedicated preview manifest field.
        seal_path, seal_check = source_root / "manifest.sha256.json", source_root / "analysis/seal_verification.json"
        seal = load(seal_path)
        if sha(seal_path) != load(seal_check)["manifest_sha256"]:
            raise ValueError("Sealed Musk05 manifest differs from its completed verification")
        sealed = {entry["path"]: entry["sha256"] for entry in seal["files"]}
        if sealed.get("review/" + spec["preview"]) != tracked[str(preview)]["sha256"]:
            raise ValueError("Musk05 preview differs from its sealed hash")
        tracked[str(seal_path)] = {"sha256": sha(seal_path), "signature": signature(seal_path)}
    raw_inputs = case.get("inputs", [])
    if len(raw_inputs) != 3:
        raise ValueError("Ready comparison must identify three complete raw inputs")
    for raw in raw_inputs:
        path = Path(raw["path"])
        if not path.is_file() or sha(path) != raw["sha256"]:
            raise ValueError("Original raw input differs from renderer provenance")
        probe(path, 141, (1312, 736))
        tracked[str(path)] = {"sha256": raw["sha256"], "signature": signature(path)}
    if any(signature(Path(path)) != tuple(saved["signature"]) for path, saved in tracked.items()):
        raise ValueError("An input changed while checking readiness")
    qa_path = source_root / "review/renderer_qa.json"
    qa = load(qa_path) if qa_path.is_file() else {}
    qa_case = qa.get("cases", {}).get(spec["case"], qa) if spec["case"] else qa
    return {"id": spec["id"], "title": spec["title"], "status": "ready", "problems": [],
            "source_root": str(source_root), "video_source": str(video), "preview_source": str(preview),
            "video_file": spec["id"] + ".mp4", "preview_file": spec["id"] + "_preview.png",
            "video_sha256": tracked[str(video)]["sha256"], "preview_sha256": tracked[str(preview)]["sha256"],
            "probe": info, "preview_source_frame": spec["preview_frame"], "source_frames_inclusive": [40, 100],
            "host": spec["host"], "formal_runs": spec["runs"], "control_report": str(control_path),
            "control_status": "pass", "control_sha256": tracked[str(control_path)]["sha256"],
            "renderer_manifest": str(renderer_path), "renderer_manifest_sha256": tracked[str(renderer_path)]["sha256"],
            "caption_style": style, "raw_input_sha256": [raw["sha256"] for raw in raw_inputs],
            "visual_review_scope": spec["review_scope"],
            "source_visual_record": {"status": qa_case.get("status"), "visual_review": qa_case.get("visual_review"),
                                     "visual_review_scope": qa_case.get("visual_review_scope", qa.get("visual_review_scope"))},
            "tracked_sources": tracked}


def inspect_all():
    results = []
    for spec in SPECS:
        try:
            results.append(inspect_case(spec))
        except (OSError, ValueError, KeyError, TypeError, IndexError, RuntimeError, subprocess.SubprocessError) as error:
            results.append({"id": spec["id"], "title": spec["title"], "status": "invalid", "problems": [str(error)]})
    return results


def record_status(cases, status, **extra):
    result = {"status": status, "checked_utc": datetime.now(timezone.utc).isoformat(),
              "ready_count": sum(case["status"] == "ready" for case in cases), "required_count": 4,
              "cases": cases, "delivery_path": str(DELIVERY), "zip_path": str(ZIP_PATH),
              "no_substituted_media": True, **extra}
    write_json(ROOT / "status.json", result)
    lines = [f"状态：{status}；就绪 {result['ready_count']}/4。", "四组全部通过之前不创建下载目录或ZIP。"]
    for case in cases:
        lines.append(f"{case['id']}: {case['status']}" + (" — " + "; ".join(case["problems"]) if case["problems"] else ""))
    (ROOT / "STATUS.txt").write_text("\n".join(lines) + "\n")
    return result


def page(cases):
    body = '<h1>四组短动作对照：Musk / Sam</h1><p>AI人物替换实验。每段为同帧横向三栏，正常速度，约2.54秒。</p>'
    for case in cases:
        body += f'<section><h2>{html.escape(case["title"])}</h2><video controls preload="metadata" poster="{case["preview_file"]}" src="{case["video_file"]}" data-source-frames="40-100" data-source-fps="24"></video><p><a href="{case["video_file"]}">打开短视频</a> · <a href="{case["preview_file"]}">查看预览</a></p></section>'
    body += '<details><summary>说明与来源</summary><p>Musk05已有详细逐帧评审；其余三组仅作有限预览/文件抽查，不据此宣称效果或整体身份质量。跨组运行环境不同。</p><p><a href="README.txt">完整说明</a> · <a href="CREDITS.txt">来源署名</a> · <a href="manifest.json">文件清单</a> · <a href="SHA256SUMS">SHA-256</a></p></details>'
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>四组短动作对照</title><style>body{background:#000;color:#fff;font:16px system-ui,sans-serif;max-width:1600px;margin:auto;padding:24px}p{line-height:1.6;color:#ddd}a{color:#fff}section{margin:32px 0}video{display:block;width:100%;height:auto;background:#000}h1{font-size:26px}h2{font-size:20px}summary{cursor:pointer}</style><body>' + body + '</body></html>\n'


def check_links(folder):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.paths = []

        def handle_starttag(self, tag, attrs):
            self.paths.extend(value for key, value in attrs if key in ("href", "src", "poster") and value)
    parser = Links()
    parser.feed((folder / "index.html").read_text())
    if not all((folder / path).resolve().is_relative_to(folder.resolve()) and (folder / path).is_file() for path in parser.paths):
        raise ValueError("Bundle HTML contains a broken or nonlocal media link")
    return len(parser.paths)


def verify_bundle(folder):
    manifest = load(folder / "manifest.json")
    expected = {record["path"] for record in manifest["files"]} | {"manifest.json", "SHA256SUMS"}
    actual = {str(path.relative_to(folder)) for path in folder.rglob("*") if path.is_file()}
    if actual != expected or len(list(folder.glob("*.mp4"))) != 4 or len(list(folder.glob("*.png"))) != 4:
        raise ValueError("Final bundle must contain exactly four videos and four previews, with no extra media")
    for record in manifest["files"]:
        path = folder / record["path"]
        if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError("Bundle content hash mismatch: " + record["path"])
    checksums = dict((path, digest) for digest, path in (line.split("  ", 1) for line in (folder / "SHA256SUMS").read_text().splitlines()))
    if set(checksums) != expected - {"SHA256SUMS"} or any(sha(folder / path) != digest for path, digest in checksums.items()):
        raise ValueError("SHA256SUMS does not cover the exact content and manifest")
    return check_links(folder)


def make_zip(folder, destination):
    files = sorted(path for path in folder.iterdir() if path.is_file())
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            info = zipfile.ZipInfo(DELIVERY.name + "/" + path.name, date_time=(2026, 10, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=6)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != {DELIVERY.name + "/" + path.name for path in files}:
            raise ValueError("ZIP CRC or folder-prefixed file set failed")
        for path in files:
            if hashlib.sha256(archive.read(DELIVERY.name + "/" + path.name)).hexdigest() != sha(path):
                raise ValueError("ZIP file differs from the assembled content")
    return len(files)


def assemble(cases):
    if len(cases) != 4 or any(case["status"] != "ready" for case in cases):
        raise ValueError("All four cases must be ready before staging or publishing")
    staging = ROOT / "staging"
    staging.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="four-ready-", dir=staging) as temporary:
        working = Path(temporary)
        folder = working / DELIVERY.name
        folder.mkdir()
        for case in cases:
            for kind in ("video", "preview"):
                source = Path(case[kind + "_source"])
                target = folder / case[kind + "_file"]
                shutil.copy2(source, target)
                if sha(target) != case[kind + "_sha256"]:
                    raise ValueError("Copied media is not byte-identical to its verified source")
        (folder / "index.html").write_text(page(cases))
        (folder / "README.txt").write_text(README)
        (folder / "CREDITS.txt").write_text(CREDITS)
        files = [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)} for path in sorted(folder.iterdir())]
        public_cases = [{key: value for key, value in case.items() if key != "tracked_sources"} for case in cases]
        manifest = {"schema_version": 1, "bundle_id": "h3-four-short-comparisons-20261015", "status": "ready",
                    "video_count": 4, "preview_count": 4, "normal_speed_only": True, "copy_method": "byte-identical copy; no re-encoding",
                    "source_frames_inclusive": [40, 100], "frames_each": 61, "fps": 24, "duration_seconds": 61 / 24,
                    "comparison_size": [1968, 416], "caption_labels": CAPTIONS, "caption_legend": "角色替换",
                    "visible_timing_overlay_added": False, "cross_case_environment_limit": "Musk05 .41; other cases .9; within-pair control pass does not isolate cross-case host/content effects.",
                    "cases": public_cases, "files": files,
                    "checksum_scope": "Content files listed here; SHA256SUMS additionally covers manifest.json. Its own digest and ZIP digest are recorded in the assembler's assembly_verification.json."}
        write_json(folder / "manifest.json", manifest)
        checksum_paths = sorted(path for path in folder.iterdir() if path.is_file())
        (folder / "SHA256SUMS").write_text("".join(sha(path) + "  " + path.name + "\n" for path in checksum_paths))
        link_count = verify_bundle(folder)
        for case in cases:
            for path, evidence in case["tracked_sources"].items():
                if sha(Path(path)) != evidence["sha256"]:
                    raise ValueError("Source evidence changed before publication")
        temporary_zip = working / "bundle.zip"
        zip_files = make_zip(folder, temporary_zip)
        expected_files = {path.name: sha(path) for path in folder.iterdir() if path.is_file()}
        if DELIVERY.exists():
            verify_bundle(DELIVERY)
            if {path.name: sha(path) for path in DELIVERY.iterdir() if path.is_file()} != expected_files:
                raise ValueError("Existing output differs; refusing to overwrite an unrelated or changed delivery")
        if ZIP_PATH.exists() and sha(ZIP_PATH) != sha(temporary_zip):
            raise ValueError("Existing ZIP differs; refusing to overwrite it")
        if not DELIVERY.exists():
            os.replace(folder, DELIVERY)
        if not ZIP_PATH.exists():
            os.replace(temporary_zip, ZIP_PATH)
        verify_bundle(DELIVERY)
        verification = {"status": "pass", "verified_utc": datetime.now(timezone.utc).isoformat(), "delivery_path": str(DELIVERY),
                        "video_count": 4, "preview_count": 4, "copied_media_byte_identical": True, "local_links_checked": link_count,
                        "zip_path": str(ZIP_PATH), "zip_bytes": ZIP_PATH.stat().st_size, "zip_sha256": sha(ZIP_PATH),
                        "zip_file_count": zip_files, "zip_crc_pass": True, "zip_all_content_hashes_match": True,
                        "manifest_sha256": sha(DELIVERY / "manifest.json"), "manifest_bytes": (DELIVERY / "manifest.json").stat().st_size,
                        "sha256sums_sha256": sha(DELIVERY / "SHA256SUMS"), "sha256sums_bytes": (DELIVERY / "SHA256SUMS").stat().st_size,
                        "source_roots_modified": False, "gpu_or_server_actions": False}
        write_json(ROOT / "assembly_verification.json", verification)
        return verification


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read source readiness and update local status only; never publish")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    cases = inspect_all()
    if any(case["status"] != "ready" for case in cases):
        result = record_status(cases, "pending", delivery_created=False, zip_created=False,
                               existing_delivery_untouched=DELIVERY.exists(), existing_zip_untouched=ZIP_PATH.exists())
        print(json.dumps({"status": result["status"], "ready_count": result["ready_count"], "required_count": 4, "status_file": str(ROOT / "status.json")}))
        raise SystemExit(2)
    if args.check:
        record_status(cases, "all_sources_ready_not_assembled", delivery_created=False, zip_created=False)
        print(json.dumps({"status": "all_sources_ready_not_assembled", "ready_count": 4}))
        return
    try:
        verification = assemble(cases)
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile) as error:
        record_status(cases, "assembly_failed", error=str(error), complete=False)
        raise
    record_status(cases, "complete", delivery_created=True, zip_created=True, verification=verification)
    print(json.dumps(verification, ensure_ascii=False))


if __name__ == "__main__":
    main()
