import unittest
import pandas as pd
from compare_reference import compare

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.x=pd.DataFrame({'date':['2024-01-02','2024-01-03'],'close':[100.,101.],'temperature':['温','热']})
        self.meta={'instrument_id':'fixture_only','price_basis':'raw','source':'synthetic test','label_vintage':'point_in_time'}

    def test_equal_labels(self):
        r=compare(self.x,self.x,self.meta,self.meta)
        self.assertEqual(r['exact_agreement'],1)

    def test_different_asset_refused(self):
        other={**self.meta,'instrument_id':'different'}
        r=compare(self.x,self.x,self.meta,other)
        self.assertEqual(r['status'],'not_comparable')
        self.assertNotIn('exact_agreement',r)

    def test_price_difference_refused(self):
        y=self.x.copy(); y.loc[0,'close']=99
        self.assertEqual(compare(self.x,y,self.meta,self.meta)['status'],'not_comparable')

    def test_missing_labels_not_treated_as_flat(self):
        y=self.x.copy(); y.loc[0,'temperature']=None
        r=compare(self.x,y,self.meta,self.meta)
        self.assertEqual(r['paired_label_dates'],1)
        self.assertEqual(r['coverage_of_reference_rows'],.5)

    def test_disagreement_measured(self):
        y=self.x.copy(); y['temperature']=['平','冻']
        r=compare(self.x,y,self.meta,self.meta)
        self.assertEqual(r['exact_agreement'],0)
        self.assertEqual(r['within_one_band'],.5)
        self.assertEqual(r['mean_absolute_band_difference'],3)

if __name__=='__main__': unittest.main()
