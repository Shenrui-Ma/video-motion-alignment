# MiniMax-H3 ref2va: aligned video guides (IC-LoRA style v2v)

Adds two flags to ai-toolkit's `minimax_h3_ref2va` architecture:

- **`align_video_refs`** — a control video becomes a true v2v guide instead of a loose
  reference: the arrangement that makes LTX-style IC-LoRA training work, applied to H3.
- **`control_latent_only`** — the control media reaches the DiT as latents only and is never
  shown to the VLM. Faster to train, much smaller embed cache, and it closes a train/inference
  gap that exists in ComfyUI today.

Verified on a **fresh clone** of ostris/ai-toolkit at `be99518` (2026-08-30): applies cleanly,
10/10 tests pass, and the flag reaches the behaviour (`_aligned_ref_flags` returns
`(False, True)` for an identity image + a guide video, `()` when the flag is off).

## What problem this solves

H3 packs references *beside* the target: `build_packed_sequence` gives every reference block
its own stretch of the shared media clock and its own aspect-normalised spatial grid, and the
target's streams start after the cumulative advance. That is right for an identity reference —
a face photo has no spatial correspondence with the output — but wrong for a driving video,
where frame `i` of the guide is meant to drive frame `i` of the output. Unaligned, the model
has to *learn* that correspondence across a positional offset instead of being handed it.

With `align_video_refs: true`, a **video** reference reuses the target's rotary clock and the
target's spatial grid, so guide row `(i, h, w)` lands on exactly the target's `(i, h, w)` and
attention between them costs nothing positionally. Aligned blocks also do not advance the media
clock. **Image** references are never aligned.

A head-swap pack is then the natural pair: aligned driving video + unaligned identity image.

## Usage

```yaml
model:
  arch: "minimax_h3_ref2va"
  model_kwargs:
    align_video_refs: true
    control_latent_only: true   # optional; guide as latents only, not through the VLM

datasets:
  - folder_path: "/path/to/target"     # the edited videos
    control_path_1: "/path/to/guide"   # the source videos -> ALIGNED v2v guide
    control_path_2: "/path/to/face"    # identity images   -> unaligned reference
    resolution: [384]
    num_frames: 73                     # must be 17n+5
    auto_frame_count: false
```

Guide and target must share a latent resolution; the patch resizes aligned guides to the
target's exact grid to guarantee it (see below).

## `control_latent_only`: the guide as latents, not as a reference

By default the control media goes in twice: as latent rows in the DiT **and** through the VLM,
which watches a control video at 2 fps and turns it into vision tokens in the text embeds. On a
73-frame 512x288 clip that is **8.2k vision tokens against 6.3k video rows** — the text stream
is bigger than the video it describes, and it is the same guide either way.

With `control_latent_only: true` the text embeds are caption-only. The guide still reaches the
model, aligned on the target's grid, where its frame-to-frame correspondence actually lives.

Measured on 300 CoinVE instruction-edit pairs (73 frames, 512x288, ref2va pruned int8), across
two runs whose configs differ by this flag and nothing else:

| | default | `control_latent_only` |
|---|---|---|
| text embeds per sample | 84 MB | **~0.9 MB** |
| sequence length | ~14.6k tokens | **~6.4k tokens** |
| training step | 53.1 s/it | **45.3 s/it** |

The embed figure counts two cache files per sample — the caption and its dropout — at 0.26-0.91
MB each. The step time is the run average on one GPU, rank-128 LoRA, batch 1, gradient
checkpointing.

The disk number is the one that bites: 84 MB per sample means a 1250-pair set needs ~105 GB of
embed cache before a single training step runs. At ~0.9 MB the same set costs ~1 GB. That is the
difference between a dataset capped by disk and one capped by what you actually have — the run
this was measured on had to be cut to 300 pairs under the default presentation, and moved to
1000 under the flag without touching anything else.

**The loss will not show you any of this.** Over identical 250-step windows the two runs sit on
top of each other — mean loss 2.28 / 2.45, 1.93 / 1.95, 1.86 / 1.91, 1.73 / 1.67 (default /
`control_latent_only`) for steps 1-250 through 750-1000. That is expected: the flag changes what
the model is *given*, not what it is scored against, and the target is identical either way.
Judge it on samples and on the table above, not on the curve.

**It also closes a train/inference gap.** In ComfyUI, `MiniMaxH3AddGuide` only appends
`minimax_keyframes` to the conditioning — it never re-tokenises the prompt, so the guide never
reaches the VLM. Only `MiniMaxH3ReferenceToVideo`'s `ref_video` input does that, and going that
route costs you the alignment (an ordinary reference sits beside the target on the media clock).
So a model trained with the default presentation is asked at inference for something it was
never given: it learned to lean on a semantic reading of the guide that `AddGuide` does not
supply. `control_latent_only` trains the way `AddGuide` infers.

