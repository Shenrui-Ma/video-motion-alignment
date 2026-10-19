"""Administrative R40 online-priority supplement; no metric changes."""
from pathlib import Path

R40 = Path('/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017')

def extra_pending(root=R40):
    for d in (Path(root) / 'audit/observations').glob('step*'):
        if ((d/'request.json').exists() and (d/'native.json').exists()
                and not (d/'pose_complete.json').exists()
                and not (d/'response.json').exists()):
            return True
    return False

def install(module, extra=extra_pending):
    previous = module.online_pending
    def combined():
        return previous() or extra()
    module.online_pending = combined
    return combined
