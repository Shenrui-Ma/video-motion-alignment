# Reference-relative RoPE perturbation: a one-sided timing response

Exact-history full-resolution runs zero / +12 / −12 all succeeded. Zero's full decoded video is bitwise RGB-equal to native across 141 frames. The −12 formal prompt is `7795a57b-79f0-484e-b48e-ec443695eaf8`, raw MP4 SHA256 `b8a79caccc85ab5dc565b400eb8bd9ddac4fe5cbcd63e1bc3f3bd40d8ea91fb6`. All raw MP4s, exact histories, input/noise/phase audits and CPU diagnostics are archived with provenance.

## Primary and preregistered gate

| Arm | Combined-arm lag, confidence 0.3 | Combined-arm lag, confidence 0.5 | Registered ±36 sensitivity |
|---|---:|---:|---:|
| −12 reference-relative coordinates | +3 | +3 | +3 at both thresholds |
| zero / native | +13 | +13 | +13 at both thresholds |
| +12 reference-relative coordinates | +13 | +13 | +13 at both thresholds |

Positive lag means the edited action occurs later. The two endpoints are separated by 10 frames and zero is at one endpoint. Thus the numerical order/separation portion of the preregistered exploratory gate passes, but this is **one-sided saturation, not a calibrated bidirectional phase actuator**. +12 did execute and altered output; its unchanged lag does not mean pixel identity. A smaller signed-pair fallback is not run this round and is not a failed experiment.

For −12, all five primary features (combined arms, left arm, right arm, shoulder-relative wrists and body XY) give reliable +3 under both thresholds. Combined-arm best-shift residual is 0.08288 / 0.08296 with same-frame coverage 100% / 98.4%. No missing-person, multiple-person or ambiguous-selection frames occurred. The reduction from +13 to +3 is a partial timing correction; it does not meet a near-zero ±2-frame definition.

## Original four windows and shape qualifications

| Window | Native lag, 0.3 | +12 lag, 0.3 | −12 lag, 0.3 | −12 best-shift shape residual, 0.3 |
|---|---:|---:|---:|---:|
| 50–65 | +13 | +13 | +3 | 0.0829 |
| 69–81 | +10 | +11 | +2 | 0.4570 |
| 80–92 | +8 | +10 | +1 | 0.0847 |
| 99–111 | +4 | +5 | +1 | 0.0602 |

At confidence 0.5, −12's second window is rejected for coverage (71.2%); the other three combined-arm lags remain +3/+1/+1. The second-window residual is large even at the lower threshold and is not presented as complete motion-shape recovery. +12 also retains its residual/coverage rejections. Common-support three-arm errors retain insufficient-support flags rather than replacing those cells with a success claim.

On the first window's identical three-arm support, zero / +12 / −12 errors are 1.1260 / 1.1090 / 0.3389 at confidence 0.3, and 1.1361 / 1.1193 / 0.3452 at confidence 0.5 (support 100% / 96.9%). Thus −12 improves same-frame pose discrepancy as well as lag; this is not a purely unconstrained alignment-score improvement. Supplementary −12 right-wrist shoulder crossings are 52/69/77/106 versus source49/66/76/106.

## Quality screen and interpretation limits

Fixed overlays 55 and 86 preserve the white room/curtains and coarse gray-shirt/dark-trouser character appearance, without the large black-background failure seen in both seed2 outputs. Raised-arm timing is visibly closer, while frame55 still need not match exact leg phase. This is a limited geometric/appearance screen, not full-video identity/flicker/texture validation.

The fixed full-clip common-support screen retains all arms and compares pre0–46 / bin47–67 / post68–140 / tail112–140. At confidence0.3, native / −12 errors are 0.1351/0.1315, 1.0244/0.3915, 0.4644/0.1633, 0.0963/0.0633. All four regions improve on this skeleton metric. It does not prove absence of visual side effects. These values use the complete available-arm common support; the fixed native-pair curves are separately retained.

The operator perturbs the native Q/reference relative temporal coordinate offset by ±20 RoPE units, corresponding to the configured ±12 physical-frame coordinate amount. It does not realign temporal origins or literally shift decoded frames. The native gap of235 units is not a141-frame action delay. The observed sign is empirical; a general monotonic law has not been established from these three points on one selected seed.

A subsequent fixed −12 intervention beginning at model call11 can test controllability after the first *sampled reliable* x0 observation at call10. It must keep amplitude, query window and layers fixed and verify earlier005/010 tensors exactly equal native. Even a positive result would establish fixed late controllability, not an online monitor/controller; calls6–9 were not observed, and no exact first-detectable time is known. This intervention and its result must be registered/reported as a later diagnostic selected after the all-step response.
