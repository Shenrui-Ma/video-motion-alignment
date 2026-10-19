"""Frozen policy adapter. Technical failure aborts; reliable absence remains visible."""
from .automatic_window_policy import Policy
from .dynamic_support import bins_for

class Controller:
    def __init__(self):self.policy=Policy(.5)
    def select(self,index,measurement):
        if not isinstance(measurement,dict) or measurement.get('status')!='complete':
            raise ValueError('observer execution failed or missing current measurement')
        observer=measurement['observer']
        if observer.get('schema')!='r27-whole-timeline-observation-v1' or observer.get('physical_index')!=index:
            raise ValueError('observer schema/current physical index mismatch')
        if observer.get('status') not in ('measured','unknown_visibility'):
            raise ValueError('invalid scientific observer status')
        rows=observer['windows']
        if observer['status']=='unknown_visibility' and rows:
            raise ValueError('unknown visibility cannot contain measured proposals')
        decision=self.policy.update(index,rows)
        bins,mapping=bins_for(decision['physical_intervals'])
        decision.update(chosen_full=bool(bins),latent_bins=bins,mapping=mapping,
                        measurement_status=observer['status'],measurement_reasons=observer.get('reasons',[]),
                        response_sha256=measurement.get('response_sha256'),request_sha256=measurement.get('request_sha256'))
        if observer['status']=='unknown_visibility':decision['reason']='unknown_visibility'
        return decision
