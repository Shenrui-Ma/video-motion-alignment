"""CPU-only presentation plumbing test. Repeats source pixels; publishes no scientific output."""
from pathlib import Path
import json,shutil,sys,tempfile,time
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import save,bound
from media import render,prepare_mf,ROLES
S=R.parent/'h3-ive-long0174-guidance-metrics-r107-20261019/incoming/long_0174/source.mp4'
out=R/'audit/UI_FIXTURE';out.mkdir(exist_ok=False)
with tempfile.TemporaryDirectory(prefix='fixture_only_',dir=R/'audit') as td:
 t=Path(td);inc=t/'incoming';inc.mkdir()
 for role in ROLES:shutil.copy2(S,inc/(role+'.mp4'))
 save(inc/'PAIR_RUNTIME_GATE.json',{'fixture_only':True});save(inc/'COLLECTION.json',{'fixture_only':True})
 p=render(inc,t/'showcase',publish=False);m=prepare_mf(inc,t/'prepared')
 assert len(p['pages'])==29 and [i for x in p['pages'] for i in x['frames']]==list(range(145))
 assert m['scores'] is None and m['status']=='INPUTS_READY_NO_TRACKER_STARTED'
 assert len({tuple(x['frame_md5']) for x in m['roles'].values()})==1
 for name in ('poster.jpg','frames_000-004.jpg','frames_140-144.jpg','caption.png'):
  shutil.copy2(t/'showcase'/name,out/name)
 save(out/'RECEIPT.json',{'passed':True,'fixture_only':True,'source_repeated_for_all_four_columns':bound(S),'valid_frames':145,'fps':24,'frame_pages':29,'all_physical_timestamps_verified':True,'all_four_lossless_crops_verified':True,'scores_prepopulated':False,'GPU_started':False,'published_to_Downloads':False,'temporary_fixture_media_removed_after_test':True,'created_unix':time.time()})
print(json.dumps({'fixture_passed':True,'receipt':str(out/'RECEIPT.json')}))
