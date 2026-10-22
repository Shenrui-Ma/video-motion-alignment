import unittest
from metric_worker import applicability
from aggregate import aggregate
class Tests(unittest.TestCase):
 def test_applicability(self):
  self.assertIsNotNone(applicability('quantity_accuracy',{'category':'subject_editing'}))
  self.assertIsNone(applicability('quantity_accuracy',{'category':'quantity_modification'}))
  self.assertIsNotNone(applicability('motion_fidelity',{'category':'subject_motion_editing'}))
 def test_paired_mf(self):
  rows=[dict(task_id='a',dataset='IVEBench',method='source',metric='motion_fidelity',status='done',score=.98),dict(task_id='a',dataset='IVEBench',method='native',metric='motion_fidelity',status='done',score=.75),dict(task_id='b',dataset='FlexiAct',method='native',metric='motion_fidelity',status='failed',score=None)]
  d=aggregate(rows);self.assertAlmostEqual(d['main_IVEBench']['methods']['native']['motion_fidelity_delta_from_reference']['mean'],-.23);self.assertEqual(d['main_all']['methods']['native']['motion_fidelity']['n_failed'],1)
 def test_cohort_and_complete_pairs(self):
  methods=['native','early','fixed','late','split','global_weak'];rows=[];expected=[]
  for case in ['a','b']:
   for i,m in enumerate(methods):
    j=dict(id=case+'_'+m,task_id=case,dataset='IVEBench',method=m,cohort='main');expected.append(j)
    if case=='b' and m=='split':continue
    rows.append(dict(j,job_id=j['id'],metric='motion_fidelity',status='done',score=.5+i*.01))
  j=dict(id='exp_native',task_id='x',dataset='IVEBench',method='native',cohort='expansion');expected.append(j);rows.append(dict(j,job_id=j['id'],metric='motion_fidelity',status='done',score=.99))
  d=aggregate(rows,expected)
  self.assertEqual(d['main_IVEBench']['complete_paired_subset']['motion_fidelity']['n_complete_cases'],1)
  self.assertEqual(d['main_IVEBench']['methods']['split']['motion_fidelity']['n_pending'],1)
  self.assertEqual(d['main_IVEBench']['methods']['native']['motion_fidelity']['mean'],.5)
  self.assertEqual(d['expansion_IVEBench']['methods']['native']['motion_fidelity']['mean'],.99)
if __name__=='__main__':unittest.main()
