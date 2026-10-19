# H3 reference-only temporal RoPE actuator — staged diagnostic v1

This is a manual/oracle actuator for testing whether the frozen H3 editor has
a controllable response to a restricted reference-time perturbation. It is
not an automatic feedback controller, not a new training method and not an
established paper contribution. It has not been installed or run on a GPU.

## R17 binding and correction to an intermediate review

The actual R3 Ref2VA attention audit records 56 heads × 128 = 7168 attention
channels, projected by `out_proj` into hidden_size5376. FinalLayer input5376
does not imply42 attentionheads. An intermediate R17 review made that inference;
it is explicitly withdrawn. R17 reads all50 actual `blocks[i].attn` attributes,
checks QKV/out projection shapes and per-layer agreement, and pins them to the
recorded R3 audit. CPU toys cover both42 and56 contracts without changing weights.

Frozen diagnostic: physical delta±4, alpha0.5, video source window50–65,
zero-based forward indices[6,15), all50 blocks, all spatial rows. No spatialmask,
pose feedback, new training, LoRA change or parameter search. A zero graph is
provided for verification, but not in the sealed two-arm generation queue.

Inactive/zero wrapper calls the exact passed native attention function and
forwards kwargs, without auxiliary Flash. Nonzero arithmetic is unchanged;
its full output still comes from explicit aten Flash/LSE, whose equivalence to
the actual native backend must pass the GPU smoke. Group invariance remains
exact-arithmetic, fixed-layer-input only. R17 CPU tests are not GPU evidence.

Actual source and parent attention evidence hashes, actual all50 module shapes,
reference SHA and actual copied inv_freq are written to the per-run audit.
Auxiliary EventAudit/PairAudit/X0 output roots are isolated toR17.

## Exact intervention

Native H3 attention arrives with normalized, already RoPE-rotated Q/K and V,
shaped `[1,56,N,128]`. The checkpoint uses partial split-half rotary encoding:

| Coordinates | First half | Paired second half |
|---|---|---|
| Time | 0:16 | 48:64 |
| Height | 16:32 | 64:80 |
| Width | 32:48 | 80:96 |
| Not rotated by native RoPE | 96:128 | — |

Source evidence is the current Comfy H3 `rope_freqs` and
`rope_rotation_table`: it constructs `[t,h,w,t,h,w]`, with 16 frequencies per
axis and matrix `[[cos,-sin],[sin,cos]]`. The actuator copies the actual
`diffusion.rope.inv_freq` buffer at installation, checks its 16 finite values,
and records values/dtype/raw-byte SHA. It never synthesizes a 10000-base grid.

The supplied `delta_frames` is measured in **physical frames at 24 fps**.
The extra rotary coordinate is `delta_frames * 5/3`. It is not a count of
latent bins. H3's varying `(1,4,4,4,4)` physical-frame spans make those units
different.

For selected output-video Q rows only, clone Q and apply this extra temporal
rotation to pairs 0:16 ↔ 48:64. All spatial and unrotated channels remain
bitwise unchanged. Use the clone solely in a separate attention operation
against **all reference-video K/V**. Do not modify the global Q, any K/V, the
reference portrait, text, audio, target-video self-attention, native position
IDs or the model's checkpoint buffer.

Let `O` and `L_all` be native full-attention output and logsumexp. On selected
queries, compute `O_ref,L_ref` using original Q against the complete reference
video, and `O_rot,L_rot` using temporally rotated Q against the same reference
video. Define:

```
m_ref = exp(L_ref - L_all)
O_new = O + alpha * m_ref * (O_rot - O_ref)
```

`alpha` is in `[0,1]`. Original group mass is clamped only against positive
floating-point LSE excess; bounded audit statistics expose that excess.
For a fixed input state, this replaces the conditional distribution inside
the reference-video group while preserving its native total mass. Every
non-reference key contribution is unchanged in exact arithmetic. For
`alpha=1`, an equivalent explicit-logit description is:

```
reference logits = rotated_logits + L_ref_original - L_ref_rotated
other logits     = original_logits
```

Therefore this normalization/decomposition is **not itself new mathematics**.
The implementation's two extra local Flash calls avoid an N×N dense mask or
probability matrix. The production path uses the same explicit Flash/LSE
backend as the audited router. Work arithmetic is FP32 for FP16/BF16 attention;
FP64 is retained in dense toy tests. Numerical roundoff prevents interpreting
the conservation statement as an exact bitwise probability guarantee on GPU.

At the low-level math helper, zero returns one explicitFlash output. At the
production wrapper, `alpha=0`, `delta_frames=0` and nonselected blocks/steps
call the passed native function directly; no auxiliary kernel or addition occurs.
The block node itself uses a nonempty checked physical window.

## Scope and signs

Default requested physical window 50–65 maps to latent bins `[14,20)`, whose
H3 positional coverage is physical frames **47–67**. This is a positional-bin
selection, not an exact statement about VAE receptive fields. Every spatial
query within those bins is selected. There is no automatic subject/hand ROI
and no evidence yet that the change only affects the short gesture.

Positive delta adds to the query time coordinate. A deliberately simple
sinusoidal toy with identical content moves its local best-matching reference
key forward for positive delta and backward for negative delta. This verifies
the rotation convention and units only. Real H3 has cross-stream positional
origins, periodic frequencies, content-dependent attention and many coupled
layers. It is **unknown** whether either sign reduces an observed +13-frame
action lag, or whether the response is monotonic. A +13-frame setting is not
claimed to cancel a +13-frame observed lag.

