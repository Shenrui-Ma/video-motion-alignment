# R5 radius-one temporal-band control

**Partial repair versus native, no improvement over radius-zero full.** The registered radius1 arm has primary lag3 frames at both confidence thresholds. Native was13 and radius0 full was1. Radius1 therefore improves the selected failure but does not pass the frozen complete-repair gate of absolute lag≤2. It is not an entirely ineffective method, and this one result does not rule out all temporal-band variants; it does reject superiority of this registered setting on the measured endpoints.

The comparison changes radius0→1: queries in the six selected latent bins can read reference bins t−1,t,t+1 instead of only t, while preserving native total reference attention mass. All other declared science settings remain fixed. The intervention uses **zero-based forward indices6–14 inclusive**, equivalent to the **7th–15th forwards**, nine forwards across50 blocks. Benchmarks are excluded. R3 native/full are archived baselines, not new independent samples.

## Frozen outcomes

| Arm | Confidence .3: four-window lag | Confidence .5 |
|---|---|---|
| Native (R3) | 13,10,8,4 | 13,unknown,unknown,4 |
| Radius0 full (R3) | 1,0,1,1 | 1,unknown,1,1 |
| Radius1 softband | 3,3,3,2 | 3,unknown,3,2 |

Windows remain50–65/69–81/80–92/99–111. Unknown detections are retained. These are pose-timing estimates, not proof of semantic deletion. Thresholds .3/.5 are detector sensitivity checks, not confidence intervals.

The direct full–softband common-support primary errors are **.13047→.33986** at .3 (support1.00000), and **.13121→.34296** at .5 (support.984375). The corresponding three-arm native/full/softband comparison also passes the support gate at the primary window:1.00000/.96875. Thus the primary comparison is not explained by one arm dropping difficult joints from its denominator.

Direct full–softband same-support checks at .3:

| Frames | Common support | Radius0 full | Radius1 |
|---|---:|---:|---:|
| 50–65 | 1.00000 | .13047 | .33986 |
| 69–81 | .92308 | .36415 | .88399 |
| 80–92 | 1.00000 | .12547 | .28292 |
| 99–111 | 1.00000 | .09779 | .21340 |
| 0–46 | 1.00000 | .12326 | .15612 |
| 47–67 | 1.00000 | .15642 | .38306 |
| 68–140 | .98630 | .11726 | .24822 |
| 112–140 | 1.00000 | .06684 | .08090 |
| 0–140 | .99291 | .12517 | .23633 |

The .5 comparison has the same ordering, except the second window does not meet the common-support gate (.67308) and must remain inconclusive at that threshold. Three-arm support in the third .5 window is also insufficient (.73077); the direct full–softband third-window support is adequate (.92308). Do not interchange those denominators. Radius1's pre-window error is slightly higher even than native on their common three-arm support. Tail error remains better than native but worse than full. These are supplementary pose checks, not perceptual-quality measurements.

## Fixed-frame visual observations

At original frame55, source/full show the hand near the head and a bent raised leg. Radius1 instead has a forearm across the face/forehead and no comparable lifted-leg shape at that exact frame. This supports a same-time mismatch, not a claim the action never appears. At86 both arms are overhead, but radius1 brings the hands together/crosses them rather than retaining the source spread. At105 the open-arm/extended-leg pose is broadly present.

The white curtains, cabinet, table and bench, and the adult-male grey-top/dark-trouser edit, remain visible in all three fixed checks. No gross room collapse is evident there. There is no established quality advantage over radius0; exact identity, fine hand detail and full-video flicker were not comprehensively tested. The hash-bound visual record is `pilot/r5_s05_softband_6to14.quality_review.json`.

## Integrity, time and decision

Actual prompt, decoded input, prepared references/VAE, Qwen presentation, full tokenization, conditioning, packed layout/positions, pair-snapshot contents and video/audio noise match the R3 full/native baselines. Both full and softband traces show1000 total attention calls,20 forwards, and450 routed calls exactly at zero-based indices6–14. Input pairing and execution gates pass separately.

Whole-prompt history wall times are1473.221s for archived full and1475.180s for softband. This is not a controlled speed benchmark: cache and passive-diagnostic/I/O effects are not isolated. No efficiency advantage is established.

Keep this result as the ordinary wider-band baseline. Do not expand radius or add capacity after seeing the outcome and describe it as preregistered. Utility evidence and novelty remain separate: the partial native improvement is real for this selected case, but it does not beat the existing full control and does not establish an architectural contribution. Any next feedback mechanism requires its own paired intervention and acceptance record.

Evidence: `compact_summary.json`, `pairs/{three_arms,full_softband}_threshold{0.3,0.5}.json`, `actual_input_noise_pair.json`, `operator_execution_gate.json`, `prompt_walltime_summary.json`, and the exact-history provenance archive. No GPU was started by this evaluator; all formal outputs and unknown outcomes were retained.
