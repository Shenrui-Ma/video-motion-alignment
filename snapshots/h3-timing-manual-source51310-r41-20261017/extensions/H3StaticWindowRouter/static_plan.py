"""One immutable posthoc control. No observations are read or fabricated."""
class StaticPlan:
    def __init__(self):self.next_index=0
    def select(self,n):
        if type(n) is not int or n!=self.next_index or not 0<=n<20:raise ValueError('static plan decision order')
        self.next_index+=1;active=n in (6,7,8,9,10,11,12,13,14)
        return {'schema':'r41-static-plan-decision-v1','physical_index':n,'decision_source':'frozen_static_plan','chosen_full':active,'latent_bins':list(range(17,38)) if active else [],'nominal_extent_inclusive':[56,127] if active else None,'reason':'manual_physical_span_fixed_schedule' if active else 'predeclared_native','online_observation':False}
