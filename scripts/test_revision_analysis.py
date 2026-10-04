"""Small hand-computed checks for the new statistical and replay boundaries."""
import unittest
import numpy as np
from revision_analysis import extraction,replay,holm,Inference,metric,paired_language,unique
from revision_panel_audit import kappa,panel,FIXED


class Checks(unittest.TestCase):
    def test_quotation_carries_previous_program(self):
        ts=[{'turn':1,'code_extracted':True,'block_tests_pass':True,'requote_of_presented':None},
            {'turn':2,'code_extracted':True,'block_tests_pass':False,'requote_of_presented':True}]
        self.assertEqual(replay(ts,False,'historical',{2:'firm'}),[True,True])
        self.assertEqual(replay(ts,False,'historical',{2:'hedged'}),[True,False])
        self.assertEqual(replay(ts,False,'cap_only',{2:'hedged'}),[True,True])
        self.assertEqual(replay(ts,False,'all_extracted',{}),[True,False])

    def test_missing_text_preserves_failing_presented_code(self):
        ts=[{'turn':1,'code_extracted':False,'block_tests_pass':None,'requote_of_presented':None}]
        self.assertEqual(replay(ts,False,'historical',{}),[False])
        self.assertEqual(extraction(None,'f')[3],'no_content')

    def test_unknown_new_code_is_not_a_failure(self):
        t={'turn':1,'code_extracted':True,'block_tests_pass':True,'requote_of_presented':None}
        self.assertEqual(replay([t],False,'first_entrypoint',{},[(None,'def f(): pass',None)],{},'p'),[None])

    def test_extractors_separate_example_from_entrypoint(self):
        x=extraction('```python\ndef f(): return 1\n```\n```python\nprint(f())\n```','f')
        self.assertEqual(x[0],'def f(): return 1');self.assertEqual(x[2],'print(f())')

    def test_duplicate_ids_fail(self):
        with self.assertRaises(ValueError):unique([{'id':1},{'id':1}],lambda r:r['id'])

    def test_holm(self):
        self.assertEqual(holm([.01,.04,.03]),[.03,.06,.06])

    def test_pairs_require_both_languages(self):
        rr=[{'problem':'p','bug':'b','scenario':'s','language':'en','flip':0},
            {'problem':'p','bug':'b','scenario':'s','language':'es','flip':1},
            {'problem':'q','bug':'c','scenario':'s','language':'en','flip':1}]
        pp=paired_language(rr);self.assertEqual(len(pp),1);self.assertEqual(pp[0]['diff'],1)

    def test_cluster_keeps_related_observations_together(self):
        inf=Inference(['a','b','c','d','e'],1000,7)
        rows=[{'problem':p,'x':i} for i,p in enumerate(['a','b','c','d','e']) for _ in range(2)]
        n,d=inf.arrays(rows,lambda r:r['x'])
        np.testing.assert_equal(n,[0,2,4,6,8]);np.testing.assert_equal(d,[2]*5)
        self.assertEqual(inf.estimate(rows,lambda r:r['x'])['estimate'],2)

    def test_no_support_is_undefined(self):
        r=Inference(['p'],100,7).estimate([],lambda r:0)
        self.assertIsNone(r['estimate']);self.assertIsNone(r['ci95'])

    def test_kappa_degeneracy_is_not_perfect_agreement(self):
        self.assertTrue(np.isnan(kappa([[2,0,0],[0,0,0],[0,0,0]])))
        self.assertEqual(float(kappa(np.eye(3))),1)

    def test_linear_kappa_penalizes_distant_errors(self):
        near=[[5,1,0],[1,5,0],[0,0,5]];far=[[5,0,1],[0,5,0],[1,0,5]]
        self.assertGreater(kappa(near,True),kappa(far,True))

    def test_missing_judge_is_not_hedged(self):
        self.assertIsNone(panel({FIXED[0]:'firm'},'tie','historical'))


if __name__=='__main__':unittest.main()
