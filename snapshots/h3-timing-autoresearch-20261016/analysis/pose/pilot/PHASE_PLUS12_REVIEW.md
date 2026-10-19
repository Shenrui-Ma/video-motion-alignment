# Reference-coordinate +12: reliable primary lag remains

Formal run `s05_full_seed1_phase_plus12_x0`, prompt `968e1d6a-ba7b-4ce1-b80e-83ad91862530`, exact successful history and config geometry checked: 1312×736, 141 frames, 24 fps. Raw output SHA256 `843275a99a4de48bcb1d88d374eef5bbfb5595a46d9611ea5fb58a4cb9d97648`. All files and failures remain in the formal inventory. This report precedes the −12 result; it does not decide the signed-pair criterion.

## Frozen primary result

| Measure, frames 50–65 | confidence 0.3 | confidence 0.5 |
|---|---:|---:|
| Both-arm reliable lag | +13 | +13 |
| Right-arm reliable lag | +13 | +13 |
| Wrist-relative reliable lag | +13 | +13 |
| Body-XY reliable lag | +13 | +13 |
| Left-arm reliable lag | +14 | +14 |
| Both-arm same-frame coverage | 100% | 98.4% |
| Both-arm best-shift residual | 0.1404 | 0.1398 |

Positive lag means the edited action is later. This is the same primary +13-frame lag as zero/native, not zero pixel change. Independently registered ±36 first-window sensitivity gives the same +13 lag under both thresholds; the expanded search remains less calibrated than the frozen ±24 primary search.

Under confidence 0.3, subsequent both-arm windows 69–81 / 80–92 / 99–111 give +11 / +10 / +5. Right-arm 69–81 is rejected for large residual even after shift; at confidence 0.5 the second window and combined-arm third window are rejected for coverage. These are retained abstentions, not missing-action findings. Right-wrist above/below-shoulder transitions at confidence 0.3 are 63/78/87/111, versus source 49/66/76/106; geometric transition times are supplementary and subject to pose uncertainty.

No person-missing, multiple-person, or ambiguous-selection frames occurred. Fixed overlays 55 and 86 show the gray long-sleeve / dark-trouser appearance and room retained; frame 55 still has low, forward hands rather than the source raised-arm event. Frame 86 has crossed-arm ambiguity, so it does not override rejected local metrics. This limited check is not a face-identity or full-video flicker assessment.

## Execution and interpretation

Root's independent audit reports 1000/1000 finite phase calls; the intervention was executed. The native generated-query/reference-key temporal coordinate gap is 235 RoPE units; +12 is a +20-unit perturbation on that native offset, not temporal-origin realignment and not a literal 12-frame shift of video pixels. Native coordinate separation is not an observed 141-frame action delay.

The posthoc full-clip common-support screen includes this arm in `analysis/pose/full_support/native_mass_x3_zero_hard_late11_phaseplus`. On the confidence-0.3 all-arm shared support, native / +12 error is 0.4187 / 0.4736 for all 141 frames, 1.0258 / 1.0222 in bin 47–67, and 0.4665 / 0.5606 after bin 68–140. Thus this coordinate perturbation has no demonstrated primary timing benefit and has larger later same-frame pose discrepancy. That auxiliary discrepancy is not a pure phase or perceptual-quality metric.

We must still measure −12 before applying the preregistered ordered-response / fallback decision. No threshold, window, metric source, or generation setting was tuned after observing this result.
