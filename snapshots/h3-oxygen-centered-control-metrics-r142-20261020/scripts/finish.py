"""Create a small JSON handoff after full98 review and verified official MF completion."""
from common import *
import math


def finish():
    actual()
    evaluation=ROOT/"audit/FINAL_VIDEO_EVALUATION.json"
    reviewed=read(evaluation)
    require(reviewed["collection"]==bound(ROOT/"incoming/actual/COLLECTION.json"),"evaluation changed generation")
    result_file=ROOT/"mf/audit/RESULTS_VERIFIED.json"
    final_release=ROOT/"mf/audit/FINAL_RELEASE_VERIFIED.json"
    r,release=read(result_file),read(final_release)
    require(r["completed_targets"]==r["requested_targets"]==1 and len(r["results"])==1,"one target required")
    score=r["results"][0]
    require(score["case"]=="short_0252" and score["role"]=="centeredauto"
            and score["actual_generated_video_sha256"]==sha(ROOT/"incoming/actual/centeredauto.mp4"),"MF target differs")
    require(score["valid_frames"]==score["evaluation_frames"]==98 and score["evaluation_fps"]==24,"MF domain")
    require(math.isfinite(score["score"]) and sha(score["result_file"])==score["result_sha256"],"score evidence")
    require(release["passed"] is True and release["fresh_task_cuda_absent"] is True
            and len(release["tracker_identities"])==1,"MF exact release required")
    route=read(ROOT/"prepared/MF_ROUTE.json")
    scores=dict(route["historical_scores"])
    scores["centeredauto"]=dict(value=score["score"],score_record=dict(file=score["result_file"],sha256=score["result_sha256"]))
    out=ROOT/"audit/REPORT_HANDOFF.json"
    save(out,dict(schema="r142-final-report-handoff-v1",status="FINAL",run_id=CONTRACT["run_id"],
         source_id="short_0252",seed=2026101703,scientific_variable=CONTRACT["scientific_variable"],
         independent_source_increment=0,video_roles=read(ROOT/"prepared/MF_INPUTS.json")["full_videos"],
         effective_domain=dict(valid_frames=98,fps=24,evaluated_physical_indices=list(range(98)),
         excluded_padding_indices=list(range(98,107)),crop_xywh=[16,8,1280,720]),
         visual_evaluation=bound(evaluation),comparison_media=bound(ROOT/"showcase/PRESENTATION.json"),
         official_MF=scores,MF_verified=bound(result_file),MF_release=bound(final_release),
         actual_collection=bound(ROOT/"incoming/actual/COLLECTION.json"),summary=reviewed["conclusion"],
         protected_report_modified=False))
    return bound(out)


if __name__=="__main__":
    print(json.dumps(finish()))
