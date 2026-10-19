# Indexing clarification (no execution or frozen-metric change)

`step_start=6, step_end=15` is a half-open interval in **zero-based model-forward indices**: 6,7,...,14. It corresponds to the **7th through 15th model forwards** in ordinary one-based counting, nine forwards total. The Full and R5 controls use exactly this interval.

R4 passive captures at zero-based indices6,10,14 correspond to the 7th,11th,15th forwards. The primary R4 capture remains index6. It must not be replaced by `x0_step005`, which is index5/the 6th forward. Earlier prose saying only “calls6..14” or “calls6/10/14” is ambiguous; read it according to the explicit zero-based configuration above.

This clarification changes no graph, saved tensor, source-frame window, threshold, sampling schedule, or frozen artifact hash. Video frame indices, VAE latent-bin indices, and denoising-forward indices are separate coordinates.