Conservation holds relative to the native attention at the **same current
layer input**. Subsequent hidden states differ; other groups' mass in later
layers or separate runs need not stay the same. Likewise, outputs outside
the direct query window may change through later self-attention and VAE
coupling. Edit identity, camera, background and overall motion must still be
checked rather than assumed unaffected.

## Installation interface, pending root review/admission

Node name: `H3PhaseRoPE`.

```
model, positive,
delta_frames, alpha, start_frame, end_frame,
block_start, block_end, step_start, step_end,
run_id, audit_dir
```

Block and step intervals are half-open, with bounds inside `[0,50]` and
`[0,20]`. The wrapper verifies exactly ordered blocks, at most 20 forwards and
an unchanged 21-entry decreasing sigma schedule ending at zero. A completed
audit means 20 complete 50-block forwards. It refuses pre-existing DiT block
patches or attention overrides. Existing recorder sampler wrappers can be
retained, because they are not DiT block patches.

For the current graph, a future new arm should **replace node 50**'s router
with this node, keeping `model=["41",0]` and `positive=["51",0]`. Do not place
it on top of the H3TemporalRouter output. The downstream passive recorder may
still take `["50",0]`, then feed BasicGuider as already planned. Use unique
run IDs and output paths. Root separately adds this plugin to the
task-local custom-node whitelist and install it only after review; this
implementation performs neither step.

Audit logs contain actual checkpoint frequencies, physical and RoPE offsets,
layout, sigma schedule, per-block/per-forward call counts and once-per-forward
summaries of bounded reference-mass/correction/finite statistics. Statistics
sample at most 8 heads × 128 queries × 16 channels; they are not full output
finite validation and not action-timing ground truth.

## Required first experiment and falsification

After numerical GPU smoke/admission, test matched native/zero, `+delta` and
`-delta` with the same seed, source, portrait, prompt, resolution, sigma grid,
model/precision and edit settings. A modest nonzero magnitude plus an
intermediate alpha is a defensible first oracle; avoid interpreting a failed
all-layer/all-step `alpha=1` run as proof that every narrower intervention is
impossible. Do not change settings after looking at one arm without recording
a new exploratory comparison.

Evaluate signed gesture lag, zero-shift error, best-aligned shape error,
visibility/confidence, edit identity and actions outside the selected window.
The actual lag sign must be independently calibrated using synthetic time
shifts in the evaluator. Low-confidence/occluded poses remain unknown.

- Opposite offsets produce reproducibly opposite lag responses while edit
  quality holds: supports a controllable actuator, not yet automatic control.
- Both signs help similarly: generic perturbation or concentration effects
  remain plausible; this does not establish signed phase correction.
- Both harm edit/motion quality, or no repeatable response: rejects these
  settings; it does not justify a new mechanism claim.
- A single favorable seed/example: exploratory evidence only, followed by
  matched seeds and a good-case nonregression control.

Before an online controller, the independent x0 observer must first reliably
read signed action timing and distinguish unknown visual states. This plugin
contains no pose extraction, threshold, tracking, teacher, gradient optimizer,
automatic time-window selection or feedback schedule.

## Prior overlap and possible distinction to test

This section uses the already completed local primary-source literature
audit, not a new novelty search. See `literature/phase_feedback_second_audit.txt`.

- [DiTFlow](https://arxiv.org/html/2412.07776v2), §§4.2–4.3 and Appendix A,
  obtains attention motion flow, minimizes reference/generated motion
  differences, and performs test-time optimization of latent or positional
  embeddings, including gradients into Q/K 3D RoPE. Frozen-backbone motion
  correction through positions is already explicit prior art.
- [RoPECraft](https://arxiv.org/html/2505.13344v1), §§4.1–4.3 and Algorithm 2,
  initializes spatial RoPE from optical-flow trajectories, then optimizes
  rotary embeddings using flow-matching and Fourier-phase objectives.
  Its initial trajectory transform deliberately preserves temporal RoPE and
  reports artifacts from modifying it. This is a warning that our temporal
  actuator may not be usable; it is not evidence that a temporal-only variant
  is automatically novel. Its Fourier phase and action occurrence-time lag
  are different quantities. The prior audit did not certify every code path
  of that method as never affecting a temporal component.

The narrow candidate distinction is a low-dimensional physical-time rotation
confined to the output→reference-video subinteraction, with no gradient
optimization and at most a future calibrated signed-lag feedback rule. The
current oracle has no such feedback and does not establish superiority or
novelty. Restricting scope and conserving mass can be useful controlled
ablations, but cannot alone support an architectural innovation claim.

## Validation evidence and remaining limits

`tests/test_phase_rope.py` currently contains 11 passing CPU tests, including:
FP64 equality to explicit normalized probability redistribution; exact
non-reference contribution invariance; reference mass and total probability
normalization; positive/negative signs and physical-frame units; rotation
composition/inverse/norm; untouched spatial/unrotated dimensions; exact zero
fast paths; no Q/K/V/frequency mutation; high-reference-mass stability; BF16
rotation channel preservation; copied-layout equality and window mapping;
half-open interval checks, callback forwarding and failure audit behavior.

No GPU kernel correctness/performance test or real video result has been
obtained for this plugin. The frozen Flash helper was audited previously, but
that does not replace validating this newly composed numerical path. Root
must review before any real run.

The layout validator is byte-for-byte copied from frozen H3TemporalRouter;
Flash/LSE and bounded-stat functions are exact excerpts with their source SHA
recorded in `audited_flash.py`. There is no runtime import of a live extension,
no external dependency addition and no mutation of frozen sources.
