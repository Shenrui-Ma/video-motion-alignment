"""Bind the three selected, CPU-validated shared-condition dance contracts."""
import copy
from common import ROOT, bound, read, write, require, verify_record, prompt_sha
from bind_producer import runtime_binding


def main():
    manifest_path=ROOT/'EVALUATION_MANIFEST.json'
    old=read(manifest_path); new=copy.deepcopy(old)
    require(not any(c['source_id']=='musk05' for c in old['cases']), 'Dance cases already appended')
    archive=ROOT/'audit/manifest_history'/bound(manifest_path)['sha256'];archive.mkdir(parents=True,exist_ok=True)
    for name in ['EVALUATION_MANIFEST.json','EVALUATION_PLAN.json','EVALUATION_FREEZE.json','OVERVIEW_FRAME_PLAN.json']:
        (archive/name).write_bytes((ROOT/name).read_bytes())
    producer_root=ROOT.parent/'h3-guidance-schedule-r150-20261021'
    additions=[]
    for cid,sub in [('musk05','host9/cases'),('firefly06','cases'),('sam07','cases')]:
        history_path=ROOT/'selected_history'/f'{cid}.json'; h=read(history_path)
        producer=producer_root/sub/cid; contract_path=producer/'configs/scientific_contract.json'
        contract=read(contract_path);seal=bound(producer/'deploy_manifest.json');sealed=read(seal['file'])['files']
        def sealed_record(path):
            r=bound(path);require(r['sha256']==sealed[str(path.relative_to(producer))]['sha256'],'Unsealed '+str(path));return r
        sealed_record(contract_path)
        require(contract['schema']=='r150-legacy-dance-shared-condition-schedule-v1' and
                contract['NFE_per_job']==20 and contract['online_observer'] is False and contract['phase_displacement']==0,'Contract scope')
        recovery=producer_root/'condition_recovery'/cid/'CACHE_RECOVERY_RESULT.json';cr=read(recovery)
        require(cr['passed'] and bound(recovery)['sha256']==contract['condition_recovery']['result_sha256'],'Recovery proof differs')
        fresh=cr['requires_shared_cache_native'];require(fresh == (not cr['same_historical_embedding']),'Native policy inconsistent')
        roles=(['native'] if fresh else [])+['fixed','early','late','split','global_weak']
        require(contract['arms']==roles and contract['case_order']==[r['run_id'] for r in contract['cases']],'Actual roles differ')
        first=contract['cases'][0];fixed=next(x for x in contract['cases'] if x['arm']=='fixed')
        require(first['prompt']==h['prompt'] and first['prompt_sha256']==h['prompt_sha256'] and first['video_sha256']==h['media']['source']['sha256'],'Historical source/prompt changed')
        fixed_graph=sealed_record(producer/'configs/graphs'/(fixed['run_id']+'.json'))
        inputs=read(fixed_graph['file'])['50']['inputs']
        invariant={k:inputs[k] for k in ['mode','alpha','radius','time_offset','start_frame','end_frame','block_start','block_end']}
        media={r:bound(h['media'][r]['file']) for r in ['source','native']}; media['fixed']=None
        for r in ['source','native']:require(media[r]['sha256']==h['media'][r]['sha256'],'Historical media SHA')
        if fresh:media['native']=None
        events=[]
        for event in h['frozen_events']['events']:
            events.append({'id':event['id'],'label':event['label'],'source':event['source_interval_inclusive'],
                           'native':None if fresh else event['native_interval_inclusive'],
                           'archived_native':event['native_interval_inclusive'],
                           **{r:None for r in ['fixed','early','late','split','global_weak']},
                           'measurement_kind':event['measurement_kind'],'uncertainty_frames':event.get('uncertainty_frames'),
                           'absent_event_rule':event['absent_event_rule']})
        row={'source_id':cid,'candidate_id':cid,'original_source_id':h['source_id'],'source_group':h['source_group'],
             'title':h['task'],'dataset':'自有素材','seed':h['seed'],
             'producer_contract_schema':contract['schema'],'geometry':dict(h['geometry'],valid_frames=h['valid_frames'],fps=h['fps']),
             'media':media,'archived_historical_media':h['media'],'prompt':h['prompt'],'prompt_sha256':h['prompt_sha256'],
             'prompt_source_label':'沿用历史人像参考与完整六段实验提示词；固定新旧对照',
             'reference_image':True,'historical_record':bound(history_path),'historical_review':h['edit_evidence'][0],
             'historical_runs':{'native':{'graph':h['graphs']['native']['graph']},'fixed':{'graph':fixed_graph,'new_output_required':True}},
             'historical_initial_noise':{'file':contract['parent_noise_file'],'sha256':contract['parent_noise_sha256'],'binding':bound(contract_path),'local_tensor_copy':False},
             'condition_recovery':bound(recovery),'conditioning_sha256':contract['conditioning_sha256'],
             'shared_cache_native_required':fresh,'new_control_roles':(['native'] if fresh else [])+['fixed'],
             'expected_output_roles':roles,'expected_run_ids':contract['case_order'],
             'native_timing_status':'pending_matching_cache_native_review' if fresh else h['frozen_events']['native_timing_status'],
             'events':events,'phases':[],'official_MF':{'native':None,'fixed':None},'invariant_router':invariant,
             'fixed_schedule':{'label':'7–15','steps_0based':list(range(6,15))},'phase_offset':0,
             'MF_source_cache':None,'task_checks':['身份/衣着编辑完成','场景、镜头与动作结构保留','全141有效帧检查']}
        new['cases'].append(row);additions.append({'case':cid,'contract':bound(contract_path),'recovery':bound(recovery),'seal':seal,'new_outputs':roles})
        runtime=runtime_binding(read(producer/'configs/runtime.json'),cid)
        for actual in contract['cases']:
            arm=actual['arm'];graph=sealed_record(producer/'configs/graphs'/(actual['run_id']+'.json'))
            steps=[] if arm=='native' else list(range(6,15)) if arm=='fixed' else new['schedules'][arm]['steps_0based']
            require(actual['steps_zero_based']==steps and actual['valid_frame_count']==141 and actual['geometry']=={'width':1312,'height':736,'frames':141,'fps':24},'Case shape/steps')
            write(ROOT/'runtime'/cid/(arm+'.json'),{'status':'READY','source_id':cid,'schedule':arm,'role':arm,'run_id':actual['run_id'],
                  'phase_offset':0,'steps_0based':steps,'historical_prompt_sha256':h['prompt_sha256'],
                  'historical_noise_sha256':contract['parent_noise_sha256'],'historical_fixed_graph_sha256':fixed_graph['sha256'],
                  'conditioning_sha256':contract['conditioning_sha256'],'condition_recovery':bound(recovery),
                  'producer_seal':seal,'producer_verifier':sealed_record(producer/'analysis/postrun/verify_schedule.py'),
                  'scientific_contract':bound(contract_path),'graph':graph,'producer_runtime':sealed_record(producer/'configs/runtime.json'),**runtime,
                  'gate_relative_file':f"analysis/postrun/{cid}/{actual['run_id']}_GATE.json",
                  'batch_gate_relative_file':f'analysis/postrun/{cid}/SCHEDULE_RUNTIME_GATE.json'})
    require(new['cases'][:len(old['cases'])]==old['cases'],'Earlier cases changed')
    write(manifest_path,new)
    plan=read(ROOT/'EVALUATION_PLAN.json');plan['source_event_manifest']=bound(manifest_path)
    pins=read(ROOT/'OVERVIEW_FRAME_PLAN.json')
    for row in new['cases'][len(old['cases']):]:
        plan['cases'].append({'source_id':row['source_id'],'valid_frames':141,'events':row['events'],'phases':[],'full_frame_review':True})
        pins['cases'][row['source_id']]=copy.deepcopy(pins['cases'][row['original_source_id']])
    write(ROOT/'EVALUATION_PLAN.json',plan);write(ROOT/'OVERVIEW_FRAME_PLAN.json',pins)
    write(ROOT/'audit/DANCE_CONTRACT_APPEND.json',{'previous_manifest':bound(archive/'EVALUATION_MANIFEST.json'),'new_manifest':bound(manifest_path),
         'prior_case_records_unchanged':True,'source_events_unchanged':bound(ROOT/'EVALUATION_EVENTS.json'),
         'new_cases':additions,'planned_new_outputs':33,'actual_outputs_claimed':False})
    freeze=read(ROOT/'EVALUATION_FREEZE.json');freeze['files']=[bound(r['file']) for r in freeze['files']];write(ROOT/'EVALUATION_FREEZE.json',freeze)
    print('Bound 3 dance cases, 17 expected outputs; no GPU launch or result claim.')
if __name__=='__main__':main()
