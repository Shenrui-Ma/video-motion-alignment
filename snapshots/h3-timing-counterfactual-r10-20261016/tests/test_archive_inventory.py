"""Reject incomplete or misbound post-run archives before reporting success."""
import ast
import copy
from pathlib import Path
import unittest


source = Path(__file__).resolve().parents[1] / 'scripts/compare_parent.py'
tree = ast.parse(source.read_text())
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_inventory')
scope = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), scope)
validate = scope['validate_inventory']


def complete():
    branches, steps = [], []
    for n in range(20):
        rows = []
        for branch in (('native', 'full') if 6 <= n < 15 else ('native',)):
            row = dict(physical_index=n, branch=branch, nfe_index=len(branches),
                       file=f'{n}_{branch}.pt', raw_stream_signatures=[n, branch])
            branches.append(row)
            rows.append(row)
        last = rows[-1]
        steps.append(dict(physical_index=n, selected_branch=last['branch'], chosen_file=last['file'],
                          chosen_raw_stream_signatures=last['raw_stream_signatures'],
                          nfe_indices=[r['nfe_index'] for r in rows], callback_observed_once=True))
    return dict(branches=branches, steps=steps,
                inputs=[dict(physical_index=n, file=f'{n}_input.pt') for n in (6, 10, 14)])


class ArchiveInventoryTests(unittest.TestCase):
    def test_complete_inventory(self):
        validate(complete())

    def test_duplicate_replacing_unpaired_parent_step(self):
        c = complete()
        c['branches'][2] = copy.deepcopy(c['branches'][1])
        with self.assertRaises(AssertionError):
            validate(c)

    def test_missing_raw_inputs(self):
        c = complete()
        c['inputs'] = []
        with self.assertRaises(AssertionError):
            validate(c)

    def test_chosen_native_in_full_step(self):
        c = complete()
        c['steps'][6]['selected_branch'] = 'native'
        with self.assertRaises(AssertionError):
            validate(c)

    def test_wrong_step_binding(self):
        c = complete()
        c['steps'][6]['chosen_file'] = c['steps'][5]['chosen_file']
        with self.assertRaises(AssertionError):
            validate(c)

    def test_wrong_nfe_mapping(self):
        c = complete()
        c['branches'][-1]['nfe_index'] = 20
        with self.assertRaises(AssertionError):
            validate(c)

    def test_duplicate_raw_input_file(self):
        c = complete()
        c['inputs'][1]['file'] = c['inputs'][0]['file']
        with self.assertRaises(AssertionError):
            validate(c)


if __name__ == '__main__':
    unittest.main()
