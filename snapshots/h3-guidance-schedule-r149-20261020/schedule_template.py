"""Only the denoising-step membership differs from the original fixed router."""
import time
from .core import RouterState, EventBlockPatch

SCHEDULES = {"early": tuple(range(9)), "late": tuple(range(11, 20)),
             "split": (*range(4), *range(15, 20)), "global_weak": tuple(range(20))}


class ScheduleState(RouterState):
    def __init__(self, *args, schedule, **kwargs):
        if schedule not in SCHEDULES:
            raise ValueError("unregistered schedule")
        self.active_steps = SCHEDULES[schedule]
        self.step_start_time = None
        super().__init__(*args, **kwargs)
        self.audit["step_interval_half_open"] = None
        self.audit["step_set_zero_based"] = list(self.active_steps)
        self.audit["schedule"] = schedule
        self.audit["phase_displacement"] = 0
        self.audit["routing_implementation"] = "unchanged core.route_attention mass_preserve"
        self.audit["fresh_patch_state"] = True
        self.audit["forward_wall_seconds"] = []
        self.write()

    def selected(self, block):
        return self.block_start <= block < self.block_end and self.forward_index in self.active_steps

    def finish_forward(self):
        self.audit["forward_wall_seconds"].append(time.monotonic() - self.step_start_time)
        super().finish_forward()


class ScheduleBlockPatch(EventBlockPatch):
    """Use the original attention override; time one physical Euler forward."""
    def __call__(self, args, extra_args):
        if self.block_index == 0:
            self.state.step_start_time = time.monotonic()
        return super().__call__(args, extra_args)
