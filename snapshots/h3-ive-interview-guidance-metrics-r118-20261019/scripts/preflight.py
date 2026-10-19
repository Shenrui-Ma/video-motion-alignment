"""CPU-only input, copied producer evidence and actual 107-frame PTS validation."""
from common import *
from render_media import media_info,check_time
c=verify_static();p=Path(c['producer_local']);seal=read(ROOT/'configs/producer_seal.json');require(sha(p/'deploy_manifest.json')==c['producer_seal_sha256'],'producer seal changed')
for rel,v in seal['files'].items():require(sha(p/relative(rel))==v['sha256'],'producer file changed')
results={}
for role,path in [('source',ROOT/c['source']['file']),('historical_native',Path(c['historical_native']['file']))]:
 s=media_info(path,'/opt/homebrew/bin/ffprobe');check_time(s,107,1312,736);results[role]=dict(input=bound(path),properties=s)
save(ROOT/'audit/CPU_PREFLIGHT.json',dict(passed=True,producer_files=len(seal['files']),producer_seal_sha256=c['producer_seal_sha256'],consumer_freeze_sha256=sha(ROOT/'CONSUMER_FREEZE.json'),input_checks=results,GPU_submitted=False,actual_forced_output='NOT_AVAILABLE'))
print(json.dumps(bound(ROOT/'audit/CPU_PREFLIGHT.json')))
