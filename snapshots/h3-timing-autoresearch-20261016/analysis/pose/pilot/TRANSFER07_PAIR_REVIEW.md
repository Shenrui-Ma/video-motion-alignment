# Source07 related-scene transfer improves phase, with retained qualifications

The exact-history mass run `s07_full_seed1_mass_x0` succeeded (prompt `aa44a87d-c3e9-45e8-817e-b4c06fc0fecc`). Its141-frame,1312×736,24fps video, audits, pose and source provenance are archived. MP4 SHA256 is `b7e3753d0ad74d25e509d92dfd601b6eda7062d318d1411f429142239cfc6fc7`.

The frozen primary54–69 window changes from native right-arm lag **+15/+15** to mass **−1/−1** at confidence0.3/0.5. Mass combined-arm, wrist-relative and body features also give−1/−1. Native combined-arm gives+15 only at0.3; at0.5 its coverage .78125 fails the .8 gate. The comparison must therefore not be described as a dual-threshold combined-arm baseline success. Mass primary same-frame coverage is .90625/.8125 for combined arms and1.0 for right arms at both thresholds; its best combined-arm residual is .14186/.08793 and right-arm residual .11997/.11997.

| Original window | Native combined,0.3 | Mass combined,0.3 | Native right,0.3/0.5 | Mass right,0.3/0.5 |
|---|---:|---:|---:|---:|
| 54–69 | +15 | −1 | +15/+15 | −1/−1 |
| 75–88 | rejected shape/multiple phases | −1 | rejected | −1/−1 |
| 98–111 | −5 | −2 | −5/−5 | −2/−2 |

The second window becomes a reliable near-zero phase match, with combined residual .14310/.13095 and right residual .14622/.14622. This is not a numeric lag improvement from a trustworthy native+15: native was explicitly rejected there. The final combined-arm window still fails coverage at0.5 (.76786), while right-arm−2 remains reliable. Isolated left-arm primary is rejected for small shift benefit at0.3 and coverage at0.5; those failures remain in the JSONs.

On source/native/mass common support, the primary combined-arm same-frame error at0.3 improves .68211→.17730 (coverage .875). At0.5 common coverage .78125 is insufficient, so its numeric errors .66579→.12221 are descriptive only. Original second-window same-frame errors improve .97416→.34277 at0.3 and .96744→.33133 at0.5, with adequate common coverage. The third window improves at0.3 but its0.5 common support is insufficient.

The full141 auxiliary screen improves .45641→.25502 at0.3. However, the before-bin segment0–51 becomes worse, .16372→.20389 at0.3 and .14709→.18961 at0.5. This modest outside-target cost must be reported, not hidden by full-clip averaging. The after-bin segment73–140 and tail112–140 improve at0.3; their0.5 common support is insufficient. Per-frame curves and every segment are in `../pairs/source07_complete_pair/`. Decorative chart shading uses this case's positional52–72 bin, not source05's bin.

All141 frames have one selected person, with no missing, multiple or ambiguous selection. Fixed frames55 and86 show the gray-shirt edited person, bed, wardrobe and bright side wall retained. This limited screen did not reveal the seed2 black-curtain failure; it does not establish identity accuracy or all-frame visual quality.

This is evidence of transfer to a second real recording with related choreography, selected because its old result was already known to lag. It is neither an unseen-domain test nor an independent newly sampled seed. The new native07 is not RGB-bitwise equal to the archived result, despite root's actual input/noise equality audit. Known execution graph differences remain old factor1 EventEmphasis versus new native router and passive capture; do not attribute the small pixel changes solely to numerical variation without another control. See `TRANSFER07_NATIVE_REVIEW.md` and `../../replication/source07_actual_input_reuse_audit.json`.

The result supports continued testing of time-correspondence routing on this problem. It does not distinguish conservation from ordinary hard routing or reference amplification; those remain necessary baselines, and the same-budget wrong-reference-bin controls are still pending.
