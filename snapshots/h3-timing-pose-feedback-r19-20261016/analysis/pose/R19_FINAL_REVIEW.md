# R19 current-native pose observer: completed development-case test

The registered online controller reduced the selected source05/Sam/seed2026101311 primary timing lag from direction13/13 and wrist13/12 to direction1/1 and wrist1/1 frames. Both confidence thresholds satisfy the frozen ±2-frame target. This is timing preservation evidence on an already selected development case; it does not establish semantic action deletion or generalization.

Actual physical indices0..5 stayed native;6..9 were the registered forced Full prefix. At10, current-native four scores were4/4/4/4 and Full was selected; at11 they were3/3/3/3 and Full was selected. At12 scores2/2/2/2 caused native selection;13 gave1/1/2/2, and14..19 gave1/1/1/1, remaining native. There were26 DiT model evaluations,20 Euler updates/callbacks,300 corrected blocks and10 full VAE/CPU pose observations. Index numbers are zero-based.

The final mask6..11 exactly matches the previously registered fixed R18 baseline. All10 common x0 snapshots plus sampler_final, both video and audio tensors, are bitwise equal to R18;141/141 decoded RGB frames are also equal with1312×736,24fps,141frames. Different MP4 container hashes are retained. This validates online observation and stopping without perturbing the selected trajectory; it does NOT show an advantage over fixed R18. Current-native here includes earlier selected interventions in its state, not an entirely unmodified trajectory.

## Frozen evaluation

| Reference-frame window | Direction lag .3/.5 | Wrist lag .3/.5 | Interpretation |
|---|---:|---:|---|
|50–65|1 / 1|1 / 1|Strict primary pass|
|69–81|0 / unknown|0 / unknown|Unknown retained at .5|
|80–92|1 / 1|1 / 1|Near zero|
|99–111|1 / 1|1 / 1|Near zero|

All141 final frames have a selected person, with0 missing/ambiguous/multiple-person frames. Confidence and motion ambiguity still produce the second-window unknown; detector presence is not equivalent to reliable phase.

Five-arm common-support comparison uses native/Full6..14/R12/R18/R19 jointly. Primary direction error at .3 is1.1292/.1334/.4046/.1831/.1831 respectively, with100% common support; at .5 it is1.1394/.1354/.4119/.1870/.1870 with96.875% support. Primary wrist error at .3 is.8331/.1503/.3475/.1841/.1841; at .5 .8312/.1522/.3427/.1836/.1836 with93.75% support. Full6..14 remains lower in this same-frame error; equal final lag is not equal pose fidelity. Tail112–140 arm/wrist errors improve versus native, but body_xy error is slightly larger (.1150 vs .1086). No all-metric improvement claim is justified.

Direct inspection of fixed55/86/105 images finds preserved curtain/furniture layout and the grey-top/black-trouser masculine edit. Hands/fast limbs remain soft with trailing edges. Exact identity likeness, full-clip flicker and full quality remain unvalidated. The images are exactly the R18 pixels, so this is not an independent new quality sample.

## Integrity and cost

Actual executed graph,70 immutable files,conditions/noise,finite branch inventories,20 callbacks,10+final captures,exact service identity and cleanup passed. Independent post-run checks reloaded R10 common native5/native10/Full10 tensors. Live G2 native10 decoded float/RGB141/MP4/pose/scores matched its frozen bridge; parent-state guards and the next Full10 exact replay passed. No decoder fallback or GPU residue was accepted.

History wall3286.889s; total observer wall1181.678s is included in it, not additive. Final CPU pose63.139s, integrity8.168s, common-support3.681s, replay2.137s. These are recorded costs, not an efficiency comparison.

The first post-run verifier had an analysis schema error: service registry stores cmdline plus argv, not cmdline_sha256. It failed before pose, was retained under pipeline_errors/service_identity_schema_attempt1, and was repaired by checking exact argv/NUL-derived SHA against the independently registered service identity. Runtime and scientific thresholds were unchanged. The unique retry completed successfully.

The same pose estimator family controls and evaluates this prototype. The selected case and known fixed schedule restrict inference. Per the newest user priority, no more old-source GPU experiments are started; prepared R21/R22 remain staged, and broader validity requires new-source tests.

## Evidence

- FINAL_SUMMARY.json and FINAL_VISUAL_REVIEW.json: structured outcome and explicit quality limits.
- replication/same_mask_R18_replay.json:11 AV pairs and141 RGB hashes.
- replication/r19_s05_pose_observer_integrity.json: independent actual inventory and prefix checks.
- replication/complete_evidence/:170 archived files, all checked against its SHA manifest; large tensors remain at their recorded remote paths.
- common_support/:exact five-arm support, frozen observer outputs and all window values.
- raw/r19_s05_pose_observer_00001_.mp4: original success output.
- live_cleanup.json: post-completion old-service/process evidence.
