# H3 Temporal Router diagnostic

This is a task-local, frozen-weight inference intervention. It makes no novelty
claim. It uses the existing H3 cloned-model DiT block replacement hook and does
not edit shared Core or checkpoint files.

`H3TemporalRouter` supports `native`, `diagnostic`, `mass_preserve`, `hard_route`.
All modes force the same explicit CUDA Flash attention operation. Block and
forward-step bounds are zero-based, half-open. The frame interval is inclusive;
it is mapped through H3 positional bins, not asserted to be the exact VAE field.
`time_offset` shifts the reference-bin center, clips it to a valid bin, and
then clips its radius-0/1 neighborhood without repeating boundary bins.

For selected target queries, let O be full attention, O_ref reference-only
attention and m_ref the reference group's probability. `mass_preserve` uses
O + alpha*m_ref*(O_aligned-O_ref). It preserves that reference group's total
probability in exact arithmetic and changes its temporal distribution.

`hard_route` is the attention result with nonaligned reference keys excluded.
It independently evaluates non-reference and aligned-reference attention and
combines their outputs via logaddexp LSE normalization. It does not subtract
nearly equal bf16 outputs to infer the non-reference contribution. Alpha blends
the hard-route result with O. Alpha=0 returns unmodified full Flash output.

Each forward writes counts and sampled mass/correction/finite summaries.
At block25 and steps0/5/10/15/19, every mode additionally records reference-only
temporal attention distributions from at most8 heads and8 center spatial
queries per selected latent frame. These are pre-intervention internal
attention readouts, not evidence of physical action timing or correspondence.
No full N-by-N attention matrix is created.

CPU validation: 12 tests passed, 4 CUDA-only tests skipped locally, using
`/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python`
and `tests/test_temporal_router.py -v` on 2026-10-16. Dense probability
redistribution/masking equivalence, outside-query bitwise preservation,
alpha0 identity, near-unit reference mass, and temporal readout normalization
are covered. CUDA tests must be run in the target runtime before inference:

```sh
H3_ROUTER_TEST_DEVICE=cuda python tests/test_temporal_router.py -v
```

Production supports one batch, equal Q/K/V dimensions, no preexisting attention
mask or override, and sequential non-CFG H3 block calls. It intentionally fails
instead of silently selecting a different attention backend.
