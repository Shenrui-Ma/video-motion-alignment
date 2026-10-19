# Wrong-reference-bin +4 is a confounded local fidelity failure

The formal `s05_full_seed1_offset4_x0` run succeeded (prompt `dc0cf459-a1ca-42b2-a33a-3b6896fef1ea`), and its raw video/exact history/audits/pose are archived. MP4 SHA256: `13f9e3c3dc2f6315ccbb7603be46bffb5b3f0846882c6a598df0f7f9b5d50452`.

The frozen primary50–65 combined-arm and right-arm lag estimates are **rejected**. At0.3, best-shift residuals .64952/.59473 exceed the .5 arm-direction shape gate. At0.5, combined-arm same-frame support is only .703125; the right arm retains .84375 support but its best residual .50231 still fails the shape gate. Unqualified numeric best shifts must not be reported as a clean directional response. Wrist-relative+5 at0.3 is not a substitute for the frozen combined-arm primary endpoint.

This also prevents the preregistered strict three-arm specificity gate from passing: source/offset0/+4/−4 common support at0.5 cannot exceed this arm's .703125, below the required .8, whatever the−4 result. No threshold relaxation or switch to right-arm primary is made. Lower-threshold error differences can still be described, with the limitation intact, after the complete control pair is available.

At0.3 the second window also fails shifted shape residual(.51825 combined/.52695 right). The third and fourth combined windows remain reliably+1 and+1, with right+2/+1; these agree across thresholds. Therefore the output is not uniformly ruined. Fixed frame55 shows a back-facing/turning torso and occluded arm, instead of the source's raised-arm configuration. Frame86 returns to a raised-arm pose. Gray clothing and white room remain in these fixed frames, but the back-facing primary pose limits identity/pose assessment.

The supported reading is local action-content distortion and measurement uncertainty under off-time routing, not pure signed phase transport. The reference offset is±4 nonuniform latent bins, corresponding to13 or16physical frames; the query region remains narrow and unchanged. The full pair and common-support errors are still pending. This is not an extra tuned condition or a replacement for the preregistered gate.
