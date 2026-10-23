"""Prepare a five-case prompt-format ablation without touching live queues."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
CASES = ('short_0252', 'short_0358', 'short_0085', 'long_0059', 'short_0343')
VARIANTS = ('raw', 'six_section')
ROLES = ('native', 'global_weak')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def six_section(instruction):
    return ('subject_definitions:\n<Video 1>: source video.\n\n'
            'summary:\n[video editing] ' + instruction + '\n\n'
            'retention_analysis:\nNot specified.\n\n'
            'detailed_description:\nNot specified.\n\n'
            'overall_soundscape:\nNot specified.\n\n'
            'non_diegetic_music:\nNot specified.')


def build(remote_root):
    catalog_file = BASE / 'innovation/pilot_ten/manifest_preparation/catalog.json'
    metric_file = BASE / 'metrics/manifest.json'
    catalog = {c['task_id']: c for c in json.loads(catalog_file.read_text())['cases']}
    metrics = json.loads(metric_file.read_text())['jobs']
    template_path = BASE / 'inference/package/graphs/new_short_0343_native.json'
    template = json.loads(template_path.read_text())
    package = HERE / 'package'
    jobs, all_jobs, reuse, assets, prompts = [], [], [], [], []
    for sid in CASES:
        c = catalog[sid]
        official = next(j['metadata'] for j in metrics if j['task_id'] == sid)
        instruction = official['edit_prompt']
        assert instruction == c['official_edit_prompt']
        geometry = c['geometry']
        frames = geometry.get('sampled_frames', geometry.get('frames'))
        video = Path(c['reference_video'])
        assert video.is_file()
        input_sha = sha(video)
        assert input_sha == c['reference_video_sha256']
        input_name = f'{sid}_video.mp4'
        assets.append({'task_id': sid, 'local_file': str(video), 'bytes': video.stat().st_size,
                       'sha256': input_sha, 'remote_file': f'{remote_root}/input/{input_name}',
                       'remote_action': 'verify existing SHA before upload; upload only if absent or mismatched'})
        prompts.append({'task_id': sid, 'official_edit_prompt': instruction,
                        'historical_prompt_protocol': c['prompt_protocol'],
                        'historical_prompt_sha256': c['prompt_sha256'],
                        'raw': instruction, 'six_section': six_section(instruction)})
        for variant in VARIANTS:
            prompt = instruction if variant == 'raw' else six_section(instruction)
            for role in ROLES:
                run_id = f'promptfmt_{sid}_{variant}_{role}'
                g = copy.deepcopy(template)
                g['5']['inputs'].update(prompt=prompt, width=geometry['width'], height=geometry['height'], length=frames)
                g['6']['inputs']['noise_seed'] = c['seed']
                g['22']['inputs']['file'] = input_name
                g['50']['inputs'].update(mode='native' if role == 'native' else 'mass_preserve',
                    alpha=1.0 if role == 'native' else 0.25, radius=0, time_offset=0,
                    start_frame=0, end_frame=geometry['valid_frames']-1, block_start=0, block_end=50,
                    step_start=0, step_end=20, schedule=role, run_id='{attempt_id}',
                    audit_dir=f'{remote_root}/audit/router')
                g['52']['inputs'].update(run_id='{attempt_id}', output_dir=f'{remote_root}/audit/timing')
                g['14']['inputs']['filename_prefix'] = run_id + '/{attempt_id}'
                graph_path = package / 'graphs' / (run_id + '.json')
                write(graph_path, g)
                md = {'cohort': 'prompt_format', 'task_id': sid, 'benchmark': 'IVEBench',
                    'dataset': 'IVEBench', 'title': c['title'], 'prompt_variant': variant,
                    'method': f'{variant}_{role}', 'guidance_method': role,
                    'prompt': prompt, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                    'official_edit_prompt': instruction, 'original_task': official,
                    'prompt_protocol': 'verbatim_official_edit_prompt' if variant == 'raw' else 'minimal_six_section_format',
                    'seed': c['seed'], 'geometry': {'width': geometry['width'], 'height': geometry['height'], 'frames': frames, 'fps': geometry['fps']},
                    'valid_frames': geometry['valid_frames'], 'fps': geometry['fps'],
                    'evaluation_crop_xywh': geometry['crop_xywh'], 'steps': 20,
                    'reference_video': str(video), 'reference_image': None,
                    'source_video': f'{remote_root}/input/{input_name}', 'reference_image_remote': None,
                    'source_video_sha256': input_sha, 'graph_input_names': {'video': input_name, 'image': None},
                    'graph_sha256': sha(graph_path), 'conditioning_policy': 'encode_current_prompt_with_H3StudyReference; no historical tensor cache',
                    'timing_file': f'{remote_root}/audit/timing/{{attempt_id}}.json',
                    'scientific_variable': 'minimal six-section format containing the verbatim official edit instruction; compare with archived prior results using their recorded prompt provenance',
                    'template_file': str(template_path), 'template_sha256': sha(template_path),
                    'model_names': {k: g[k]['inputs'] for k in ('1','2','3','4')},
                    'sampler': g['8']['inputs']['sampler_name'], 'sigmas': g['9']['inputs']['sigmas'],
                    'reference_size': 'match', 'schedule': role,
                    'router_alpha': g['50']['inputs']['alpha'], 'runtime_validation': 'pending'}
                job = {'id': run_id, 'graph': 'graphs/'+graph_path.name, 'expected_output_prefix': run_id+'/', 'metadata': md}
                all_jobs.append(job)
                if sid == 'short_0343' and variant == 'raw':
                    prior = next(j for j in metrics if j['id'] == f'new_{sid}_{role}')
                    reuse.append({'comparison_id': run_id, 'cohort': 'prompt_format', 'task_id': sid,
                        'prompt_variant': variant, 'method': f'{variant}_{role}', 'guidance_method': role,
                        'existing_job_id': prior['id'], 'video': prior['video'], 'video_sha256': prior['sha256'],
                        'source_frames_parent': prior['source_frames_parent'], 'target_frames_parent': prior['target_frames_parent'],
                        'metric_manifest_file': str(metric_file), 'metadata': md,
                        'reuse_reason': 'Exact current raw prompt, input, seed, geometry, sampler, and H3Study graph; no duplicate inference.'})
                if variant == 'six_section' and role == 'native':
                    jobs.append(job)
    manifest = {'schema': 'h3-prompt-format-five-v1', 'cohort': 'prompt_format', 'jobs': jobs}
    write(package/'jobs.json', manifest)
    write(HERE/'jobs_append.json', manifest)
    write(HERE/'all_twenty_comparisons.json', {'schema': manifest['schema'], 'status':'preparation_archive_only',
        'user_selected_scope':'Only five six_section_native jobs are authorized for this batch.', 'jobs': all_jobs})
    write(HERE/'reuse.json', {'schema': 'h3-prompt-format-reuse-v1', 'status':'not_scheduled_reference_only', 'items': reuse})
    write(HERE/'prompts.json', {'schema': 'h3-minimal-six-section-format-v1', 'cases': prompts})
    write(HERE/'assets.json', {'assets': assets})
    write(HERE/'preparation.json', {'status':'prepared_not_submitted', 'cohort':'prompt_format',
        'new_jobs':len(jobs), 'reused_jobs':0, 'total_active_comparisons':len(jobs),
        'scope':'Five six-section ordinary edits only; no new raw prompts or guided edits.',
        'prepared_unscheduled_graphs':len(all_jobs)-len(jobs),
        'source_catalog':str(catalog_file), 'source_catalog_sha256':sha(catalog_file),
        'source_metrics_manifest':str(metric_file), 'source_metrics_manifest_sha256':sha(metric_file),
        'remote_root':remote_root, 'observed_historical_prompt_mismatch':
        'Four old showcase cases use adapted prompts; only doctor uses raw instruction. Both formats must therefore be tested anew for the other four.'})
    files = [package/'jobs.json'] + [package/j['graph'] for j in jobs]
    write(HERE/'deployment_files.json', {'files':[{'local':str(p), 'relative':str(p.relative_to(package)),
        'bytes':p.stat().st_size, 'sha256':sha(p)} for p in files], 'total_bytes':sum(p.stat().st_size for p in files),
        'instructions':'Merge only the FIVE six_section_native jobs in package/jobs.json after active jobs. Never replace the live manifest. The other 15 prepared graphs are NOT scheduled. Inputs listed separately in assets.json.'})
    print(json.dumps({'new_jobs':len(jobs), 'reused':0, 'unscheduled_graphs':len(all_jobs)-len(jobs), 'deployment_bytes':sum(p.stat().st_size for p in files)}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--remote-root', default='/data4/research-user/h3_runs/benchmark_schedule_20261022')
    build(ap.parse_args().remote_root)
