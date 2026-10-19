# R9 hold2: verified execution, unsuccessful final correction

The ordinary two-consecutive-aligned stopping rule did not repair the selected delayed example. At confidence threshold 0.3 its main-window lag is +12 frames, compared with native +14, immediate-stop feedback R6 +13, and fixed Full +2. At threshold 0.5 both feedback outputs are unknown. R9 therefore fails the frozen complete-repair gate (absolute lag at most 2) and the partial-repair gate (at least 4 frames less absolute lag than native). The 1-frame difference from R6 is not evidence of a useful control improvement.

All indices below are zero-based. All four source windows and detector thresholds remain frozen. This is one previously selected failure, with reused same-host baselines, not a new independent sample or a general failure-rate estimate.

## Actual controls

- Exact success history, graph identity, one SaveVideo output, SHA checks, and 1312×736/141-frame/24-fps geometry passed.
- Actual conditioning, reference encoding, tokenization, embeddings/tags/packed layout and actual noise streams agree across R2 native, R2 Full, R6 and R9. See `actual_input_noise_pair.json`.
- Saved video and audio x0 at index5 are bitwise equal to R6 before the first possible intervention at index6. R6 already passed the corresponding R4-native prefix control. No inference from container-MP4 hashes is used.
- Independent hold2 audit passed all state transitions, streak resets, previous-callback latching, all50-or-zero block routes, and terminal callback19 nonmutation. The checker also rejected five deliberately corrupted audit cases.
- All 8 intermediate tensors (5/6/7/8/9/10/15/19) plus final are actually present and match manifest hashes, float32 dtype, expected shapes and finite-value checks. Captures alone do not prove independently decoded early motion.

## Frozen final pose results

Positive lag means edited motion occurs later than the reference. `unknown` is retained rather than treated as zero or as a successful correction.

| Run | Threshold | 50–65 | 69–81 | 80–92 | 99–111 |
|---|---:|---:|---:|---:|---:|
| Native | 0.3 | +14 | +12 | +11 | +6 |
| Native | 0.5 | +14 | unknown | +11 | +6 |
| Fixed Full, indices6–14 | 0.3 | +2 | +10 | +9 | +5 |
| Fixed Full, indices6–14 | 0.5 | +2 | unknown | +9 | +5 |
| R6 immediate stop | 0.3 | +13 | +11 | +9 | +6 |
| R6 immediate stop | 0.5 | unknown | unknown | +9 | +6 |
| R9 hold2 | 0.3 | +12 | +10 | +9 | +5 |
| R9 hold2 | 0.5 | unknown | unknown | +9 | +5 |

Direct Full/R9 common-support main-window error at threshold0.3 is worse for R9 in all three geometric features:

| Feature | Common support | Full error | R9 error |
|---|---:|---:|---:|
| Arm direction | .9375 | .294651 | .882169 |
| Relative wrist | .8750 | .276169 | .918834 |
| Normalized body coordinates | .973958 | .192407 | .423539 |

At threshold0.5 main arm and wrist support is only .6875, below the frozen .8 gate; do not use those comparisons as accepted shape evidence. Body support is .869792 and errors are .174671 versus .395772.

For R6/R9 and for all four arms together, even threshold0.3 main arm support is .796875 and wrist support .75. These narrowly fail .8 and remain rejected; the threshold was not relaxed. There is no accepted arm-error superiority claim over R6. The usable body-coordinate differences between R6 and R9 are small (.397091/.395699 at threshold0.3 for the direct pair).

## Outside-window screening

Direct Full/R9 arm-direction errors, threshold0.3, same valid support within each row:

| Frames | Support | Full | R9 |
|---|---:|---:|---:|
| 0–46 | 1.0000 | .142700 | .141822 |
| 47–67 | .952381 | .384322 | .828404 |
| 68–140 | .996575 | .549896 | .549982 |
| 112–140 | 1.0000 | .175050 | .158316 |
| 0–140 | .991135 | .382337 | .436160 |

The tail's small improvement does not rescue the target failure or imply global quality superiority. The full curves and both thresholds are retained in `pairs/`; these screens do not classify semantic action deletion.

## What the controller actually did

Actual guided forwards were `[6,7,9,10,11,12,13,14,15,16,17,18,19]`: 13 forwards/650 block corrections, versus 13/650 for R6 and 9/450 for fixed Full. Observer lags at callbacks5–19 were `[11,1,1,11,7,10,10,10,10,10,10,10,10,10,10]`.

Callback6's first near-zero observation retained guidance at forward7. Callback7's second near-zero observation stopped forward8. Callback8 then reported +11 and reactivated forward9. This is verified observer/controller behavior, not yet independently decoded proof of motion rebound. R6's missing index6/7/8 tensors cannot be reconstructed or filled from R9.

NFE remains20. The observer's synchronous copy/hash/normalization/readout/decision cost was17.495s, excluding JSON writes. Whole-prompt R9 time was1751.625s, versus1729.061s R6 and1614.145s Full. These are different executions including loading/decode/audit, not a controlled speed experiment. Following the latest user preference, efficiency is recorded here without using speed as a diagnostic or adding speed-driven experiments.

## Fixed-frame visual scope and conclusion

Archived frames55/86/105 were inspected. The gray-shirt/dark-trouser adult male edit, white curtains, cabinet, table, bench, shelf and letterbox layout remain visible. At55 the arms reach forward/down and the feet remain near the floor, rather than the desired same-time head-hand/raised-leg phase; at105 the broad open-arm/extended-leg action is present. This supports a temporal mismatch interpretation rather than asserting that the action is semantically absent from the entire video.

This is a limited gross-layout/edit-presence review. Exact Sam likeness, full-video flicker, facial and hand quality are unverified. The technical execution is valid; the final correction is unsuccessful. The result rejects this two-consecutive stopping rule on this case, not all feedback, held guidance, or architectural approaches. Any subsequent mechanism claim needs its own matched control and independent output evidence.