Changing the flag changes the embedding space, so the patch bumps
`text_embedding_space_version` — existing text-embed caches are invalidated on purpose rather
than silently reused.

## What each conditioning actually buys, measured

Two LoRAs on the same 1000 CoinVE instruction-edit pairs (rank 128, 73 frames, area 384),
differing in how the guide reached the model during training:

- **guide-latents LoRA** — `control_latent_only: true`, the arrangement this patch adds
- **VLM-presented LoRA** — the same guide, also presented to the VLM as vision tokens

Each was then sampled two ways: with the guide as latents only (ComfyUI's Add Guide), and with
the source **also** passed as a ref2va reference. The base model with that reference and no LoRA
is the third row.

### Synchrony is what the LoRA buys, and only the guide-latents one has it

The stage light turns blue midway through this clip. The guide-latents LoRA follows it. The
VLM-presented one keeps rendering the suit red — it is painting from what it knows rather than
tracking the guide frame by frame.

![stage light](https://gist.githubusercontent.com/alisson-anjos/b300f2b90e65cf85846519d78b660cd3/raw/fig_sync_lighting.jpg)

Same clip, earlier frame. Nothing in the instruction mentions the wardrobe, so the question is
what survives untouched: shorts and knee socks in the source, kept by one, replaced with long
trousers by the other.

![wardrobe](https://gist.githubusercontent.com/alisson-anjos/b300f2b90e65cf85846519d78b660cd3/raw/fig_sync_wardrobe.jpg)

Burned-in captions are the strictest version of the same test — a few pixels wrong and the text
stops being text. All three perform the edit here; only the guide-latents LoRA leaves the
caption alone. With no LoRA at all it turns to garbage.

![burned-in text](https://gist.githubusercontent.com/alisson-anjos/b300f2b90e65cf85846519d78b660cd3/raw/fig_preservation_text.jpg)

### The reference input is what carries the edit where the guide dominates

The other half of the picture. When the thing to change **is** the most salient thing in the
guide, the latent path copies the guide instead of editing it — overlay graphics and all.
Passing the source as a reference as well rescues the edit, and costs nothing in synchrony: the
composition, the hands and the timing are the same in both columns.

![reference rescue](https://gist.githubusercontent.com/alisson-anjos/b300f2b90e65cf85846519d78b660cd3/raw/fig_guide_copy_rescue.jpg)

That failure is not universal. In a second clip a comparably dominant subject — an electric
guitar held in frame center, asked to become a wooden one — is replaced correctly with the
latent path alone. What the two failing cases share is a source with heavy burned-in graphics,
not a category of instruction.

### The recipe this leads to

Train with `control_latent_only`. At inference, add the source as a reference when the edit
targets whatever dominates the guide. The two conditionings are complementary, not alternatives:
the aligned latents carry the frame-to-frame correspondence, the presented reference carries the
semantics of what to change.

Practically this also means the 84 MB/sample embed cache the presentation costs buys nothing
here — it measurably hurts the axis that matters.

**Caveats.** Four clips, one instruction each. The two checkpoints are not step-matched (2750 vs
2000), and the later one also runs a sigma-decayed guidance-loss target and a newer upstream
tree, so this is a direction, not a controlled ablation of the flag alone.

## What is in the patch

**`src/packing.py`** — `build_packed_sequence` takes `aligned_refs`, a per-block flag. An
aligned block is placed on the target's clock and grid, is excluded from `media_advance`, and
is validated against the target's latent resolution.

**`minimax_h3.py`** — `_aligned_ref_flags` derives the flags from `model_kwargs`, marking blocks
with `t_lat > 1` (videos). Training and sampling call the *same* helper, because a layout that
differs between them fails silently. Aligned guides are sized to the target's exact height and
width in both paths, instead of area-matched to the guide's own aspect: on a real head-swap set
25% of guides sat a few percent off the target's aspect, which the pack rejects.

**`src/ref_video_cache.py`** — `load_ref_video_latent` takes `align`, and its disk cache key
gains `ref_sizing` plus the target dimensions.

Also fixes a **pre-existing bug** worth having on its own: the in-memory reference cache was
keyed by file path alone, so with multi-resolution buckets the same guide was reused at whatever
size happened to be encoded first. Unaligned that is silent — the guide simply rides on a grid
that is not the target's, at whatever its own resolution costs. Aligned it raises. The key is
now `(path, target_h, target_w, align)`.

**`src/pipeline.py`** — sampling derives `aligned_refs` from the same helper.

**`toolkit/dataloader_mixins.py`, `toolkit/data_loader.py`,
`toolkit/data_transfer_object/data_loader.py`** — `control_latent_only` reaches the caching path,
where the item's embeds are then encoded from the caption alone.

**`tests/test_minimax_h3_aligned_refs.py`** — 10 tests; the decisive one asserts the guide's and
the target's `position_ids` are literally equal.

## Inference in ComfyUI — no custom node needed

ComfyUI has no notion of an aligned reference, but the geometry is already expressible, because
a **keyframe** is packed on the target's spatial grid at `cursor + FRAME_RESCALE * frame_idx`
and keyframes do not advance the media clock:

```
MiniMaxH3ReferenceToVideo    prompt + ref_image_1 = the identity image
MiniMaxH3AddGuide            image = the whole guide clip, frame_idx = 0, vae = video VAE
   -> sampler
```

Verified against `comfy.ldm.minimax.model.PackedLayout`: as an ordinary reference the guide sits
at T 201..301 while the target is at 307..407; as a keyframe at `frame_idx=0` both are 201..301,
equal on all three axes. Sequence order differs from the trainer, but RoPE attention is
permutation-equivariant, so only the positions matter.

Two things to get right at inference:

- **Resample the guide to 24 fps.** Training paces references in real time
  (`frame i <- source frame round(i * src_fps / 24)`). ComfyUI's H3 node assumes its input is
  already 24 fps, so feeding raw frames from a 30 or 60 fps clip plays the motion at 80% or 50%
  speed — off-distribution in exactly the signal a guide carries.
  ostris' [ComfyUI-AIToolkit-MiniMaxH3](https://github.com/ostris/ComfyUI-AIToolkit-MiniMaxH3)
  node does this (plus the 17n+5 snap, the audio trim and the /32 sizing) and is the easy path.
- **Generate at the area you trained at.** That node defaults to 0.258 MP (res-512); a run
  trained at 384 wants ~0.147 MP.

## Applying

```bash
cd /path/to/ai-toolkit

curl -L -o aligned_video_refs.patch \
  https://gist.githubusercontent.com/alisson-anjos/b300f2b90e65cf85846519d78b660cd3/raw/aligned_video_refs.patch

git apply --check aligned_video_refs.patch   # dry run, changes nothing
git apply aligned_video_refs.patch
```

Then check it took:

```bash
python -m pytest tests/test_minimax_h3_aligned_refs.py -q     # 10 passed
```

The patch touches four files and adds one test file:

```
extensions_built_in/diffusion_models/minimax_h3/minimax_h3.py
extensions_built_in/diffusion_models/minimax_h3/src/packing.py
extensions_built_in/diffusion_models/minimax_h3/src/pipeline.py
extensions_built_in/diffusion_models/minimax_h3/src/ref_video_cache.py
extensions_built_in/diffusion_models/minimax_h3/src/text_encoder.py
toolkit/dataloader_mixins.py
toolkit/data_loader.py
toolkit/data_transfer_object/data_loader.py
tests/test_minimax_h3_aligned_refs.py                          (new)
```

### If `--check` complains

- **Not inside a git repo** (downloaded zip, vendored copy): use `patch -p1 < aligned_video_refs.patch`.
- **A fork that has drifted from ostris/main**: `git apply -3 aligned_video_refs.patch` does a
  three-way merge and resolves most of it on its own.

To undo: `git apply -R aligned_video_refs.patch`.

### Quick sanity check without running a training

```python
from extensions_built_in.diffusion_models.minimax_h3.minimax_h3 import MinimaxH3Ref2VAModel as M

class Cfg:
    def __init__(self, kw): self.model_kwargs = kw

obj = M.__new__(M)
face, guide = (1, 24, 24, 0), (19, 24, 24, 0)   # image ref, video guide

obj.model_config = Cfg({})
print(obj._aligned_ref_flags((face, guide)))    # ()  -> nothing aligned

obj.model_config = Cfg({"align_video_refs": True})
print(obj._aligned_ref_flags((face, guide)))    # (False, True)  -> only the video
```

## Credits

The ComfyUI inference notes lean on ostris'
[ComfyUI-AIToolkit-MiniMaxH3](https://github.com/ostris/ComfyUI-AIToolkit-MiniMaxH3) node, which
mirrors ai-toolkit's reference treatment (24 fps real-time pacing, 17n+5 snap, audio trim, /32
sizing) and is what makes a guide clip arrive at inference the way training saw it.
