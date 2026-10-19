# R2 same-host component experiment: the independent residual branch did not retain full repair

All four formal .41 runs have successful exact-history intake, geometry checks, archived original MP4s and frozen CPU pose evaluation. The two-step benchmarks are excluded. Every arm uses the registered source05/seed, 1312×736, 141 frames at24fps, 20 Euler calls and, where applicable, intervention calls6–14. The tested reference-query bins remain unchanged. No endpoint or detection threshold was adjusted.

The observed result is **full correction repairs the selected phase endpoint; neither independent component demonstrates sufficient repair at its registered natural strength**. This does not establish an architecture improvement. It also does not prove that a temporal residual can never work at another strength, schedule or decomposition.

## Frozen phase results

Positive lag means the edited pose occurs later than the source. Values below list original windows50–65 /69–81 /80–92 /99–111. `unknown` is retained, not counted as zero or removed.

| Arm | Confidence .3 | Confidence .5 | Primary decision |
|---|---|---|---|
| native N |14 /12 /11 /6|14 /unknown /11 /6|Delayed failure reproduced on this host|
| full F |2 /10 /9 /5|2 /unknown /9 /5|Primary complete under frozen \|lag\|≤2 rule|
| dynamic-only D |12 /10 /9 /5|unknown /unknown /9 /5|No demonstrated partial repair; .3 improves only2 frames, .5 rejects coverage|
| static-only S |14 /13 /11 /6|14 /unknown /11 /6|No primary improvement|

The dynamic primary .5 same-frame detection coverage is .65625; this is a measurement limitation in addition to its .3 failure. A single arm sensitivity result must not replace that primary endpoint. Later windows still have substantial lag even for F. This experiment addresses local phase, not proof that semantic actions were deleted.

## Shared-support and off-window checks

For the N/F pair alone, the primary common support is1.0 at.3 and.875 at.5. Shared-weight errors improve1.10572→.34484 and1.09878→.32314 respectively. Thus the full-versus-native primary improvement is not explained by dropping difficult joints from only one denominator.

For all four arms together, primary common support is.953125 at.3, with errors N=1.14670, F=.35794, D=.97268, S=1.14255. At.5, support is only.609375: **the strict four-arm common-support gate fails**. The numerical .5 values remain archived, but do not support a dual-threshold four-arm superiority claim.

All-four .3 errors on the fixed bins are:

| Source frames | N | F | D | S |
|---|---:|---:|---:|---:|
|0–46|.17053|.14315|.14590|.15026|
|47–67|1.05278|.43970|.87761|1.05010|
|68–140|.62218|.55000|.54657|.62458|
|112–140|.15602|.17495|.16732|.15605|

The final tail is slightly worse for F and D than N; the main-window gain is not a guarantee of no changes elsewhere. Original second/third windows also have .5 common-support limitations. These are exploratory paired error checks, not significance tests, and were not substituted for the registered phase endpoint.

## Fixed-frame visual limits

Frames55 and86 were examined for every arm against the original source. The room's white curtains, cabinet, table, bench and framing remain recognizable, and the adult male grey-top/dark-trouser edit remains present. There is no gross black-background collapse in these inspected frames. This is only a limited layout/edit-presence check, not a full quality pass or a biometric identity judgment.

F frame55 is nearer the requested raised-hand event but shows visible motion blur/ghosting around limbs/face; fine hand detail cannot be certified. Its frame86 still differs from the source hands-overhead pose. D frame55 retains a low forward-arm/bent-knee stance and S resembles the native delayed stance. The individual `pilot/*.quality_review.json` files bind these observations to exact video hashes. Full-video flicker, exact face identity and detailed hand quality remain unassessed.

## What this changes about the structural hypothesis

The preregistered promising outcome “D sufficient, S insufficient, F sufficient” did not occur. The data instead fall into “F sufficient, individual components not shown sufficient.” A joint contribution, changed natural correction magnitude, cancellation, or nonlinear trajectory interaction remains possible. The experiment does not isolate which one explains the difference. In particular, R2 did not record the same-QKV three-component probe: selected-branch statistics and separate algebraic smoke tests cannot fill that gap after the fact.

Time-mean and residual V are mathematical components of contextual features, not verified pure appearance and pure human motion. The fixed-QK static-value invariance is an operator property, not a claim that complete generated backgrounds stay unchanged. R3's separately registered actual component probe and alternative nonnegative spatial-marginal construction can test a more precise follow-up; R2 itself is a negative result for the simple independent-residual sufficiency claim.

## Provenance and operational recovery

The .41 native is not an exact replay of the old .9 native:0/141 decoded RGB frames match, and all common video/audio capture SHA fields differ. R2 therefore uses its own .41 N/F anchors. This observation alone does not isolate hardware as the cause of divergence.

Follow-up actual-audit comparison with R3 .9 native additionally finds different input-video tensor, prepared-video VAE tensor, VAE latents and conditioning embedding hashes, while prompt, actual noise streams/signature, tags and packed layout match. The R3 native is an exact replay of the old .9 native. Thus the cross-round DC difference must not be attributed solely to GPU arithmetic; input preprocessing/encoding differs as well. This does not invalidate the within-R2 paired experiment, but limits cross-round causal interpretation. Detailed hashes are in the R3 `analysis/pose/replication/r2_r3_actual_inputs.json`.

Exact MP4 hashes:

- N: `79c6513b11e6407b129d17c5b308d7512ffd9c596d6774b6fd8f490a2be28295`
- F: `ebf0f823c0999ce92ee819e9cf70fafa4693e8831a3fd08f8497a7af77aa94e2`
- D: `be6b7eb6cad64e2430e709d5570222df44b3a039f778ba160f65b86f6a8a7e2c`
- S: `6ebfd1b17ed44edef27b07967e64b0e4399e5c8fdd0dac31bae1301a5f4e08e4`

The first local consumer stopped during a readiness SSH connection closure after N/F were archived. It did not terminate or restart a GPU job. D/S successful remote outputs were subsequently consumed serially after bounded network retries and hash-bound archive reuse were added. This is a pipeline failure/recovery, not an unsuccessful scientific arm. The resumed consumer exited0 and all four outputs remain included. `WATCHER_RECOVERY.json` records the recovery; frozen model graphs and metrics were not edited.

Machine-readable evidence: `compact_summary.json`, complete `current_summary.json`, `pairs/native_full_threshold*.json`, `pairs/four_arms_threshold*.json`, exact-history `pilot/*_provenance/archive_manifest.json`, and `replication/native_rtx_vs_a100.json`. `within_round_actual_input_gate.json` independently confirms all four arms have equal actual conditioning objects and noise streams/signature. The root's model/operator execution review remains a separate gate to combine with this measurement report.

## Measured cost and contribution boundary

Actual successful prompt wall times are N1595.374s, F1614.145s, D1616.889s and S1615.137s (`prompt_walltime_summary.json`). These include graph/cache/model effects and are not a controlled throughput benchmark. D did not demonstrate either a timing-repair or speed advantage here. This is an efficacy result, not rejection because temporal centering resembles prior work. A later combined method or local-event benchmark remains assessable through its own registered utility, quality, efficiency and ablations.
