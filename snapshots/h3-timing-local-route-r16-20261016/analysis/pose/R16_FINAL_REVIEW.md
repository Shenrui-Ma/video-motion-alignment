# R16 frozen source-forearm routing: final independent review

Both tested arms fail to correct the already known development-case delay. ROI and Uniform have primary direction lag **+13/+13 frames** and wrist lag **+12/+12**, while the existing Full control has **+1/+1** in both features. There is no useful demonstrated advantage of the tested source-only ROI over its equal-alpha-sum uniform control. This is a local efficacy failure, not a claim that all spatial interventions are impossible or that a broader research category lacks novelty.

## Design and completed integrity gates

The one source05/Sam/seed2026101311 case uses 141 frames, 1312×736, 24 fps, 20 Euler model evaluations. Both new arms route the same temporal bins14–19 (nominal physical47–67, primary50–65), all50 blocks, physical zero-based indices6–14 inclusive:20 NFE,20 updates,20 callbacks,1000 blocks,450 active corrections. The rule is `O + alpha_q * m_ref * (O_same - O_ref)`.

ROI uses the frozen source-forearm mask (32px inner/64px outer support, source confidence0.3); Uniform uses that mask's per-bin mean (about2.6%–5.2%). Equal alpha sum does **not** make attention-mass-weighted correction dose equal. Geometry, original conditions, tokens/embedding, actual reference latent, noise, and index5 prefix match the R3 controls. Both exact executed histories, eight unique snapshots plus final, finite raw tensors, actual call ranges, and raw MP4 hashes pass. No scientific graph or runtime was changed during sampling.

The deployed 63-file payload was checked. Its only documented change was administrative: allowing one exact parallel R17 process. The other62 files remain unchanged. The original sealed analysis tools were preserved; new `_v2` evaluation-only files fix two schema assumptions (the frozen router keeps status `sampling` after completion, and the manifest uses `{bytes,sha256}` entries). Actual successful history, counts, and complete20-callback recorder establish completion. See `EVALUATOR_V2_ADDENDUM.json` and both `replication/*_integrity.json` files.

## Frozen phase results

Each pair below is confidence threshold0.3 /0.5. Positive means edited motion is later. `?` is rejected/unknown and is not filled from neighboring windows. No windows or thresholds were changed.

| Arm | 50–65 direction; wrist | 69–81 direction; wrist | 80–92 direction; wrist | 99–111 direction; wrist |
|---|---|---|---|---|
| Native |13/13;13/12|10/?;10/?|8/?;8/?|4/4;4/4|
| Full6–14 |1/1;1/1|0/?;0/?|1/1;1/1|1/1;1/1|
| ROI6–14 |13/13;12/12|10/?;10/?|8/?;8/?|4/4;4/4|
| Uniform6–14 |13/13;12/12|10/?;10/?|8/?;8/?|4/4;4/4|

Strict primary success requires known direction **and** wrist estimates at both thresholds, all within±2 frames. Both new arms fail. Temporal lag is not evidence of semantic action deletion.

## Common valid support and off-window checks

Four-arm common-support direction errors at50–65:

| Confidence | Common support | Native | Full | ROI | Uniform |
|---|---:|---:|---:|---:|---:|
|0.3|1.000|1.11986|0.13519|1.10041|1.12060|
|0.5|0.921875|1.11105|0.13967|1.10047|1.10983|

Wrist errors are0.81804/0.14877/0.80830/0.81674 at0.3 (support1), and0.81607/0.15096/0.80423/0.81384 at0.5 (support0.90625), in Native/Full/ROI/Uniform order. The phase failure therefore cannot be dismissed as a difference in detected-frame support alone.

At0.3, direction errors before the target (0–46) are0.13679/0.12380/0.13813/0.13138; after it (68–140),0.47997/0.12453/0.47498/0.47899; tail112–140,0.09677/0.06684/0.08780/0.09098. The small ROI/Uniform differences do not establish an effect or distribution advantage. All complete curves remain in `common_support/`. At0.5 the69–81 and80–92 direction common support is only0.73077; corresponding wrist support is0.57692/0.61538. These cells do not pass the0.8 support requirement and are not promoted to strict comparative evidence.

The independently frozen lower-body auxiliary is pairwise source/arm support, **not** the four-arm common support above. Its primary leg lags are Native12/12, Full0/0, ROI13/13, Uniform12/12. At0.3 the respective same-frame leg errors are0.49062/0.13409/0.48546/0.48632. The source-forearm ROI does not inherit Full's leg correction. Retaining an already delayed native leg is not a preservation success. Torso lags18/18,5/5,17/17,18/18 occur with small direction errors; near-static torso measurements should not be treated as another independent event. The initial auxiliary convenience summary used a nonexistent field and recorded null; it is preserved, and the corrected summary reads the unchanged detailed `same_frame` records.

## Fixed visual review and geometry diagnostic

The three fixed frames55/86/105 and eight samples42/47/52/57/62/67/72/77 were inspected in both new arms. White curtains, cabinet, table, white bench, and the adult male gray-top/black-trouser edit remain visible. No gross room/silhouette collapse was observed in these samples. Hands and fast-motion regions are blurred. Exact identity likeness, fine fingers and full-clip flicker/ghosting remain unverified; this is not a full quality pass. The original-rate40-frame `[42,82)` segments and contact sheets are archived in `visual_review/`; they do not replace metrics on the original full MP4.

The source-only mask barely overlaps much of the visible delayed forearm at the final endpoint. A post-outcome diagnostic gives ROI-output mean alpha0.166 left/0.067 right (0.3), versus1.0 at the source. An exact-hash reused preintervention index5 decode shows left-arm alpha0.158 at0.3 and0.194 at0.5, but the right arm is largely unobservable (4/16 and0/16 valid frames). This supports spatial mismatch as a concrete hypothesis, not its causal proof: decoded clean estimates and final poses are not the actual noisy input or contextual query-feature support. Full's final overlap may be an effect of successful correction. The mask, window and thresholds were not expanded after observing failure. See `MASK_COVERAGE_INTERPRETATION.md` and both coverage JSONs.

## Cost, retained evidence, and release

ROI whole-history wall time1579.775s; Uniform1474.246s. Both20 NFE. CPU pose extraction68.477s/66.412s; integrity verification0.759s/0.784s. Four-arm frozen postprocessing2.913s,0 added NFE. These are cost records only, without a speed explanation or efficiency claim.

Both originals and all rejected/unknown metric cells are retained. The exact R16 service17134 exited, its cleanup records report process and owned compute absent, and a live check confirmed GPU2 idle before the parent reused it for R18. No other user's process was changed. The current GPU2 occupant is outside R16's completed lifecycle.

Use `FINAL_SUMMARY.json` for compact machine data, `FINAL_VISUAL_REVIEW.json` for visual scope, and `FINAL_REVIEW_MANIFEST.json` for file hashes. This single preselected development case cannot support generalization, statistical significance, or an architecture novelty claim.
