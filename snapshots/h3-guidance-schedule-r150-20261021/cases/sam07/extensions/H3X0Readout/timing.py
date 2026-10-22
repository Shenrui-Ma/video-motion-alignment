"""Passive wall-clock wrapper; original recorder, callback arguments and result pass through."""
import time
from pathlib import Path
from .core import PassiveRecorder, atomic_write


class TimedRecorder(PassiveRecorder):
    def __call__(self, executor, model_wrap, sigmas, extra_args, callback, noise,
                 latent_image=None, denoise_mask=None, disable_pbar=False):
        start = previous = time.monotonic()
        records = []
        passed = False
        def timed_callback(step, x0, x, total_steps):
            nonlocal previous
            now = time.monotonic()
            records.append({"step_zero_based": step, "callback_interval_seconds": now-previous})
            previous = now
            if callback is not None:
                return callback(step, x0, x, total_steps)
        try:
            result = super().__call__(executor, model_wrap, sigmas, extra_args, timed_callback,
                                      noise, latent_image, denoise_mask, disable_pbar)
            passed = True
            return result
        finally:
            end = time.monotonic()
            directory = Path(self.config.output_dir) / self.config.run_id
            if directory.is_dir():
                atomic_write(directory / "timing.json", {
                    "schema": "r149-sampler-wall-v1", "run_id": self.config.run_id,
                    "passed": passed, "sampler_wall_seconds": end-start,
                    "callback_steps": records, "after_last_callback_seconds": end-previous,
                    "scope": "entire original PassiveRecorder/KSAMPLER call including audit I/O; callback endpoints occur after synchronized CPU x0 capture; first interval includes sampler setup; each later interval includes previous Euler update and current prediction/capture",
                    "no_extra_forward": True})
