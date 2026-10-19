# R6 feedback final-pose review

The tested controller did not repair the primary event timing. At confidence0.3 the final signed arm-direction lag is13 frames versus14 for native and2 for the same-host fixed Full control. At0.5 the feedback primary estimate is unknown because detection coverage is insufficient. Neither the complete nor partial repair criterion passes; unknown is retained rather than counted as zero lag.

| Run | Original four-window lag, confidence0.3 | Original four-window lag, confidence0.5 |
|---|---|---|
|R2 native|14,12,11,6|14,unknown,11,6|
|R2 fixed Full|2,10,9,5|2,unknown,9,5|
|R6 feedback retry1|13,11,9,6|unknown,unknown,9,6|

All windows remain50–65/69–81/80–92/99–111. Positive lag means the edited action is later. This is one selected failure case and reused same-host controls, not a new seed or population result.

## Integrity and realized controller

Actual conditioning, tokenization, pair snapshots and video/audio noise match the R2 controls. The preintervention x0 at zero-based forward5 is bitwise equal to R4 native in both video/audio, verified both during sampling and again from complete capture manifests. The executed graph matches outside the declared actuator and administrative fields. The controller audit passes all20-forward/1000-attention-call/state-machine checks.

The controller routes at zero-based forward indices `[6,8,9,10,11,12,13,14,15,16,17,18,19]`:13 forwards,650 routed blocks. Fixed Full uses indices6–14:9 forwards,450 routed blocks. NFE stays20. The observer reports20.11s total synchronous copy/validation/normalization/readout/decision time, excluding JSON writes. Whole-prompt duration is1729.061s versus1614.145s for fixed Full and1595.374s for native, descriptive only; no efficiency gain is established.

Its primary observer sequence at callback indices5/6/7/8 is11→1→12→6 frames. The index6 reading turns the next forward off; index7 turns it back on. Later readings rise to11 at the terminal callback. This is an observed readout rebound, not yet independent decoded-pose proof of a transient correction. Independent x0 indices5/6/7/8 decoding/pose is a separate pending diagnostic. A current guided x0 becoming aligned does not prove that the accumulated Euler state retains the correction.

## Common-support pose and quality

At0.3 the direct Full–feedback primary common valid support is0.84375. Arm-direction error is0.2935 versus0.7187; normalized wrist-relative error0.2634 versus0.7957; body-relative error0.1844 versus0.3896. The feedback result is worse on these shared-support measurements. At0.5 primary arm support0.65625 and wrist support0.59375 fail the0.8 gate; their numeric errors are retained but do not support a strict comparison. Body support0.849 remains usable, with error0.1689 versus0.3749. Single-arm sensitivity is not substituted for the combined-arm primary endpoint.

Three-arm0.3 primary support is0.84375 and shared errors are native1.0896/Full0.2963/feedback0.7220. Thus feedback does reduce one same-frame error relative to native, but that does not establish phase repair. The strict0.5 three-arm primary support is only0.65625.

| Direct Full vs feedback,0.3 | Common support | Full error | Feedback error |
|---|---:|---:|---:|
|Before region0–46|1.0000|0.1431|0.1495|
|Routed physical bins47–67|0.8810|0.3910|0.7044|
|After region68–140|0.9897|0.5476|0.5721|
|Tail112–140|1.0000|0.1754|0.1682|
|Whole141 frames|0.9770|0.3809|0.4320|

The tiny tail-error improvement does not outweigh failure at the target or establish a broad quality advantage. Original event windows2–4 also show no consistent superiority over fixed Full.

Fixed frames55/86/105 retain the white-curtain room, cabinet/table/bench, black borders and adult-male grey-top/dark-trouser edit. Frame55 has a clear same-time action mismatch; this is not proof of action deletion. Exact identity, hand anatomy, full-video flicker and fine background preservation remain unverified. Full quality success is not claimed.

## Retained failures and scope

The initial run `r6_s05_feedback` failed before any DiT step because of a Comfy guider-interface guard. It is a technical failure, not a scientific negative result, and is archived under `attempts/attempt1_pre_sampling_interface_failure`. The successful retry1 above is the evaluated scientific result.

This negative result rejects the implemented immediate on/off rule on this case; it does not prove that all feedback, late guidance or temporal routing is ineffective. The prior fixed Full success remains evidence that the case can be improved. A fair subsequent diagnosis needs to distinguish the missing early forward7, continued late routing, and readout-versus-state persistence; changes should remain separately registered rather than retuning this outcome.

Evidence: `compact_summary.json`, `actual_input_noise_pair.json`, `operator_execution_gate.json`, `replication/preintervention_gate.json`, `pairs/*.json`, `pilot/r6_s05_feedback_retry1.quality_review.json`, and the exact-history archive manifest.
