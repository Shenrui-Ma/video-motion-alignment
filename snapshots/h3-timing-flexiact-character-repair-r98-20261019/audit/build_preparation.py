from pathlib import Path
import json,hashlib,copy,shutil
R=Path(__file__).resolve().parents[1]; OLD=Path('/Users/researcher/DevProjects/h3-timing-flexiact-expanded-r66-20261018'); P=Path('/Users/researcher/DevProjects/h3-timing-flexiact-p1-control-r90-20261018')
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
pair='human2animal_1__game_man_4';run='r98_'+pair+'_seed2026101701_native';oldrun='r66_'+pair+'_seed2026101701_native';remote='/data5/researcher/h3_runs/timing_flexiact_character_repair_r98_20261019'
prompt='''subject_definitions:
<Subject 1> is the anime man in <Picture 1>, with short parted black hair, a green cloak, a cropped brown jacket, a light shirt and cravat, dark trousers with pale crossing harness straps, dark boots, and paired hip gear. His identity, clothing, equipment and anime drawing style come from <Picture 1>.
<Subject 2> is the plain white backdrop in <Picture 1>.
<Subject 3> is the complete sequence of low floor-supported body motions performed by the woman in <Video 1>. This label supplies motion only; the woman's face, long braid, purple top and patterned trousers are replaced by <Subject 1>.
<Video 1> supplies the continuous shot structure, body orientation, motion order and physical timing for the target sequence.

summary:
[reference generation] Generate <Subject 1> performing <Subject 3> against <Subject 2>, following the complete motion sequence and timing of <Video 1>. The target image determines the character and plain white environment.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - preserve the short-haired male identity, anime style, green cloak, brown jacket, light shirt and cravat, dark trousers with pale crossing harness straps, boots and paired hip gear from <Picture 1> throughout the motion.
<Subject 2> (appears in [Shot 1]): fully_preserved - use the plain white backdrop from <Picture 1> throughout the shot.
<Subject 3> (appears in [Shot 1]): attribute_transfer - transfer the complete visible floor-supported motion to <Subject 1>, including body orientation, limb contact, direction, range, order and timing.
<Video 1> (continuous shot and motion timing): fully_preserved - follow the reference clip's continuous view and complete temporal progression while the character and environment are supplied by <Picture 1>.

detailed_description:
The target video uses the anime drawing style and plain white environment of <Picture 1>. The character remains the same short-haired man throughout, with the illustrated outfit and equipment moving naturally with his body.
[Shot 1] The camera shows <Subject 1> in the floor-supported pose and orientation seen at the beginning of <Video 1>, against <Subject 2>. His short parted black hair, facial structure, green cloak over the cropped brown jacket, light shirt and cravat, dark trousers, pale crossing harness straps, tall dark boots and paired hip gear retain the appearance established by <Picture 1>. His posture is animated according to <Subject 3>, rather than holding the standing pose of the reference image. The complete visible body follows the reference action within the frame.
The character begins low to the ground with his arms supporting his weight. Following the progression visible in <Video 1>, his elbows bend and his chest moves close to the floor. His hands and lower-body support points follow the reference contacts and their changes. He then pushes through his arms, raises his chest and extends his back as the source performer does. His shoulders, elbows, wrists, hips and head follow the same coordinated changes of position and orientation. Preserve the reference movement's pauses and transitions, including the portions between the larger poses, so each stage occurs at its corresponding point in the source motion.
As the reference motion continues, the character rounds his back and lowers his head. Follow the remaining visible movement through the end of <Video 1>, retaining the source sequence's pace, direction and range. The cloak, jacket and harness follow the bending and extension while preserving their appearance and attachment to the character. Keep the man recognizable during low poses, foreshortening and turns of the head; his face and short hair remain consistent with the target image. The plain white backdrop remains visible around the moving body throughout the shot. Maintain the reference clip's continuous camera view and overall framing so the body motion can be followed from beginning to end, with the target figure fully participating in each motion phase.

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
'''
pf=R/'configs/prompts'/f'{pair}_p1.txt';pf.write_text(prompt)
case=next(x for x in read(OLD/'configs/scientific_contract.json')['cases'] if x['run_id']==oldrun)
definition={'pair_key':pair,'motion_source_id':'human2animal_1','group':case['group'],'original_pair_id':case['original_pair_id'],'portrait':case['portrait'],'portrait_sha256':case['portrait_sha256'],'reference_image_expected':case['reference_image_expected'],'source':{k:case[k] for k in ('video','video_sha256','provenance','provenance_sha256')}}
definition['source'].update(original='source_human2animal_1_original.mp4',original_sha256=sha(R/'inputs/source_human2animal_1_original.mp4'));write(R/'design/CASE_DEFINITION.json',definition)
case.update(run_id=run,parent_graph='configs/parent_graphs/r66_actual_native.json',parent_graph_sha256=sha(R/'configs/parent_graphs/r66_actual_native.json'),graph_template_only=False,prompt=prompt,prompt_file='configs/prompts/'+pf.name,prompt_sha256=sha(pf),prompt_version='P1-reference-v1')
s=read(P/'configs/scientific_contract.json');s.update(schema='r98-flexiact-character-repair-native-v1',cases=[case],case_order=[run],source_ids=[pair],pair_keys=[pair],prompt_version='P1-reference-v1',scope_note='Task repair replication on host9; historical R66 P0 on host41 differs in Torch/PyAV/runtime. Prompt is the only scientific graph change; P0/P1 output differences cannot be attributed solely to prompt. No timing guidance or new method.',noise_cache_sha256='aa10316e74d49ed5a92fa96eefd26e3c42d569bd61a202b9d5d48744a3307446');write(R/'configs/scientific_contract.json',s);write(R/'configs/queue.json',{'jobs':[run],'finalize':True})
b={'schema':'r98-historical-task-repair-bindings-v1','parent_root':str(OLD),'parent_remote_root':'/data3/researcher/h3_runs/timing_flexiact_expanded_r66_20261018','parent_run':oldrun,'parent_native_graph_sha256':sha(R/'configs/parent_graphs/r66_actual_native.json'),'p1_file_sha256':sha(pf),'definition_sha256':sha(R/'design/CASE_DEFINITION.json'),'noise_cache_relative':'design/R66_ACTUAL/r66_'+pair+'_seed2026101701_noise.pt','noise_cache_sha256':s['noise_cache_sha256'],'actual_record_sha256':{p.name:sha(p) for p in (R/'design/R66_ACTUAL').iterdir()},'runtime_comparison':'Different hosts/libraries; current VAE tensors and x0 may differ. Actual AV raw noise is copied exactly from R66.'};write(R/'configs/parent_bindings.json',b)
rt=read(R/'configs/runtime.json');rt.update(remote_root=remote,port=8562,profile='host9_gpu3_r98_normal_reserve8',profile_scope=s['scope_note']);write(R/'configs/runtime.json',rt)
write(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
# Reuse all six exact numerical modules; adapters only call the new contract.
kh=read(P/'configs/runtime_kernel_hashes.json')
for rel,row in kh.items():
 parent=OLD/rel
 row.update(parent_sha256=sha(parent),current_sha256=sha(R/rel),byte_equal=sha(parent)==sha(R/rel),parent_file=str(parent))
 assert row['byte_equal'],rel
write(R/'configs/runtime_kernel_hashes.json',kh)
# Predecessor is still the exact live R85 original generation; root supplies dynamic peer separately.
contract=R/'scripts/r98_contract.py';text=contract.read_text().replace('Only the prompt bundle differs from R85 P0 science.','Cross-host task repair; the prompt is the only scientific graph change.').replace("P1_SHA='11efbddcdd973499bea0f716f55429f789a5c0275462bc82d6c5fd925cd2207f'",'P1_SHA='+repr(sha(pf))).replace('R72 P1 exact','R98 P1 exact').replace("case['prompt_version']=='P1'","case['prompt_version']=='P1-reference-v1'").replace("a['r85_native_graph_sha256']","a['parent_native_graph_sha256']").replace('R85','R66').replace("'motion_source_id':'one_leg'","'motion_source_id':'human2animal_1'")
contract.write_text(text)
# Original graph is rebuilt by the audited contract, preserving all numerical fields.
import sys;sys.path.insert(0,str(R/'scripts'));import r98_contract as c
write(R/'configs/graphs'/(run+'.json'),c.expected_graph(R,case))
for file in (R/'tests').glob('*.py'):
 t=file.read_text().replace('R85_ACTUAL','R66_ACTUAL').replace('r85_actual_native','r66_actual_native').replace('r85_human2animal_1__game_man_4','r66_human2animal_1__game_man_4')
 file.write_text(t)
# Seal binds the raw noise archive and all historical small records; no dependency on a live .41 service.
wrapper=R/'audit/root_run_native.py';t=wrapper.read_text();start=t.index('def prepare_original_noise():');end=t.index('\ndef main():',start)
t=t[:start]+'''def prepare_original_noise():
    bindings=read(ROOT/'configs/parent_bindings.json')
    source=ROOT/bindings['noise_cache_relative'];digest=bindings['noise_cache_sha256']
    require(sha(source)==digest,'original R66 AV noise cache changed')
    target=ROOT/'audit/r98_human2animal_1__game_man_4_seed2026101701_noise.pt'
    if not target.exists():
        tmp=target.with_suffix('.copying')
        with source.open('rb') as before,tmp.open('xb') as after:shutil.copyfileobj(before,after)
        require(sha(tmp)==digest,'R66 noise copy not exact');os.replace(tmp,target)
    require(not target.is_symlink() and sha(target)==digest,'new noise cache differs from actual R66')
    return {'source':str(source),'destination':str(target),'sha256':digest,'bytes':target.stat().st_size}
''' +t[end:]
wrapper.write_text(t)
# Keep historical outcome review separate from all model inputs.
review=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/audit/flexiact_inventory/r66_human1_game4_task_recheck/REVIEW.json');shutil.copy2(review,R/'design/HISTORICAL_QUALITY_REVIEW.json')
write(R/'design/TASK_ACCEPTANCE.json',{'scope':'Visual task acceptance before any temporal-success claim; manual evaluation only, never control input.','target':'Reference image anime man, short parted black hair, green cloak, brown jacket, light shirt/cravat, dark trousers/pale crossing harness, dark boots/hip gear.','scene':'Plain white backdrop as old task requested and current image shows.','required_checks':['Stable target face and short hair across the 147 valid frames; inspect front/side/low poses.','Target clothing, harness, boots and hip gear remain coherent; clothing-only transfer is insufficient.','No persistent source long braid, source face, purple top or patterned trousers; mixed identity fails.','Plain white backdrop rather than inherited source room.','Low support, chest near floor, arm-supported rise/back extension, rounded back/head down follow source stages.'],'report_separately':['identity','clothing','environment','motion phase','geometry/artifacts'],'valid_frames':147,'original_precision_seconds':0.125,'quality_success_is_not_implied_by_runtime_gate':True})
print('prepared',run,sha(pf))
