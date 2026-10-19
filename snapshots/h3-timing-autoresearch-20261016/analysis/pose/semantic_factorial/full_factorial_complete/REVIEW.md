# Semantic clock factorial: one-case interaction, both consistent main-effect gates fail

A=P0/T0, B=P6/T6, C=P0/T6, D=P6/T0. Both frozen confidence thresholds give primary arm lag **A13, B5, C13, D13 frames**.

| Predeclared contrast | Threshold0.3 | Threshold0.5 | Interpretation |
|---|---:|---:|---|
| C−A: timestamp at P0 | 0 | 0 | no primary phase response |
| B−D: timestamp at P6 | −8 | −8 | conditional response |
| D−A: pixels at T0 | 0 | 0 | no primary phase response |
| B−C: pixels at T6 | −8 | −8 | conditional response |
| B−D−C+A | −8 | −8 | descriptive interaction only |

Neither factor passes the preregistered >=4-frame effect with consistent direction at both levels of the other factor. No condition-specific response is silently promoted into a consistent main effect. This is one selected source/identity/seed, not a significance test or an independent validation set.

Four-arm shared-support main-window errors at threshold0.3 are A/B/C/D **1.131/.651/1.119/1.128**, support1.0; at0.5 **1.145/.659/1.124/1.144**, support.922. Whole-video errors at0.3 are .430/.270/.456/.434, support.993. The pre-bin range0–46 worsens slightly for B(.136→.149) and C(.136→.151). At0.5 the middle two windows have shared support.731/.673, below the frozen.8 requirement, and remain insufficient. Original per-run shape/coverage rejections are retained.

The fixed55/86 screen of B/C/D retains gray clothes and the white curtain/room; it is not a full identity/all-frame quality measure. B retains+5frames and is only partial improvement, not full temporal alignment.

Physical sample shiftP6=.25s is distinct from displayed text shift=.3s. Native one-decimal rounding gives A paired mean.25→label.2 (−.05s), while B mean.5→label.5. A/B each use timestamp labels associated with their samples, subject to rounding. The joint-only effect may involve quantization or nonlinear image/text context interactions. It does **not** establish generic frame-sampling superiority, a temporal-RoPE defect, Qwen2fps losing the action, or a universal dual-clock conflict. Timestamp text changes contextual Qwen embeddings, not direct RoPE.

`actual_encoding_acceptance.log` passed the dedicated all-arm actual-pixel/timestamp/conditioning/noise checks; protocol copy preserves its original preregistration. Initial local evaluator launch failed before evaluation because it assumed the protocol was also in remote primary/configs; it was then supplied as an unchanged verified copy under analysis/pose. No thresholds or outcomes were changed. Parent owns the additional actual native replay on the semantic GPU0 runtime. Until that replay gate is resolved, retain the runtime attribution qualification.
