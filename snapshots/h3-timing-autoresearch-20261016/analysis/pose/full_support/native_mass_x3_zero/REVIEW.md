# Full-clip exploratory preservation and propagation screen

This analysis was requested after the native/mass outcomes. It is an ancillary screen, not a preregistered main endpoint. The original four local timing windows and their rejection rules are unchanged. The exact method set here is native, all-steps mass, archived x3 and the byte-identical phase-zero control. Every comparison uses the common valid joint-frame intersection and shared confidence weights. Pairwise native-versus-each files are also retained so future arms need not change an earlier pair's denominator.

| Frames, confidence0.3 | Common coverage | Native | Mass | x3 |
|---|---:|---:|---:|---:|
| 0–140 | 99.1% | .43333 | .14601 | .17154 |
| 0–46, before intervention bin | 100% | .13555 | .14115 | .15569 |
| 47–67, intervention bin | 100% | 1.03923 | .10305 | .16844 |
| 68–140, after intervention bin | 98.3% | .46747 | .16198 | .18367 |
| 112–140, tail | 100% | .09711 | .11650 | .11255 |

These are unit arm-bone direction errors, not pixel MSE. Mass and x3 improve the high-error targeted section and much of the later motion, but both slightly worsen the already accurate early and final sections in this pose metric. Thus neither "strictly local effect" nor "no cost outside the target window" is supported. Confidence0.5 gives the same direction of these comparisons; full-clip common coverage is94.7%. Small peripheral differences could include pose-estimator error and are not established perceptual degradation.

The SVG curves plot all141 source-frame times without DTW. Missing observations remain gaps. Same-frame differences combine phase, pose, shape and detection errors; they cannot be read as missing actions outside the frozen diagnostic windows. This is one selected source/seed. Pose preservation alone also cannot establish edit identity, appearance or temporal visual quality.

Future hard/late/phase results belong to new snapshots with their exact compared method sets. Do not silently compare all-group numerical values between snapshots when the common support has changed.
