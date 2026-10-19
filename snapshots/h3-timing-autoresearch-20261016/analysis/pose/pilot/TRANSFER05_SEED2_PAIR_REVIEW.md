# Additional source05 seed: timing improves, full edit preservation fails

The preselected noise seed 2026101312 provides a second stochastic sample of source05, not a second scene. Matched formal outputs are `s05_full_seed2_native_x0` and `s05_full_seed2_mass_x0`. Both passed exact successful-history and 1312×736 / 141-frame / 24-fps geometry admission. The mass retry prompt is `523346ee-97f0-4d20-99a9-caae70903283`; MP4 SHA256 is `852f37e4c99720c71606c3b976a86cc6353ffc2a42dd5bd9076adff831f56e17`.

**The timing result is positive, but this pair is not an overall successful video edit.** Native and mass both turn a large part of the source's white curtain/wall background into black curtain-like regions. This violates background preservation. It already occurs in native, so these frames do not establish that mass newly caused the problem. It remains an explicit quality failure in the inventory and cannot be dismissed because arm error improves.

## Frozen four-window findings

Positive lag means edited action later. Residual is arm-direction error after the best permitted local time shift; it is distinct from same-frame error.

| Frozen source window | Lag native → mass, confidence 0.3 | Lag native → mass, confidence 0.5 | Best-shift shape residual native → mass, 0.3 |
|---|---|---|---|
| 50–65 | +15 → −1 | +15 → −1 | 0.0936 → 0.0854 |
| 69–81 | +15 → −2 | Both rejected for coverage | 0.3630 → 0.4899 |
| 80–92 | +16 → −1 | +16 → −1 | 0.1002 → 0.0811 |
| 99–111 | +17 → −1 | +17 → −1 | 0.2476 → 0.0468 |

The primary right arm and shoulder-relative wrists move from +16 to −1 at both thresholds. Mass left-arm and body-XY features also give −1. Primary combined-arm coverage is 100% / 98.4% at thresholds 0.3 / 0.5 for both outputs; the primary phase result is reliable under the frozen gates.

The second window is a retained weakness: mass's combined-arm best-shift residual rises to 0.4899, its right-arm residual 0.5060 exceeds the 0.5 gate, and high-confidence same-frame coverage is only 65.4% versus native 80.8%. The high-threshold native lag also fails coverage over its search. A near-zero low-threshold combined-arm lag does not mean this window's motion shape is recovered.

Mass right-wrist geometric above/below-shoulder transitions at confidence 0.3 are 48/65/74/104, compared with source 49/66/76/106 and native 64/82/91/123. These provide supplementary event timing agreement, not a proof of action-omission recovery. No missing-person, multiple-person or ambiguous-selection frames occurred in either output.

## Same-support error and window-external screening

The following uses the intersection of source/native/mass valid joint-frame support and identical minimum confidence weights. These are same-frame pose discrepancies, not a standalone perceptual-quality score. The whole-clip/segment screen is explicitly exploratory; the original four lag windows were not moved.

| Region | Native error → mass error, confidence 0.3 | Shared support |
|---|---:|---:|
| Entire clip 0–140 | 0.7793 → 0.2012 | 98.9% |
| Before active bin 0–46 | 0.4493 → 0.1748 | 100% |
| Active bin 47–67 | 1.0724 → 0.1928 | 100% |
| After bin 68–140 | 0.9161 → 0.2219 | 97.9% |
| Tail 112–140 | 0.4738 → 0.1493 | 100% |

All these segments improve under the high threshold as well. The first, third and fourth original windows improve strongly on common support; the second remains shape/coverage-confounded. Therefore no increase in this arm-direction screen was observed outside the chosen bin in this particular seed. This does not establish absent visual side effects: the background-preservation failure is visible, and a sparse skeleton metric does not assess faces, texture, fingers, camera preservation or flicker.

Fixed frames 55 and 86 confirm the mass raised-arm / raised-leg poses rather than the delayed native poses; the coarse gray clothing remains. Both outputs contain the conspicuous altered black background. No extensive visual search or cherry-picked replacement event windows were used.

## Conclusion and provenance

This pair supports that the fixed same-time reference routing can improve the measured action timing for an additional preselected seed of the discovery source. It does not establish a novel mechanism, generalization to a new scene, superiority to ordinary hard masking or x3 weighting, online feedback, or overall successful editing. The latter fails background preservation here.

Full raw videos and exact history/config/conditioning/noise/router audits are archived locally with transfer-root provenance. Paired curves and full data are in `analysis/pose/pairs/source05_seed2_complete_pair/`. The initial transfer technical failure before sampling remains separately archived; it is not counted as a generated-video timing failure. This mass CPU evaluation ran in a verified ~10-minute primary-inference gap, without another DWPose process, and the subsequent scheduled consumer will use the exact-hash pose cache. Frozen metric source, thresholds and four windows were unchanged.
