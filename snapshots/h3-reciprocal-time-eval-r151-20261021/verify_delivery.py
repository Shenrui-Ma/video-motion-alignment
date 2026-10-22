"""Check the final R151 evidence and embedded media before distribution."""
import base64
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from prepare import ROOT, bind, read
from sam_pose import verify


class MediaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.videos = []
        self.images = []
        self.external_assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("video", "img", "source", "script", "iframe"):
            value = attrs.get("src")
            if value and not value.startswith("data:"):
                self.external_assets.append(value)
            if value and tag == "video":
                self.videos.append(value)
            if value and tag == "img":
                self.images.append(value)
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.external_assets.append(attrs.get("href"))


def media_hash(data_url):
    prefix, content = data_url.split(",", 1)
    if not prefix.endswith(";base64"):
        raise ValueError("Expected a base64 embedded asset.")
    return hashlib.sha256(base64.b64decode(content, validate=True)).hexdigest()


def main():
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    findings = read(ROOT / "FINDINGS.json")
    assert findings["complete"]
    assert manifest["roles"] == ["source", "native", "forward", "reverse", "combined"]
    assert {c["source_id"] for c in manifest["cases"]} == {
        "short_0252", "short_0358", "05_real_megumi_v"}
    expected_videos, expected_images, reviewed = [], [], []
    for case in manifest["cases"]:
        sid = case["source_id"]
        presentation = read(ROOT / "overview" / sid / "PRESENTATION.json")
        table = read(ROOT / "reviews" / f"{sid}.json")
        assert presentation["roles"] == manifest["roles"]
        assert presentation["full_decode_passed"] and table["MF_complete"]
        assert len(table["table"]) == 4
        assert all(row["MF"] != "待评测" for row in table["table"])
        verify(presentation["video"])
        expected_videos.append(presentation["video"]["sha256"])
        for screenshot in presentation["screenshots"]:
            verify(screenshot)
            expected_images.append(screenshot["sha256"])
        if case.get("reference_image"):
            verify(case["reference_image"])
            expected_images.append(case["reference_image"]["sha256"])
        for role in ("reverse", "combined"):
            result_file = ROOT / "results" / sid / f"{role}.json"
            result = read(result_file)
            review_file = ROOT / "reviews" / sid / role / "REVIEW.json"
            review = read(review_file)
            verify(result["video"])
            verify(result["execution_evidence"])
            verify(review["result"])
            assert review["result"]["sha256"] == bind(result_file)["sha256"]
            assert review["reviewed_valid_frames"] == [0, case["geometry"]["valid_frames"] - 1]
            for image in review["reviewed_images"]:
                verify(image)
            gate = read(Path(result["execution_evidence"]["file"]))
            assert gate["passed"] and gate["NFE"] == 20
            assert gate["reverse_routed_calls"] == 450
            assert gate["forward_routed_calls"] == (450 if role == "combined" else 0)
            assert gate["actual_routed_steps_zero_based"] == list(range(9))
            reviewed.append(bind(review_file))
        for key in ("verified_results", "final_release"):
            verify(table["MF_evidence"][key])
        for role, score in table["MF_evidence"]["new_scores"].items():
            result = read(ROOT / "results" / sid / f"{role}.json")
            assert score["actual_generated_video_sha256"] == result["video"]["sha256"]
    timing = read(ROOT / "reviews" / "05_real_megumi_v" / "TIMING_SUMMARY.json")
    assert timing["complete"] and set(timing["roles"]) == {"native", "forward", "reverse", "combined"}
    page = ROOT / "index.html"
    parser = MediaParser()
    parser.feed(page.read_text())
    assert not parser.external_assets
    assert [media_hash(v) for v in parser.videos] == expected_videos
    assert [media_hash(i) for i in parser.images] == expected_images
    output = ROOT / "DELIVERY_VERIFIED.json"
    output.write_text(json.dumps({
        "passed": True,
        "page": bind(page),
        "cases": 3,
        "new_generated_videos": 6,
        "conditions_per_case": 4,
        "columns_per_video": 5,
        "embedded_videos": len(parser.videos),
        "embedded_images": len(parser.images),
        "reviewed_outputs": reviewed,
        "external_media_dependencies": [],
        "verification": "Evidence hashes, actual intervention counts, complete review domains, final scores and embedded media.",
        "browser_rendering": "Not performed; file preview was unavailable.",
    }, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": True, "receipt": str(output), "bytes": page.stat().st_size}))


if __name__ == "__main__":
    main()
