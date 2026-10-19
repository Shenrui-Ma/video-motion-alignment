"""CPU toy harness; existing attention and block patch code execute unchanged."""
import contextlib
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extensions"))
from H3CoarsePoseObserverRouter.core import Config, State, BlockPatch, SamplerAudit, PredictionProbe
from H3CoarsePoseObserverRouter.dependencies import router


class Nested:
    is_nested = True
    def __init__(self, values):
        self.values = values
    def unbind(self):
        return self.values


def unpack(value, shapes):
    cursor, leaves = 0, []
    for shape in shapes:
        count = math.prod(shape)
        leaves.append(value.reshape(-1)[cursor:cursor + count].reshape(shape))
        cursor += count
    return leaves


class FakeModel:
    def __init__(self, shapes):
        self.latent_shapes = list(shapes)
        self.latent_format = SimpleNamespace(scale_factor=1.0)
    def audio_scale(self):
        return 4.0
    def process_latent_out(self, value):
        video, audio = value.unbind()
        return Nested([video, audio * 0.25])


class FakeGuider:
    cfg = 1.0


def config(root, run_id="case", policy="native_observer", fixed=""):
    return Config(run_id, str(root), policy=policy, fixed_indices=fixed)


def observation(lag):
    return {"accepted": lag is not None, "best": None if lag is None else {"lag_frames": lag},
            "rejection_reasons": [] if lag is not None else ["ambiguous_separated_lag"],
            "curve": [{"lag_frames": i, "signed_cosine_error": None} for i in range(-24, 25)]}


class Observations:
    def __init__(self, lags):
        self.lags = list(lags)
        self.count = 0
    def __call__(self, video):
        value = self.lags[min(self.count, len(self.lags) - 1)]
        self.count += 1
        return observation(value)


class PhysicalObservations:
    """Native observations indexed by physical time, immune to extra Full calls."""
    def __init__(self, state, lags, full_lag=-20):
        self.state, self.lags, self.full_lag = state, list(lags), full_lag
    def __call__(self, video):
        phase = self.state.phase
        if phase['branch'] == 'full':
            return observation(self.full_lag)
        index = max(0, self.state.callback_count - 5)
        return observation(self.lags[min(index, len(self.lags)-1)])


def make_state(root, lags=(0,), policy="native_observer", fixed="", run_id="case"):
    c = config(root, run_id, policy, fixed)
    reference = torch.zeros(c.shapes[0], dtype=torch.float32)
    state = State({"refs": []}, reference, c, observer=Observations(lags))
    plan = {"seq_len": 84, "frame_rows": 1, "latent_interval_half_open": [14, 20],
            "query_interval_half_open": [56, 62], "reference_video_segment": [0, 42]}
    state.plan_for = lambda _: plan  # Only packed geometry is toy; block/counter/kernel code is real.
    state.observer = PhysicalObservations(state, lags)
    return state


def dense_attention(q, k, v):
    logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


@contextlib.contextmanager
def cpu_attention():
    original = router.route_attention
    def route(*args, **kwargs):
        return original(*args, **kwargs, attention=dense_attention)
    with patch.object(router, "route_attention", route):
        yield


ZERO_VALUES = False

def run_blocks(state, patches, *, sigmas=None):
    q = torch.arange(168, dtype=torch.float32).reshape(1, 1, 84, 2) / 100
    k = q.flip(-2).contiguous()
    v = torch.zeros_like(q) if ZERO_VALUES else torch.sin(q * 3)
    layout = object()
    value = None
    def attention_pytorch(*args, **kwargs):
        raise AssertionError("the override must intercept native dispatch")
    def original(args):
        nonlocal value
        override = args["transformer_options"]["optimized_attention_override"]
        value = override(attention_pytorch, q, k, v, 1, skip_reshape=True)
        return {"img": value}
    for i in range(50):
        options = {"block_index": i, "minimax_h3_layout": layout}
        if sigmas is not None:
            options["sample_sigmas"] = sigmas
        patches[("double_block", i)]({"layout": layout, "transformer_options": options},
                                      {"original_block": original})
    return value



def make_guider(state):
    guider = FakeGuider()
    guider.inner_model = FakeModel(state.config.shapes)
    guider.original_conds = {'positive': [{'minimax_refs': [{'kind': 'video', 'latent': state.reference.clone()}]}]}
    guider.conds = {}
    prediction = PredictionProbe(state)
    guider.model_options = {'transformer_options': {'patches_replace': {'dit': {
        ('double_block', i): BlockPatch(state, i) for i in range(50)}},
        'wrappers': {'predict_noise': {'counterfactual': [prediction]}}}}
    return guider, prediction


def execute(state, *, fail=None, callback=None, nested_callback=False):
    guider, prediction = make_guider(state)
    shapes = state.config.shapes
    count = sum(math.prod(s) for s in shapes)
    noise = torch.arange(count, dtype=torch.float32).reshape(1, 1, -1) / count
    sigmas = torch.linspace(1, 0, 21)
    guider.model_options['transformer_options']['sample_sigmas'] = sigmas
    patches = guider.model_options['transformer_options']['patches_replace']['dit']
    received, selected = [], []
    class PredictionExecutor:
        class_obj = guider
        def __call__(self, x, sigma, options, seed):
            received.append((state.callback_count, state.phase['branch'], x.clone(), sigma.clone(), seed))
            value = run_blocks(state, patches, sigmas=sigmas)
            if fail == 'double_forward':
                run_blocks(state, patches, sigmas=sigmas)
            if fail == 'rng':
                torch.rand(1)
            if fail == 'timestep_mutation':
                sigma.add_(0.01)
            if fail == 'grid_mutation':
                options['transformer_options']['sample_sigmas'][-2].add_(0.001)
            if fail == 'input_mutation':
                x.add_(1)
            if fail == 'condition_mutation':
                guider.original_conds['positive'][0]['minimax_refs'][0]['latent'].add_(1)
            return x * 0.25 + value.mean() * 0.001
    class SamplerExecutor:
        class_obj = SimpleNamespace(sampler_function=SimpleNamespace(__name__='sample_euler'), extra_options={}, inpaint_options={})
        def __call__(self, model_wrap, grid, extra_args, cb, noise, latent_image, mask, disable):
            x = noise.clone()
            for i in range(20):
                sigma = grid[i:i+1]
                if fail == 'wrong_sigma':
                    sigma = sigma + 0.01
                x0 = prediction(PredictionExecutor(), x, sigma, extra_args['model_options'], extra_args['seed'])
                if fail == 'duplicate_prediction':
                    prediction(PredictionExecutor(), x, sigma, extra_args['model_options'], extra_args['seed'])
                selected.append(x0.clone())
                d = (x - x0) / grid[i]
                xx, yy = (Nested(unpack(x, shapes)), Nested(unpack(x0, shapes))) if nested_callback else (x, x0)
                cb(i, yy, xx, 20)
                if fail == 'duplicate_callback':
                    cb(i, yy, xx, 20)
                x = x + d * (grid[i+1] - grid[i])
            return x
    audit = SamplerAudit(state, unpack=unpack, nested=Nested, guider_class=FakeGuider)
    with cpu_attention():
        result = audit(SamplerExecutor(), guider, sigmas, {'seed': 123, 'model_options': guider.model_options},
                       callback, noise, torch.zeros_like(noise), None, True)
    return result, received, selected
