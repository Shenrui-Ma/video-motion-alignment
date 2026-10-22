"""Record a qualitative review against actual paired evidence; no metric computation."""
import hashlib
import json
from pathlib import Path
import time

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
gate=ROOT/'incoming/short_0135/PAIR_RUNTIME_GATE.json'
prepared=ROOT/'prepared/short_0135/METRIC_INPUTS.json'
presentation=ROOT/'showcase/short_0135/PRESENTATION.json'
ready=ROOT/'audit/consumer_execution_20261018/short_0135_PRESENTATION_READY.json'
g=json.loads(gate.read_text())
p=json.loads(presentation.read_text())
r=json.loads(ready.read_text())
assert g['passed'] is True and all(g['checks'].values()) and r['passed'] is True
assert p['gate']['sha256']==sha(gate) and p['prepared']['sha256']==sha(prepared)
files=[gate,prepared,presentation,ready,OUT/'PAIR_FIXED_FRAMES.json',OUT/'ALL112_BRUSH_FRAMES.json',OUT/'REPORT.txt']
files.extend(sorted(OUT.glob('pair_page*.jpg')))
files.extend(sorted(OUT.glob('all112_brush_page*.jpg')))
record=dict(schema='r73-short0135-agent-visual-review-v1',source='short_0135',unix=time.time(),
    reviewer='Codex visual review; not a human-annotated benchmark label',
    scope=dict(valid_frames=112,fps=24,full_frame_checkpoints=list(range(0,112,4))+[111],
               brush_region_all_frames=list(range(112)),crop_xywh=[500,0,500,500],
               time_alignment='same original physical index; no lag correction or temporal interpolation'),
    task=dict(native='robotic hand/forearm replacement visibly achieved',forced='robotic hand/forearm replacement visibly achieved',
              unedited_scene='canvas, easel, artwork layout and framing retained in both'),
    motion=dict(native='main repeated up/down brush phases present',forced='main repeated up/down brush phases present',
                incremental_timing_improvement='not clearly established by all-frame qualitative comparison',
                contact_onset='UNKNOWN: white bristles overlap pale paint; depth/contact cannot be uniquely read',
                lift_off='UNKNOWN: same visibility limitation',exact_lag_frames=None),
    conclusion='Keep as task-completed pair without a demonstrated clear visual timing benefit.',
    official_MF='pending root-controlled target tracking/scoring; no new metric computed here',
    html=r['html'],html_sha256_at_review=sha(r['html']),
    video_paths=[item['video']['file'] for item in p['videos']],
    evidence={str(x):dict(sha256=sha(x),bytes=x.stat().st_size) for x in files},GPU_calls=0)
(OUT/'REVIEW.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=True,source=record['source'],html=record['html'],review_sha256=sha(OUT/'REVIEW.json'))))
