"""Four preregistered arms; only a complete all-UNKNOWN scan permits fallback."""
from .automatic_window_policy import Policy
from .dynamic_support import bins_for, bin_coverage
from .geometry import LEGACY

ARMS = ('native', 'visible_only', 'visible_fallback', 'weak_only')
FEATURES = ('arm_direction', 'left_arm_direction', 'right_arm_direction')
WEAK_INDICES = tuple(range(6, 15))
WEAK_ALPHA = 0.25


def observation_rows(index, measurement, geometry):
    if not isinstance(measurement, dict) or measurement.get('status') != 'complete':
        raise ValueError('observer execution failed or missing current measurement')
    if measurement.get('physical_index') != index:
        raise ValueError('current response physical index mismatch')
    observer = measurement['observer']
    if (observer.get('schema') != 'r27-whole-timeline-observation-v1'
            or observer.get('physical_index') != index):
        raise ValueError('observer schema/current physical index mismatch')
    if observer.get('status') not in ('measured', 'unknown_visibility'):
        raise ValueError('invalid scientific observer status')
    if observer.get('observation_domain') != geometry.domain_record:
        raise ValueError('observer valid-domain mismatch')
    expected = {(tuple(w), f) for w in geometry.windows() for f in FEATURES}
    rows = observer['windows']
    actual = [(tuple(row['window']), row['feature']) for row in rows]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError('complete window/descriptor enumeration required')
    proof = observer.get('complete_scan', {})
    if proof != {'descriptor_version': 'r56-arm-bone-unit-v1',
                 'expected_rows': len(expected), 'actual_rows': len(rows), 'complete': True}:
        raise ValueError('complete visible scan proof differs')
    allowed = ('unknown', 'aligned', 'delayed_candidate', 'advanced_candidate')
    for row in rows:
        bins_for([row['window']], geometry)
        if row['baseline'] not in allowed:
            raise ValueError('invalid baseline classification')
        if row['baseline'] in ('unknown', 'aligned'):
            if row.get('status') != 'baseline_' + row['baseline']:
                raise ValueError('baseline row status disagrees')
        elif row.get('status') not in ('measured', 'unknown'):
            raise ValueError('candidate comparison status invalid')
    all_unknown = bool(rows) and all(row['baseline'] == 'unknown' for row in rows)
    if observer['status'] == 'unknown_visibility' and not all_unknown:
        raise ValueError('unknown visibility contradicts reliable rows')
    return observer, rows, all_unknown


class Controller:
    def __init__(self, geometry=LEGACY, *, arm='visible_only'):
        if arm not in ARMS:
            raise ValueError('unknown preregistered arm')
        self.arm = arm
        self.geometry = geometry
        self.policy = Policy(.5)
        self.last_index = -1

    @property
    def needs_observation(self):
        return self.arm in ('visible_only', 'visible_fallback')

    def select(self, index, measurement=None):
        if type(index) is not int or index != self.last_index + 1 or not 0 <= index < 20:
            raise ValueError('decisions must cover consecutive physical indices0..19')
        all_unknown = False
        if self.needs_observation:
            observer, rows, all_unknown = observation_rows(index, measurement, self.geometry)
            decision = self.policy.update(index, rows)
            bins, mapping = bins_for(decision['physical_intervals'], self.geometry)
            decision.update(observation_complete=True, all_unknown=all_unknown,
                            reliable_rows=sum(r['baseline'] != 'unknown' for r in rows),
                            total_rows=len(rows), candidate_groups=len(decision['groups']),
                            measurement_status=observer['status'],
                            measurement_reasons=observer.get('reasons', []),
                            response_sha256=measurement.get('response_sha256'),
                            request_sha256=measurement.get('request_sha256'))
        else:
            if measurement is not None:
                raise ValueError('Native/Weak-only decisions do not consume an observer')
            bins, mapping = [], []
            decision = {'index': index, 'groups': [], 'selected': [],
                        'physical_intervals': [], 'active': False, 'reason': 'fixed_arm',
                        'observation_complete': False, 'all_unknown': None,
                        'reliable_rows': None, 'total_rows': None, 'candidate_groups': None,
                        'measurement_status': 'not_requested'}
        state, alpha = ('visible', 1.0) if bins else ('native', 0.0)
        if (not bins and index in WEAK_INDICES
                and (self.arm == 'weak_only' or (self.arm == 'visible_fallback' and all_unknown))):
            bins = list(range(self.geometry.latent_bins))
            state = 'weak_only' if self.arm == 'weak_only' else 'weak_fallback'
            alpha = WEAK_ALPHA
            decision['reason'] = state
        decision.update(arm=self.arm, chosen_full=bool(bins), latent_bins=bins, mapping=mapping,
                        bin_coverage=bin_coverage(bins, self.geometry),
                        control_state=state, route_alpha=alpha,
                        execution_support='all_canvas_bins' if state.startswith('weak') else 'selected_time_bins',
                        spatial_support='all_spatial_queries', blocks=list(range(50)))
        self.last_index = index
        return decision
