Robust coverage pilot: PREPARED, NOT RUN ON REAL POSES

Scientific scope
The original 49-lag numeric functions are byte-for-byte snapshots. Candidate proposal drops only the old coverage gate, while preserving >=8 frames, residual, search-edge and observed remote-basin checks. The new result is a conditional gain/residual certificate against null[-2,2]; it is not a unique-lag or physical-truth guarantee. All186 windows are retained for each endpoint. Uniform and confidence-completion estimands differ and are reported separately; coarse/tight bounds are separate outputs, not selectable alternatives after inspection.

Files
PROTOCOL.json/sha256 were written before implementation or actual target reads.
bounds.py: standard-library strict/coarse and one-sided tight completion bounds.
evaluate.py: gated original-pose intake, original diagnostics, all intervals and joint classifications.
launch_cpu.py + locked_remote.py: nonblocking Mac->remote CPU lock chain, one thread, CUDA hidden, no uploads or services.
frozen/: unmodified pinned numeric modules.
test_bounds.py/test_intake.py: standard-library tests and enumeration. attempt1 has a test-function placement error; attempt2 fixes only that fixture error and passes20/20. Both logs are retained.

Actual execution is pending independent review and a new reviewed BINDING JSON.
No real R26 or R27 pose sequence has been evaluated by this pilot. No remote files were uploaded or commands executed. No policy_replay/live files were modified.

Binding requirements
Top level: authorized_for_actual_evaluation=true, protocol_sha256, freeze_sha256, expected_runs map of run IDs to exact ordered endpoint list, cases list. R26 endpoint='final'; each R27 run must contain exactly indices0..19 before any target is read. Each case has safe case_id, run_id, family, endpoint; source_pose/target_pose {path,sha256}; gates [{kind:'RUN_GATE',path,sha256}] whose actual passed=true and run_id match; archive_evidence [{path,sha256,predicates:[{pointer:[...],equals:value}]}]; pose_evidence {source_pose:{path,pointer},target_pose:{path,pointer}} points into an already bound archive JSON to the actual recorded pose SHA. Do not fabricate evidence: R26 CPU_COMPLETE and source-selection metadata or R27 archived observations provide actual links. Parent/critic must review each binding's evidence and terminal-state scope.

Deployment/launch after approval only
Copy this frozen isolated directory to /data5/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/robust_coverage_pilot, then create the reviewed local and remote binding with remote input paths. launch_cpu.py --binding-name BINDING_<batch>.json --output-name results_<batch> takes the local shared lock first; locked_remote.py then takes the remote shared lock. Exit75 means lock busy and no analysis. The unique local/remote lock prevents a duplicate pilot consumer. No wait is performed while holding locks. SSH failure is not automatically retried; inspect actual remote process and partial results before explicit recovery. The output directory is exclusive and inside this owned root.

Unverified boundary
The standard-library tests cover algebra, partial information, correlated unit-vector completions, signed-shift proposals, multiple basins, unknown/invalid cases, both-confidence/all-null gates and archive-intake rejection. Actual NumPy pose-loader integration has not run yet; it will require the normal CPU lock and a tiny synthetic real-loader check before any real batch. No claims about recovered index5 or actual certificate counts are made.
