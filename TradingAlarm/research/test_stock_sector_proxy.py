import unittest
import numpy as np
from stock_sector_proxy import best_proxy
class ProxyTests(unittest.TestCase):
 def test_insufficient_or_negative_relationship_rejected(self):
  x=np.arange(126,dtype=float)
  self.assertEqual(best_proxy(x,{'a':-x},{'a':True}),(None,None))
  y=x.copy();y[:30]=np.nan
  self.assertEqual(best_proxy(x,{'a':y},{'a':True}),(None,None))
 def test_unseasoned_proxy_excluded_and_ties_deterministic(self):
  x=np.arange(126,dtype=float)
  self.assertEqual(best_proxy(x,{'b':x,'a':x},{'a':True,'b':True})[0],'a')
  self.assertEqual(best_proxy(x,{'b':x,'a':x},{'a':False,'b':True})[0],'b')
if __name__=='__main__':unittest.main()
