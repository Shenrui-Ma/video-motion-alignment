"""Attach comparison scope to verified video scores; never alter official score values."""
from pathlib import Path
import json,hashlib,time
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def b(p):return {'file':str(p),'sha256':sha(p)}
p=R/'audit/RESULTS_VERIFIED.json';d=read(p)
assert d['completed_targets']==d['requested_targets']==4
r=R/'audit/FINAL_RELEASE_VERIFIED.json';release=read(r)
assert release['passed'] and release['all_spawned_trackers_released']
rows=[]
for v in d['results']:
 m=read(R/'cases'/v['case']/'INPUTS.json');t=next(t for t in m['targets']if t['role']==v['role'])
 assert v['actual_generated_video_sha256']==t['full_sha256']
 row=dict(v,case_inputs=b(R/'cases'/v['case']/'INPUTS.json'))
 if v['case']=='long_0039':
  assert t['exploratory'] and not t['strict_gate_pass']
  row.update(input_pairing=t['input_pairing'],paired_input_exact=False,strict_gate_pass=False,exploratory=True,comparison_kind='reference_origin_control',scope='Official MF of this actual generated video. Historical inference-input pixel equality failed; not a strict same-condition causal paired result.',original_failed_gate=b(R/'configs/long_0039/REFERENCE_ORIGIN_RUNTIME_GATE.json'),input_difference_diagnosis=b(R/'configs/long_0039/INPUT_PIXEL_DIFFERENCE_SUMMARY.json'),visual_review=b(R/'configs/long_0039/REVIEW.json'))
 else:row.update(exploratory=False,scope='Actual generated video score; visual task and event findings remain separate.')
 rows.append(row)
out=R/'audit/QUALIFIED_RESULTS.json';out.write_text(json.dumps(dict(schema='mf-video-scores-with-comparison-scope-v1',passed=True,official_results=b(p),final_release=b(r),seal=b(R/'SEAL.json'),adapter=b(Path(__file__)),results=rows,created_unix=time.time()),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(b(out)))
