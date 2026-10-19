import copy
import importlib.util
from pathlib import Path
import unittest

from counterfactual_support import observation
from H3NativeObserverRouter.core import Config, selection_decision
from test_counterfactual import LAGS, EXPECTED

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r12_compare', ROOT/'scripts/compare_parent.py')
module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
validate = module.validate_inventory


def complete(policy='native_observer', fixed=''):
    config = Config('case','/tmp/r12',policy=policy,fixed_indices=fixed)
    branches, steps, previous, active = [], [], False, []
    for n in range(20):
        obs = observation(LAGS[n-5]) if n >= 5 else None
        decision = selection_decision(config,n,obs,previous)
        decision['native_nfe_index'] = len(branches)
        rows = []
        for branch in (('native','full') if decision['chosen_full'] else ('native',)):
            row = dict(physical_index=n,branch=branch,nfe_index=len(branches),
                       file=f'{n}_{branch}.pt',raw_stream_signatures=[f'{n}{branch}'],
                       same_input={'sha256':str(n)},observation=obs if branch=='native' else observation(-24))
            rows.append(row);branches.append(row)
        if decision['chosen_full']:active.append(n)
        last = rows[-1]
        steps.append(dict(physical_index=n,selected_branch=last['branch'],chosen_file=last['file'],
                          chosen_raw_stream_signatures=last['raw_stream_signatures'],decision=decision,
                          nfe_indices=[r['nfe_index'] for r in rows],callback_observed_once=True))
        if n>=6:previous=decision['chosen_full']
    return dict(policy=policy,fixed_indices=list(config.indices),branches=branches,steps=steps,
                full_physical_indices=active,actual_full_count=len(active),actual_model_nfe=len(branches),
                actual_euler_updates=20,inputs=[dict(physical_index=n,file=f'{n}_input.pt') for n in (6,10,14)])


class ArchiveInventoryTests(unittest.TestCase):
    def test_complete_variable_inventory_not_fixed29(self):
        c=complete();self.assertEqual(validate(c),EXPECTED);self.assertEqual(c['actual_model_nfe'],27)
        self.assertEqual(validate(complete('off')),[])
        self.assertEqual(validate(complete('fixed','6,19')),[6,19])
        self.assertEqual(validate(complete('fixed',','.join(map(str,range(6,20))))),list(range(6,20)))

    def test_all_full_observations_are_passive(self):
        c=complete()
        for row in c['branches']:
            if row['branch']=='full':row['observation']=observation(24)
        self.assertEqual(validate(c),EXPECTED)

    def test_corruption_rejected(self):
        for kind in ('duplicate','missing_input','wrong_chosen','wrong_binding','wrong_nfe','same_input',
                     'extra_branch','wrong_k','index5_pending','wrong_native_gate','wrong_active'):
            with self.subTest(kind=kind):
                c=complete()
                if kind=='duplicate':c['branches'][2]=copy.deepcopy(c['branches'][1])
                elif kind=='missing_input':c['inputs']=[]
                elif kind=='wrong_chosen':c['steps'][7]['selected_branch']='native'
                elif kind=='wrong_binding':c['steps'][7]['chosen_file']=c['steps'][6]['chosen_file']
                elif kind=='wrong_nfe':c['branches'][-1]['nfe_index']=20
                elif kind=='same_input':next(r for r in c['branches'] if r['branch']=='full')['same_input']={'sha256':'wrong'}
                elif kind=='extra_branch':c['branches'].append(copy.deepcopy(c['branches'][-1]))
                elif kind=='wrong_k':c['actual_full_count']=9
                elif kind=='index5_pending':c['steps'][6]['decision']['previous_actual_full']=True
                elif kind=='wrong_native_gate':next(r for r in c['branches'] if r['physical_index']==7 and r['branch']=='native')['observation']=observation(0)
                else:c['full_physical_indices']=[6,19]
                with self.assertRaises(AssertionError):validate(c)

if __name__=='__main__':unittest.main()
