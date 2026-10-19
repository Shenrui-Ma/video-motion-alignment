"""One immutable posthoc control. No observations are read or fabricated."""
class StaticPlan:
    def __init__(self):self.next_index=0
    def select(self,n):
        if type(n) is not int or n!=self.next_index or not 0<=n<20:raise ValueError('static plan decision order')
        self.next_index+=1;active=n==4
        return {'schema':'r34-static-plan-decision-v1','physical_index':n,'decision_source':'frozen_static_plan','chosen_full':active,'latent_bins':list(range(42)) if active else [],'nominal_extent_inclusive':[0,140] if active else None,'reason':'predeclared_global_pulse' if active else 'predeclared_native','online_observation':False}
