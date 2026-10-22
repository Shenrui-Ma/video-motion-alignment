import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from common import CONTRACT, ROOT, read, sha, validate_static
from consume import check_started
from evaluate import summarize, validate_review
import consume


class ConsumerTests(unittest.TestCase):
    def test_source_prompt_seed_bindings(self):
        self.assertEqual(validate_static()["case"]["seed"],2026101703)

    def test_historical_arithmetic_matches_r138(self):
        handoff=read(CONTRACT["historical_handoff"]["file"])
        for old,new in (("native","native"),("fixed","fixed"),("auto","originalauto")):
            events=read(ROOT/"configs/EVALUATION_PLAN.json")["events"]
            result=summarize(events,new)
            for key,value in handoff["descriptive_timing"][old].items():
                self.assertEqual(result[key],value)

    def review(self):
        events=read(ROOT/"configs/EVALUATION_PLAN.json")["events"]
        return events,dict(all_valid_frames_inspected=True,examined_frames=list(range(98)),
            task_acceptance=dict(status="PASS_CORE_EDIT",elderly_woman_identity=True,
            child_cabin_and_mask_retained=True,action_sequence_retained=True,framing_retained=True,
            source_man_identity_copy_observed=False,notes="test fixture only"),
            static_pose=dict(frame_range_inclusive=[4,19],all_range_frames_inspected=True,
            keyframe_observations=[dict(frame=i,source_native_originalauto_centeredauto_notes="fixture") for i in (4,10,19)],
            centeredauto_relative_to_originalauto="UNCERTAIN",worsened_static_pose_preservation=None,
            notes="test fixture only",evidence_scope="final_video_only"),
            events=[dict(id=e["id"],centeredauto_frames=e["source_frames"],
            centeredauto_status="COMPARABLE_VISIBLE",notes="test fixture only") for e in events],
            conclusion="synthetic fixture, not an experimental result")

    def test_full98_required(self):
        events,r=self.review();r["examined_frames"].pop(50)
        with self.assertRaises(ValueError):validate_review(r,events)

    def test_padding_rejected(self):
        events,r=self.review();r["events"][0]["centeredauto_frames"]=[97,98]
        with self.assertRaises(ValueError):validate_review(r,events)

    def test_missing_event_remains_null(self):
        events,r=self.review();r["events"][1].update(centeredauto_frames=None,centeredauto_status="OCCLUDED")
        result=validate_review(r,events)
        self.assertEqual(summarize(result,"centeredauto")["comparable_events"],2)
        self.assertEqual(summarize(result,"centeredauto")["comparable_phases"],0)

    def test_missing_event_cannot_have_time(self):
        events,r=self.review();r["events"][1]["centeredauto_status"]="MISSING"
        with self.assertRaises(ValueError):validate_review(r,events)

    def test_pending_is_not_complete(self):
        events,r=self.review();r["events"][0]["centeredauto_status"]="PENDING"
        with self.assertRaises(ValueError):validate_review(r,events)

    def test_task_pass_must_match_fields(self):
        events,r=self.review();r["task_acceptance"]["elderly_woman_identity"]=False
        with self.assertRaises(ValueError):validate_review(r,events)

    def test_static_review_cannot_use_intermediate_pose(self):
        events,r=self.review();r["static_pose"]["evidence_scope"]="intermediate_x0"
        with self.assertRaises(ValueError):validate_review(r,events)

    def test_static_worse_cannot_be_hidden(self):
        events,r=self.review();r["static_pose"].update(centeredauto_relative_to_originalauto="WORSE",
            worsened_static_pose_preservation=False)
        with self.assertRaises(ValueError):validate_review(r,events)

    def test_started_generation_and_protocol_required(self):
        runtime=read(CONTRACT["runtime"]["file"])
        s=dict(protocol_sha256=CONTRACT["protocol"]["sha256"],service=dict(pid=123,
            gpu_uuid=runtime["gpu_uuid"],port=runtime["port"],
            identity=dict(uid=runtime["uid"],start_ticks="456",cmdline=["python",CONTRACT["producer_remote"]+"/main.py"])))
        self.assertEqual(check_started(s)["pid"],123)
        bad=copy.deepcopy(s);bad["protocol_sha256"]="wrong"
        with self.assertRaises(ValueError):check_started(bad)
        bad=copy.deepcopy(s);bad["service"]["identity"]["cmdline"]=["other producer"]
        with self.assertRaises(ValueError):check_started(bad)

    def test_complete_binding_and_reject_wrong_video_or_owner(self):
        """Synthetic metadata only, deleted at test exit; never a reported R142 result."""
        c=CONTRACT;runtime=read(c["runtime"]["file"]);noise=read(c["noise"]["file"])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/"bundle";d.mkdir();(root/"audit").mkdir();(root/"scripts").mkdir()
            os.link(ROOT/"scripts/export_bundle.py",root/"scripts/export_bundle.py")
            owner=dict(pid=123,gpu_uuid=runtime["gpu_uuid"],port=runtime["port"],
                identity=dict(uid=runtime["uid"],start_ticks="456",cmdline=["python",c["producer_remote"]+"/main.py"]))
            started=dict(service=owner,protocol_sha256=c["protocol"]["sha256"])
            def put(name,value): (d/name).write_text(json.dumps(value))
            put("STARTED.json",started)
            (root/"audit/EXECUTION_BINDING.json").write_text(json.dumps(dict(run_id=c["run_id"],
                owner=owner,STARTED=dict(file=str(d/"STARTED.json"),sha256=sha(d/"STARTED.json")))))
            os.link(c["graph"]["file"],d/"graph.json")
            graph=read(d/"graph.json")
            put("job.json",dict(status="success",name=c["run_id"],graph_sha256=c["graph"]["sha256"],
                service_pid=123,service_identity=owner["identity"],prompt_id="synthetic"))
            put("history.json",dict(status=dict(completed=True,status_str="success"),
                prompt=[0,"synthetic",graph],outputs={"14":{"images":[dict(type="output",subfolder="",filename="synthetic.mp4")]}}))
            os.link(c["historical"]["source"]["file"],d/"centeredauto.mp4")
            gate=dict(passed=True,status="pass",cleanup_verified=True,valid_frames=98,verified_runs=[c["run_id"]],
                producer_manifest_sha256=c["producer_seal"]["sha256"],protocol_sha256=c["protocol"]["sha256"],
                service_record=owner,video=dict(file=c["producer_remote"]+"/output/synthetic.mp4",sha256=sha(d/"centeredauto.mp4")),
                cases=[dict(run=c["run_id"],arm="visible_only",independent_parent_inputs=dict(
                actual_initial_AV_noise_exact=True,noise_file_sha256=noise["source_sha256"]),
                NFE=20,updates=20,mask=[],first_on=None,
                independent_native_prefix=[dict(physical_index=i) for i in range(20)])],
                efficiency=dict(NFE=20,per_step=[dict(index=i) for i in range(20)]),
                raw_filtered_pose_binding=[dict(index=i) for i in range(20)])
            put("ONLINE_RUNTIME_GATE.json",gate)
            put("COMPLETE_REVIEW_HOLD.json",dict(passed=True,run_id=c["run_id"],no_followup_submission=True,
                gate_sha256=sha(d/"ONLINE_RUNTIME_GATE.json")))
            put("ROOT_EXIT_RECEIPT.json",dict(passed=True,service=owner,
                service_cleanup=dict(process_absent=True,own_compute_absent=True),
                observer_children=dict(all_exact_generations_absent=True,all_registered_CUDA_pids_absent=True)))
            put("counterfactual.compact.json",dict(status="complete",completed_forward_calls=20,
                completed_calls=1000,routed_calls=0,calls_by_forward=[50]*20,counterfactual=dict(
                seed=2026101703,full_physical_indices=[],actual_model_nfe=20,actual_euler_updates=20,callback_count=20,
                steps=[dict(physical_index=i,decision=dict(chosen_full=False)) for i in range(20)],
                measurements=[dict(physical_index=i,centered_eligibility={}) for i in range(20)],
                branches=[dict(nfe_index=i) for i in range(20)])))
            def seal():
                put("EXPORT.json",dict(run_id=c["run_id"],producer_root=c["producer_remote"],
                    exporter_sha256=sha(ROOT/"scripts/export_bundle.py"),
                    original_audit=dict(file=c["producer_remote"]+"/audit/counterfactual/"+c["run_id"]+".json",sha256="0"*64),
                    files={p.name:sha(p) for p in d.iterdir() if p.name!="EXPORT.json"}))
            seal()
            with patch.object(consume,"ROOT",root):
                self.assertEqual(consume.verify(d)["NFE"],20)
                original=read(d/"ROOT_EXIT_RECEIPT.json")
                bad=copy.deepcopy(original);bad["service"]["identity"]["start_ticks"]="wrong"
                put("ROOT_EXIT_RECEIPT.json",bad);seal()
                with self.assertRaisesRegex(ValueError,"mixed owners"):consume.verify(d)
                put("ROOT_EXIT_RECEIPT.json",original)
                gate["video"]["sha256"]="0"*64;put("ONLINE_RUNTIME_GATE.json",gate)
                done=read(d/"COMPLETE_REVIEW_HOLD.json");done["gate_sha256"]=sha(d/"ONLINE_RUNTIME_GATE.json")
                put("COMPLETE_REVIEW_HOLD.json",done);seal()
                with self.assertRaisesRegex(ValueError,"exact actual video"):consume.verify(d)


if __name__=="__main__":unittest.main()
