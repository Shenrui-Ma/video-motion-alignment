"""CPU display fixture: all three columns show the SAME source. No generated result."""
import sys,shutil,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
import common as c,render_pair as r
fixture=root/'audit/presentation_fixture';fixture.mkdir(exist_ok=False)
s='short_0131';out=fixture/'prepared'/s;out.mkdir(parents=True);(fixture/'incoming'/s).mkdir(parents=True)
real=root/'prepared'/s/'source_score.mp4'
for m in ('source','native','forced'):shutil.copy2(real,out/(m+'_score.mp4'))
manifest={'source_score_video':c.bound(out/'source_score.mp4'),'edited':{m:{'score_video':c.bound(out/(m+'_score.mp4'))} for m in ('native','forced')}}
c.save(out/'METRIC_INPUTS.json',manifest);c.save(out/'READY.json',{'passed':True,'metric_inputs':c.bound(out/'METRIC_INPUTS.json'),'fixture_only':True})
c.save(fixture/'incoming'/s/'PAIR_RUNTIME_GATE.json',{'fixture_only':True,'scientific_results':False})
r.ROOT=fixture;r.render(s,'/opt/homebrew/bin/ffmpeg','/opt/homebrew/bin/ffprobe',r.choose_font())
c.save(fixture/'FIXTURE_ONLY.json',{'three_columns_same_source':True,'generated_model_results':0,'purpose':'caption, encoding, physical PTS and layout integration test'})
print(fixture/'showcase'/s/'six_times.png')
