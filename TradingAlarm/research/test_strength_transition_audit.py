import unittest
import pandas as pd
from strength_transition_audit import changes
class Tests(unittest.TestCase):
    def test_symbol_separation_and_first_rows(self):
        f=pd.DataFrame(dict(date=pd.to_datetime(['2026-01-01','2026-01-02','2026-01-03']*2),symbol=['A']*3+['B']*3,strength=[1,5,3,9,9,10]))
        r=changes(f,1);self.assertEqual(r.change.tolist(),[4,-2,0,1]);self.assertEqual(r.direction.tolist(),['rising','falling','flat','rising'])
        self.assertEqual(changes(f,2).change.tolist(),[2,1])
if __name__=='__main__':unittest.main()
