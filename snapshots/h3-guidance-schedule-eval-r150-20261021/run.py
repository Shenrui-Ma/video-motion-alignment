"""Execute hash-pinned R149 CPU/media helpers with writes confined to R150."""
import hashlib, json, runpy, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OLD=ROOT.with_name('h3-guidance-schedule-eval-r149-20261020')
ALLOW={'collect_job','ingest','finalize_batch','finalize_composite','make_contact_sheets','make_full_frame_sheets','make_event_detail_sheets','summarize_review','prepare_mf'}
if len(sys.argv)<2 or sys.argv[1] not in ALLOW:raise SystemExit('Usage: python3 run.py '+ '|'.join(sorted(ALLOW))+' [existing options]')
for r in json.loads((ROOT/'audit/REUSE_ADAPTER.json').read_text())['records']:
 p=Path(r.get('file',r['source']));expected=r.get('sha256',r['source_sha256'])
 if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise SystemExit('Reviewed helper changed: '+str(p))
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(OLD)]
import common
assert common.ROOT==ROOT
script=sys.argv.pop(1)+'.py'
path=ROOT/script if (ROOT/script).exists() else OLD/script
sys.argv[0]=str(path)
runpy.run_path(str(path),run_name='__main__')
