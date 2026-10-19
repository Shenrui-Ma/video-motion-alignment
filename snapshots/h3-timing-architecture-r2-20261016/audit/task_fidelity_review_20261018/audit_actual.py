"""Read captured actual graph/history/conditioning/DiT routing evidence."""
from pathlib import Path
import hashlib, json

ROOT=Path(__file__).resolve().parent
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    results={'runs':[], 'pairs':[], 'core_equality':{}}
    for core in (ROOT/'actual/host9/core').rglob('*.py'):
        relative=core.relative_to(ROOT/'actual/host9/core')
        other=ROOT/'actual/host41/core'/relative
        results['core_equality'][str(relative)]={'host9':sha(core),'host41':sha(other),'equal':sha(core)==sha(other)}
    for producer in sorted((ROOT/'actual').glob('host*/timing_*')):
        for graphfile in sorted(producer.glob('configs/graphs/*.json')):
            graph=read(graphfile); name=graphfile.stem
            record={'producer':producer.name,'run_id':name,'graph_file':str(graphfile.relative_to(ROOT)), 'graph_sha256':sha(graphfile)}
            jobfile=producer/'logs'/f'{name}_job.json'; historyfile=producer/'logs'/f'{name}_history.json'
            record['submitted']=jobfile.exists(); record['completed_history']=historyfile.exists()
            if jobfile.exists():
                job=read(jobfile);record['job_status']=job['status'];record['job_graph_hash_equal']=job['graph_sha256']==sha(graphfile)
            if historyfile.exists():
                history=read(historyfile);record['history_status']=history['status'];actual=history['prompt'][2]
                record['history_graph_equal']=actual==graph
                graph=actual
            event=graph['5']['inputs']; record['prompt']=event['prompt']
            record['prompt_sha256']=hashlib.sha256(event['prompt'].encode()).hexdigest()
            record['path_checks']={
                'load_video_to_frames':graph['23']['class_type']=='GetVideoComponents' and graph['23']['inputs']['video']==['22',0],
                'all_frames_to_reference':event['ref_video']==['23',0],
                'vae_supplied':event['vae']==['3',0] and graph['3']['class_type']=='VAELoader',
                'condition_to_sampler':graph['51']['inputs']['positive']==['5',0] and graph['7']['inputs']['conditioning']==['51',0],
                'empty_target_to_sampler':graph['51']['inputs']['target']==['5',1] and graph['10']['inputs']['latent_image']==['51',1],
                'no_ref_image': 'ref_image' not in event,
                'semantic_fps_2_phase_0':event['semantic_fps']==2 and event['phase_frames']==0,
                'euler20':graph['8']['inputs']['sampler_name']=='euler' and len(graph['9']['inputs']['sigmas'].split(','))==21,
            }
            assert all(record['path_checks'].values()),record
            record['length']=event['length'];record['source']=graph['22']['inputs']['file']
            record['explicit_editing']='[video editing]' in event['prompt']
            record['explicit_unedited_preservation']='unedited scene content' in event['prompt']
            auditfile=producer/'audit'/f'{name}_conditioning.json'
            if auditfile.exists():
                a=read(auditfile); refs=a['pair_snapshot']['actual']['references']
                assert a['pair_snapshot']['verified'] and len(refs)==1 and refs[0]['kind']=='video'
                assert a['input_video']['shape'][0]==event['length']
                assert a['native_vae_calls'][0]['prepared_frames']['shape'][0]==event['length']
                record['conditioning']={k:a[k] for k in ['input_video','native_vae_calls','target_latent_shapes']}
                record['conditioning']['actual_references']=refs
                record['conditioning']['packed_segments']=a['pair_snapshot']['actual']['packed_layout']['segments']
                record['conditioning']['qwen_sampling']=a['qwen_presentation'][0]['sampling']
                assert refs[0]['clean_latent']['sha256']==a['native_vae_calls'][0]['latent']['sha256']
            routerfile=producer/'audit/router'/f'{name}.json'
            if routerfile.exists():
                a=read(routerfile)
                record['actual_DiT']={k:a[k] for k in ['status','completed_forward_calls','routed_calls','metadata','validated_layout','first_attention'] if k in a}
            if historyfile.exists():
                assert record['history_graph_equal'] and record['job_graph_hash_equal']
                assert record['history_status']['completed'] and record['history_status']['status_str']=='success'
                assert record['actual_DiT']['completed_forward_calls']==20
                assert record['actual_DiT']['routed_calls']==(0 if name.endswith('_native') else 450)
            results['runs'].append(record)
    rows={r['run_id']:r for r in results['runs']}
    for name,n in rows.items():
        if not name.endswith('_native'):continue
        f=rows[name[:-7]+'_forced']
        record={'native':name,'forced':f['run_id'],'prompt_equal':n['prompt']==f['prompt'],
                'source_equal':n['source']==f['source'],'length_equal':n['length']==f['length'],
                'both_actual_complete':n['completed_history'] and f['completed_history']}
        assert record['prompt_equal'] and record['source_equal'] and record['length_equal']
        if 'conditioning' in n and 'conditioning' in f:
            record['actual_source_RGB_equal']=n['conditioning']['input_video']==f['conditioning']['input_video']
            record['actual_clean_reference_equal']=n['conditioning']['actual_references']==f['conditioning']['actual_references']
            assert record['actual_source_RGB_equal'] and record['actual_clean_reference_equal']
        results['pairs'].append(record)
    results['summary']={'planned_runs':len(rows),'submitted_runs':sum(r['submitted'] for r in rows.values()),
       'completed_runs':sum(r['completed_history'] for r in rows.values()),'completed_pairs':sum(r['both_actual_complete'] for r in results['pairs'])}
    (ROOT/'CHECKS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(results['summary']))
    for r in results['runs']:
        print(r['run_id'],r.get('job_status','PLANNED'),r.get('conditioning',{}).get('input_video',{}).get('shape'),r.get('actual_DiT',{}).get('completed_forward_calls'))

if __name__=='__main__':main()
