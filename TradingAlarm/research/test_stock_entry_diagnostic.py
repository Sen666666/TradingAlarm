import unittest
import pandas as pd
from stock_entry_diagnostic import select

class EntrySelectionTests(unittest.TestCase):
    def test_future_returns_cannot_change_selection_or_refill(self):
        f=pd.DataFrame(dict(date=['2020-01-02']*12,symbol=[f'{x:02}' for x in range(12)],atr_fraction=list(range(12)),turnover60=[100]*12,forward_10=[None]*12))
        a=select(f,'atr_fraction').symbol.tolist()
        f['forward_10']=list(reversed(range(12)))
        self.assertEqual(select(f,'atr_fraction').symbol.tolist(),a)
        self.assertEqual(a,[f'{x:02}' for x in range(10)])
    def test_current_liquidity_then_symbol_break_ties(self):
        f=pd.DataFrame(dict(date=['2020-01-02']*3,symbol=['C','B','A'],atr_fraction=[.02]*3,turnover60=[100,200,200]))
        self.assertEqual(select(f,'atr_fraction').symbol.tolist(),['A','B','C'])
if __name__=='__main__':unittest.main()
