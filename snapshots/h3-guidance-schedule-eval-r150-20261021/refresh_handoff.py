"""Refresh compact actual progress references without changing experimental records."""
from datetime import datetime, timezone
from common import ROOT, read, write, bound

def main():
 p=ROOT/'HANDOFF.json';h=read(p);archive=ROOT/'audit/handoff_history'/bound(p)['sha256'];archive.mkdir(parents=True,exist_ok=True);(archive/p.name).write_bytes(p.read_bytes())
 h['updated_utc']=datetime.now(timezone.utc).isoformat();h['planned_new_outputs']=33;h['conditional_matching_native_outputs_max']=2
 h['ready_cases']=[c['source_id'] for c in read(ROOT/'EVALUATION_MANIFEST.json')['cases']];h['pending_producer_contract_tasks']=[]
 h['task_count']=10;h['independent_source_video_count']=9
 h['shared_source_tasks']=['R149 Sam05','R150 Musk05']
 h['notes']=[
  'Actual current plan: 33 new outputs; the original 31-output selection plan remains frozen.',
  'Firefly06 and Sam07 each require one new Native because the recovered conditioning tensor differs; Musk05 reuses its matching historical Native.',
  'Review and score accepted per-job videos as they arrive. Producer batch release and the strict MF tracker release are recorded independently.',
  'Redhair and alien are near-synchronous preservation cases; their broad phase intervals are not precise lag measurements.',
  'Ten tasks use nine independent source videos; R149 Sam05 and R150 Musk05 share source05.'
 ]
 h['runtime_note']='Runtime status follows actual accepted gates and batch release records below. Book preserves GPU6/GPU7 unknown-memory hardware failures and the final GPU0 exact release. The host60 MF queue runs independently from the producer queues.'
 presentations=sorted((ROOT/'review').glob('*/*/PRESENTATION.json'));reviews=sorted((ROOT/'review').glob('*/*/REVIEW.json'))
 h['actual_new_outputs_accepted']=len(presentations);h['completed_visual_review_count']=sum(read(p).get('review_completed',False) for p in reviews)
 h['completed_reviews']=[bound(p) for p in reviews if read(p).get('review_completed')]
 h['actual_completed_cases']=[{'source_id':p.parent.name,'batch_release':bound(p)} for p in sorted((ROOT/'actual').glob('*/BATCH_RELEASE.json'))]
 scores=sorted((ROOT/'scores').glob('*/*.json'))
 h['planned_new_score_targets']=34
 h['new_score_count']=len(scores)
 h['new_generated_videos_scored']=sum(not read(p).get('historical_media_reused',False) for p in scores)
 h['historical_videos_newly_scored']=sum(read(p).get('historical_media_reused',False) for p in scores)
 h['score_count_note']='34 target scores = 33 new generated videos + the reused historical Musk Native. Two first-time reference trackers are additional source computations, not edited-video scores.'
 h['first_source_trackers_completed']=[bound(p) for p in sorted(
  (ROOT/'mf_preparation/source_caches').glob('*/SOURCE_CACHE.json'))]
 h['references']={k:bound(v['file']) for k,v in h['references'].items()}
 h['references']['audit/DANCE_CONTRACT_APPEND.json']=bound(ROOT/'audit/DANCE_CONTRACT_APPEND.json')
 h['mf_preparation']['ready_host9_batches']=[{'case':p.parent.name,'seal':bound(p),'target_cpu':bound(p.parent/'audit/TARGET_CPU_VERIFIED.json') if (p.parent/'audit/TARGET_CPU_VERIFIED.json').exists() else None} for p in sorted((ROOT/'mf_preparation/host9_batches').glob('*/SEAL.json'))]
 h['current_showcase_source_qa']=bound(ROOT/'audit/SHOWCASE_SOURCE_QA.json')
 write(p,h);print({'accepted':len(presentations),'reviewed':h['completed_visual_review_count'],'planned_new':33})
if __name__=='__main__':main()
