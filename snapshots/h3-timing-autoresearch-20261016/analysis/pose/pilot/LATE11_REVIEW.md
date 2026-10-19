# Starting the same-bin route at call11 does not repair the selected phase error

The formal run `s05_full_seed1_mass_late11_x0` succeeded (prompt `bb507afe-2d7e-4823-9930-31069693c3dd`), producing the exact recorded MP4 `s05_full_seed1_mass_late11_x0_00001_.mp4`,141 frames,1312×736,24fps. Runtime was24:35. Its raw video, history, config, audit and pose outputs are archived.

The primary50–65 window still has a reliable delay of11frames at confidence0.3 and12frames at0.5, or approximately0.46–0.50seconds. Right-arm direction gives+11 at both thresholds; wrist-relative features give+12 at both; body features also give+12. There is no distinct-peak ambiguity or large-residual rejection in the primary combined-arm result. Best-shift residuals are .16086/.15242, and threshold0.5 same-frame coverage remains .828 for combined arms and .8125 for wrists. The isolated left-arm estimate at0.5 fails the .8 coverage gate and remains rejected.

Classification: **phase lag persists; this fixed late-start schedule did not repair the case**. This is not an unknown caused by total detector failure, nor proof that an action was irreversibly omitted. Relative to native+13, the phase changed by only1–2frames and did not reach the±2frame near-zero region. Right-wrist raising crosses the shoulder threshold at61 versus source49 and native63; the later crossings77/85/108 remain essentially native-like.

| Frozen window | Native combined-arm lag,0.3 | Late11 lag,0.3 | All-steps mass lag,0.3 |
|---|---:|---:|---:|
| 50–65 | +13 | +11 | 0 |
| 69–81 | +10 | +10 | −1 |
| 80–92 | +8 | +8 | 0 |
| 99–111 | +4 | +4 | −1 |

On the joint common support of source/native/mass/hard/late11/x3, primary error at0.3 is native1.124858, late11 .771300, mass .106138, hard .106380 and x3 .150512, with100% coverage. At0.5 it is1.129242/.785254/.108787/.111475/.154961 with82.8% coverage. Thus some same-frame pose discrepancy improves, but timing is still clearly wrong. The following windows retain near-native errors. These exploratory errors are not significance tests.

All141 frames contain one selected person, with zero missing, multiple or ambiguous selections. Frame55 was checked: the hands remain forward near the torso rather than in the source's raised-arm pose, consistent with the measured delay. Gray long sleeves, dark trousers and the room remain. This is only a fixed-frame pose/appearance sanity check, not a full identity or visual-quality evaluation.

The causal preintervention control passed: root's saved `audit/late11_preintervention_tensor_equality.json` reports exact video and audio tensor equality to native at x0_step005 and x0_step010. The analysis reads that artifact; it does not duplicate the tensor test. The route begins at zero-based call11 and continues through19. Actual video sigma starts at .90756303 (video t .09243697); call10 had sigma .92307693. Calling this the last9calls is accurate; calling it a low-noise terminal phase or a comparable fraction of a different paper's sampling schedule is not.

This failure narrows the control question: the reliable combined-arm signal sampled at call10 comes too late for this particular call11-start route to fully fix the current case. It does not prove that every actuator, every earlier observation or every schedule must fail. The schedule was chosen after baseline observability and remains a static test, not an online controller. The already preregistered earlier-start follow-up can be evaluated separately without changing these thresholds or windows.

Evidence: `LATE11_PRIMARY_DECISION.json`; `full_native_mass_hard_late11_x3_threshold0.3_common_support.json` and0.5; `../full_support/native_mass_x3_zero_hard_late11/` complete curves. The full-clip ancillary screen gives a small overall gain(.4199 native to .3967 late11 at0.3) but a slightly worse after-bin aggregate(.4670 to .4759), so it does not rescue the phase result. MP4 SHA256: `3e514fe8ee0a2bf3080e2ce34a50140c97c33fdd242357f1fca67698e87e91f0`.
