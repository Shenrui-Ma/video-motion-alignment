"""Freeze whole-source timing and reuse the verified lossless H3 input transform."""
from pathlib import Path
from fractions import Fraction
import hashlib, importlib.util, json, math, subprocess, time

R=Path(__file__).resolve().parents[1]
B=R.parent
S='long_0116'
P=B/'h3-timing-ive-otter-color-r136-20261020'
source=B/'h3-ive-short-source-selection-20261020/position_edit_candidate/sources'/f'{S}.mp4'
metadata=B/'h3-ivebench-next-candidates-20261018/metadata/ivebenchdb_prompt_long.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

assert sha(source)=='5f1bca7328778c7ba269b5cd2492ff67e54a4c3fe96d59e77579727eab8d4ea8'
inv=B/'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json'
assert S not in {x['source_id'] for x in json.loads(inv.read_text())['items']}
official=next(x for x in json.loads(metadata.read_text()) if x['src_video_name']==S+'.mp4')
assert official['edit_prompt']=='Move the muscular man to the left side of the frame'
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',str(source)]))
stream=probe['streams'][0]
tb=Fraction(stream['time_base'])
pts=[Fraction(x['best_effort_timestamp'])*tb for x in probe['frames']]
end=(int(stream['start_pts'])+int(stream['duration_ts']))*tb
start=pts[34]
valid=math.ceil((end-start)*24)
total=5+17*math.ceil((valid-5)/17)
mapping=[min(range(34,len(pts)),key=lambda k:(abs(pts[k]-start-Fraction(i,24)),k)) for i in range(valid)]
mapping += [len(pts)-1]*(total-valid)
assert (len(pts),stream['avg_frame_rate'],valid,total)==(184,'25/1',144,158)
contact=B/'h3-ive-short-source-selection-20261020/position_edit_candidate/long_0116_contact.jpg'
row={'source_id':S,'pair_id':S,'source':{'file':str(source),'sha256':sha(source),'bytes':source.stat().st_size,'frame_count':len(pts),'original_size':[stream['width'],stream['height']],'fps_rational':stream['avg_frame_rate'],'time_base':stream['time_base'],'actual_pts_rational':[str(x) for x in pts],'actual_pts_s':[float(x) for x in pts]},'clip':{'start_frame':34,'end_frame_inclusive':183,'start_pts_rational':str(start),'end_pts_rational_inclusive':str(pts[-1]),'end_exclusive_rational':str(end),'duration_rational':str(end-start)},'input_protocol':{'h3_frame_count':total,'effective_frame_count':valid,'input_to_original_frame':mapping,'fps':24,'geometry':[1312,736],'content_rectangle_xywh':[16,8,1280,720]},'edit_prompt':official['edit_prompt'],'official_task':official,'metadata_evidence':{'path':str(metadata),'sha256':sha(metadata)},'reference_image_used':False,'evaluation_scope':'IVEBench官方长片1.36–7.36秒连续片段探索','task_scope':'subject_position_edit','source_review':{'contact':str(contact),'sha256':sha(contact),'scientific_scope':'Three push-up cycles and a terminal torso transition; intended horizontal relocation is part of edit.'}}
plan={'schema':'r137-source-excerpt-v1','created_unix':time.time(),'pairs':[row]}
put(R/'design/INPUT_PLAN.json',plan)
put(R/'audit/SOURCE_AND_DUPLICATION_CHECK.json',{'source_sha256':sha(source),'inventory_sha256':sha(inv),'not_previously_run':True,'source_frame_count':184,'valid_frames':valid,'total_frames':total,'last_valid_map':mapping[valid-1],'padding_indices':list(range(valid,total))})
text=(P/'scripts/prepare_inputs.py').read_text().replace('import shutil','import shutil\nimport os').replace('shutil.copyfile(source,original)','os.link(source,original)').replace('r136','r137').replace('short_0235',S)
helper=R/'audit/inherited_input_preparer.py'
helper.write_text(text)
spec=importlib.util.spec_from_file_location('r137_prepare_input',helper)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.ROOT=R;m.SELECTION=R/'design/INPUT_PLAN.json';m.SELECTION_SHA=sha(m.SELECTION)
m.prepare(S)
put(R/'audit/SOURCE_PREPARED.json',{'created_unix':time.time(),'input_plan_sha256':sha(m.SELECTION),'provenance_sha256':sha(R/'inputs'/f'{S}_provenance.json'),'prepared_video_sha256':sha(R/'inputs'/f'{S}_video.mp4'),'original_hardlinked':source.stat().st_ino==(R/'inputs'/f'{S}_original.mp4').stat().st_ino,'geometry':[1312,736],'valid_frames':valid,'total_frames':total,'GPU_started':False})
