"""Bounded content/data and single-clock checks; no browser or inference."""
import copy
from html.parser import HTMLParser
import json
import re
from pathlib import Path
import tempfile
import build

ROOT=Path(__file__).resolve().parent
base=build.read(ROOT/'benchmarks.template.json')
checks={}
def rejected(data):
    try:build.validate(data)
    except ValueError:return True
    return False
x=copy.deepcopy(base);x['benchmarks'][0]['cases'][0]['ordinary']['timing_lag_ms']['value']=83
checks['pending_score_rejected']=rejected(x)
x=copy.deepcopy(base);x['benchmarks'][0]['cases'][0]['ordinary']['timing_lag_ms']['status']='unknown'
checks['unknown_without_interval_body_rejected']=rejected(x)
x['benchmarks'][0]['cases'][0]['timing_evaluation']={'body_part':'left_arm','frame_interval_inclusive':[32,63],'fps':24}
checks['unknown_with_interval_body_retained']=build.validate(x)==x and build.metric(x['benchmarks'][0]['cases'][0]['ordinary']['timing_lag_ms'],'lag')=='UNKNOWN'
with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
    p=Path(tmp)/'observed.json';p.write_text('{"lag_ms":83}')
    y=copy.deepcopy(x);y['benchmarks'][0]['cases'][0]['ordinary']['timing_lag_ms']={'status':'complete','value':83,'evidence':{'path':str(p),'sha256':build.sha(p),'json_pointer':'/lag_ms'}}
    checks['complete_lag_evidence_bound']=build.validate(y)==y and build.metric(y['benchmarks'][0]['cases'][0]['ordinary']['timing_lag_ms'],'lag')=='+83'
    y['benchmarks'][0]['cases'][0]['ordinary']['timing_lag_ms']['value']=84
    checks['wrong_lag_number_rejected']=rejected(y)
x=copy.deepcopy(base);x['benchmarks'][1]['cases'][0]['automatic']['video']={}
checks['pending_policy_output_rejected']=rejected(x)
x=copy.deepcopy(base);x['benchmarks'][0]['cases'].pop()
checks['fixed_denominator_rejected']=rejected(x)
class Groups(HTMLParser):
    def __init__(self):super().__init__();self.groups=[];self.current=None;self.external=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='figure' and a.get('class')=='comparison':self.current={'videos':0,'captions':0};self.groups.append(self.current)
        if self.current is not None and tag=='video':self.current['videos']+=1
        if self.current is not None and tag=='div' and a.get('class')=='caption':self.current['captions']+=1
        if tag in ('script','video','img','link'):
            for name in ('src','href'):
                if a.get(name,'').startswith(('https:','http:')):self.external.append(a[name])
    def handle_endtag(self,tag):
        if tag=='figure':self.current=None
html=(ROOT/'DRAFT_NOT_DELIVERED.html').read_text();parser=Groups();parser.feed(html)
embedded=json.loads(re.search(r'<script type="application/json" id="benchmark-data">(.*?)</script>',html,re.S).group(1))
expected_videos=5+sum(all(r is not None for r in (c['source_video'],c['ordinary']['video'],c['automatic']['video'])) for bench in embedded['benchmarks'] for c in bench['cases'])
checks['all15_groups_have_three_captions']=len(parser.groups)==15 and all(g['captions']==3 for g in parser.groups)
checks['completed_groups_use_one_player_each']=sum(g['videos'] for g in parser.groups)==expected_videos and all(g['videos']<=1 for g in parser.groups)
checks['timing_columns_rendered']=html.count('普通编辑 Δt (ms)')>=3 and html.count('自动法 Δt (ms)')>=3 and html.count('Δt测量：部位 / 帧段')==2
checks['fixed_detection_start_wording']='检测固定从去噪索引0开始' in html and '检测起点、干预起点和停止点均由该流程决定' not in html
checks['ambiguity_boundary_rejections_visible']='另一个匹配峰' in html and '搜索边界' in html
checks['no_external_asset_fetches']=not parser.external
manifest=build.read(ROOT/'DRAFT_MANIFEST.json');records=[]
for d in manifest['derived_media']:
    p=Path(d['mapping_path']);m=build.read(p)
    records.append({'path':str(p),'sha256':build.sha(p),'frames':m['output_probe']['nb_frames'],'maximum_timestamp_error_s':m['maximum_timestamp_error_s']})
    assert build.sha(p)==d['mapping_sha256'] and build.sha(m['output'])==d['output_sha256']
checks['all_encoded_videos_frame_mapping_verified']=len(records)==expected_videos and all(r['maximum_timestamp_error_s']<=1e-6 for r in records)
result={'schema':'h3-paper-draft-static-check-v2','passed':all(checks.values()),'checks':checks,'groups':parser.groups,'media':records,'browser_layout_review':'not performed; policy block respected','browser_playback_review':'not performed','scope':'evidence binding, frame timestamps, derived-media geometry and HTML player structure'}
(ROOT/'STATIC_CHECK.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['passed']
