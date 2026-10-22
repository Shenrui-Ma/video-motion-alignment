"""Only complete reviewed R121 runs enter official scoring; failures stay in the set."""
SOURCES={'short_0252':98,'short_0358':105}
def reviewed_roles(completion):
 assert completion['schema']=='r121-screen-completion-v1' and completion['passed']
 assert completion['GPU_released'] and completion['all_sources_reviewed']
 assert completion['remaining_sources']==[] and completion['unreviewed_native_results']==[]
 rows=completion['terminal_sources'];assert [r['source_id']for r in rows]==list(SOURCES)
 paired=set(completion['guided_sources']);assert paired<=SOURCES.keys()
 assert set(completion['native_only_sources'])==SOURCES.keys()-paired
 expected=[];roles={}
 for row in rows:
  s=row['source_id'];role_list=['native','forced']if s in paired else['native'];roles[s]=role_list
  for role in role_list:expected.append(f'r121_{s}_seed2026101701_{role}')
 assert completion['successful_runs']==expected
 return roles

def validate_domain(source,manifest,roles):
 assert source in SOURCES
 n=SOURCES[source]
 assert (manifest['source_id'],manifest['valid_frames'],manifest['total_frames'],manifest['fps'],manifest['crop_xywh'])==(source,n,107,24,[16,8,1280,720])
 assert manifest['evaluation_indices']==list(range(n))
 assert set(manifest['raw_videos'])=={'source',*roles}
 assert manifest['reference_image_used']is False
 assert len(manifest['input_to_original_frame'])==n
 return n
