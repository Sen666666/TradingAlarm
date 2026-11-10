import unittest
import pandas as pd
from sector_exit_context import join_context
class Tests(unittest.TestCase):
 def test_exact_date_join_no_future_fill(self):
  e=pd.DataFrame({'date':pd.to_datetime(['2026-01-01','2026-01-02']),'symbol':['a','a']});m=e.assign(proxy='p');states=pd.DataFrame({'date':pd.to_datetime(['2026-01-02']),'proxy_symbol':['p'],'score':[9.]})
  z=join_context(e,m,states,'proxy');self.assertTrue(pd.isna(z.score.iloc[0]));self.assertEqual(z.score.iloc[1],9)
  with self.assertRaises(pd.errors.MergeError):join_context(e,pd.concat([m,m]),states,'proxy')
if __name__=='__main__':unittest.main()
