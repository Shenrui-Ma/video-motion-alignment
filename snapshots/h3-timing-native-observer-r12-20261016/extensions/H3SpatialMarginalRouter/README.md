# Staged spatial-marginal reference diagnostic

This package is isolated from every active extension. It has not been installed,
loaded into a model, or tested on a GPU. It registers `H3SpatialMarginalRouter`,
with `native`, `diagnostic`, and `spatial_marginal` modes. Do not substitute it in
an active service. Root owns admission, deployment, and experiments.

## Operator

At fixed Q/K/V, let A_q(u,s) be the softmax within all reference-video keys,
where u is reference time and s is its fixed spatial-grid location. Let m_q be
native attention mass on the reference-video group, and let q belong to target
latent frame t. Define M_q(s) = sum_u A_q(u,s). The diagnostic is

    B_q = sum_s M_q(s) V(t,s)
    O'_q = O_q + alpha*m_q*(B_q - sum_{u,s} A_q(u,s)V(u,s)).

For alpha in [0,1], its equivalent conditional reference weights are

    A'_q(u,s) = (1-alpha) A_q(u,s) + alpha*1[u=t] M_q(s).

The reference-group mass, reference spatial marginal, and all other-key
contributions are preserved at the SAME input state in exact arithmetic. At
alpha=1, reference values come only from the target bin. No spatial tracking or
motion compensation is asserted: fixed grid positions need not be the same
object. V is a contextual internal feature, not an identified motion channel.

Adding any time-constant spatial field S(s) to reference V leaves the correction
unchanged at fixed Q/K. A fully time-constant V yields zero correction. The
whole output still responds natively to S(s); invariance is of the correction,
not the original attention output. BF16 kernel/casting error remains possible.

## Distinction, not a novelty claim

Full same-frame routing uses A_q(t,s)/sum_s A_q(t,s), which generally changes
the spatial marginal. This operator instead uses sum_u A_q(u,s). The DC-split
operator A + (A_same-A)(I-P_temporal) can have negative effective coefficients;
this operator has nonnegative coefficients. CPU tests include concrete
counterexamples and independently construct full dense output probabilities.

It nevertheless IS expressible as a data-dependent bias/mask on unchanged QK
logits and unchanged V. At alpha=1, mask u != t, and choose new target-frame
logits L_ref + log M_q(s); their logsumexp is the original L_ref. Thus this is
not outside attention-reweighting mathematics. It must not be marketed as a
new backbone or presumed novel merely because its implementation repeats V.
The real diagnostic question is whether preserving spatial allocation while
changing time retains the useful timing effect and reduces collateral changes.

## Implementation and cost

`core.py` copies the audited Flash backend, layout/state/readout lifecycle from
round1's H3TemporalRouter. Its new helper processes each selected target bin
sequentially. It repeats that bin's V across all reference times and computes
Flash(Q_bin,K_ref,V_repeated), never storing an N-by-N attention matrix. Original
Q/K/V and unselected output rows are unchanged; alpha=0/native use the original
single Flash fast path. Radius and time_offset must both be zero.

For the actual 56 heads, head dimension128, 42 reference bins, 943 spatial tokens,
6 selected bins, reference V is 567,791,616 bytes (about 541.49 MiB). One repeated
buffer is live at a time. Its output is 81,113,088 bytes (about 77.36 MiB), also
comparable to the existing selected-output buffers. No additional model exists.

Attention calls per active layer: full packed attention + original reference
branch + 6 repeated-V branches = 8, versus 3 for full same-frame routing.
The QK pair count is N^2 + 2*(6*943)*(42*943), compared with
N^2 + (6*943)*(42*943) + 6*943^2 for full routing. At N=87592 this is about
2.77% more pair products than full routing (not a measured runtime prediction).
Kernel launches, repeated V bandwidth, and device behavior require GPU timing.
There is no per-layer CPU synchronization beyond the inherited optional sparse
readouts; per-forward audit flush is inherited. Diagnostics report sampled
finite/mass/correction ratio, not measured full spatial marginals.

## CPU and future admission

Run tests with the existing local torch interpreter and CUDA_VISIBLE_DEVICES='':
`tests/test_spatial_marginal.py` (12 tests). These validate FP64 exact algebra,
FP32/BF16 tolerance, fixed-input invariants, immutable inputs, strict same-time
geometry, separate node registration, and 450 active layer calls for [6,15).

`scripts/gpu_spatial_marginal_smoke.py` is root-operated only. Tiny mode uses
actual head count/dimension and strided BF16 QKV, ordinary and near-unit reference
mass. Optional --actual-shape uses [1,56,87592,128] without dense attention.
It verifies alpha0/untargeted/native bitwise comparisons and tolerance for BF16
versus independent FP32 dense transport. It must run only after GPU admission;
no GPU result currently exists. Static cancellation is tolerance-based, not
bitwise, because whole-window and per-bin Flash launches can round differently.

Any actual comparison should first pass same-host native/passive replay and
actual condition/noise hashes, then use the identical source, seed, prompt,
geometry, source window50–65, blocks[0,50), calls[6,15), alpha1. Compare with the
same-host full/DC/static arms; no hyperparameter search is implied. Spatial
marginal preservation alone does not imply preserved identity/background or
successful action timing, and successive hidden states diverge after editing.
