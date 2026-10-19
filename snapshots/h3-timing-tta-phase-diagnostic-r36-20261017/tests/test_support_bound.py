import ast,copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import contract
from support_bound import identity_bound
from math_core import common_costs,all_windows


class SupportBoundTests(unittest.TestCase):
    def test_full_view_mask_is_subset_of_identity(self):
        rng=np.random.default_rng(3601)
        s=rng.normal(size=(3,141,4,2));t=rng.normal(size=s.shape)
        sc=np.ones(s.shape[:-1]);tc=np.ones_like(sc)
        # Sparse non-identity missingness preserves identity as an upper bound.
        sc[1,60,0]=0;tc[2,75,1]=0;t[1,90,2]=np.nan
        for threshold in (.3,.5):
            for window in [(50,65),(0,15),(99,111),(109,140)]:
                upper=identity_bound(s[0],t[0],sc[0],tc[0],window,threshold)
                full=common_costs(s,t,sc,tc,window,threshold)
                self.assertTrue((np.asarray(full['common_mask'])<=np.asarray(upper['mask'])).all())
                self.assertLessEqual(full['coverage'],upper['coverage_upper_bound'])
                self.assertLessEqual(full['valid_frames'],upper['positive_weight_frames_upper_bound'])
    def test_identical_views_equal_support(self):
        s=np.ones((3,141,4,2));sc=np.ones(s.shape[:-1]);sc[:,63,2]=.4
        for threshold in (.3,.5):
            a=identity_bound(s[0],s[0],sc[0],sc[0],(50,65),threshold)
            b=common_costs(s,s,sc,sc,(50,65),threshold)
            self.assertEqual(a['mask'],b['common_mask']);self.assertEqual(a['coverage_upper_bound'],b['coverage'])
    def test_bound_independent_of_coordinate_values(self):
        s=np.ones((141,4,2));sc=np.ones((141,4))
        a=identity_bound(s,s,sc,sc,(50,65),.3)
        b=identity_bound(s*12345,s*-32,sc,sc,(50,65),.3)
        self.assertEqual(a,b);self.assertNotIn('lag',a);self.assertNotIn('costs',a)
    def test_bound_edges_not_clamped(self):
        s=np.ones((141,4,2));sc=np.ones((141,4))
        a=identity_bound(s,s,sc,sc,(0,15),.3)
        self.assertEqual(a['coverage_upper_bound'],0);self.assertFalse(a['possibly_eligible'])
    def test_one_identity_hole_can_remove_all_lag_stencils(self):
        s=np.ones((141,4,2));sc=np.ones((141,4));tc=sc.copy();tc[55]=0
        a=identity_bound(s,s,sc,tc,(50,65),.3)
        self.assertFalse(a['possibly_eligible']);self.assertEqual(a['valid_vectors_upper_bound'],0)
    def test_support_only_module_has_no_scoring_calls(self):
        text=(ROOT/'scripts/support_bound.py').read_text()
        for name in ('argmin','linalg','common_costs','decisions','pairwise_gain'):
            self.assertNotIn(name,text.replace('or argmin',''))
    def test_pruning_all_negative_blocks_pose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'results/identity_support_upper_bound';dest.mkdir(parents=True)
            for name in ('FREEZE.json','PROTOCOL.json','INPUTS.json'):(root/name).write_text('{}')
            summary={'freeze_sha256':contract.sha(root/'FREEZE.json'),'protocol_sha256':contract.sha(root/'PROTOCOL.json'),'inputs_sha256':contract.sha(root/'INPUTS.json'),'rows':792,'any_potentially_eligible':False}
            rows=[{'dual_possibly_eligible':False} for _ in range(792)]
            def write_files():
                (dest/'SUMMARY.json').write_text(json.dumps(summary));(dest/'RESULTS.json').write_text(json.dumps({'summary':summary,'rows':rows}))
                (dest/'COMPLETE.json').write_text(json.dumps({'status':'complete','freeze_sha256':contract.sha(root/'FREEZE.json'),'files':{n:contract.sha(dest/n) for n in ('RESULTS.json','SUMMARY.json')}}))
            write_files()
            with patch.object(contract,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'No potentially eligible'):contract.require_pruning_allows_pose()
                summary['any_potentially_eligible']=True;rows[0]['dual_possibly_eligible']=True;write_files()
                contract.require_pruning_allows_pose()
                (dest/'SUMMARY.json').write_text('{}')
                with self.assertRaisesRegex(ValueError,'changed'):contract.require_pruning_allows_pose()


if __name__=='__main__':unittest.main()
