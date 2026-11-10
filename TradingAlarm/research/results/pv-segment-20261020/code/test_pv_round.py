import unittest
import numpy as np
import pandas as pd
from trend_cash_book import simulate
from trend_pv_segment import segment_frame


def frame(n=7, volume=10000):
    ix=pd.bdate_range('2020-01-01',periods=n)
    return pd.DataFrame(dict(open=10.,close=10.,high=11.,low=9.,volume=float(volume)),index=ix)


def run(frames, values, **kw):
    ledger=[];orders=[];snapshots=[]
    states={s:pd.Series(v,index=frames[s].index,dtype=float) for s,v in values.items()}
    nav=simulate(frames,states,{s:f.index[0] for s,f in frames.items()},ledger,lot=100,orders=orders,snapshots=snapshots,**kw)
    cash=1e6;qty={s:0. for s in frames};byday={}
    for o in orders:byday.setdefault(o['date'],[]).append(o)
    for row in snapshots:
        for o in byday.get(row['date'],[]):
            cash-=o['units']*o['price']+o['fee'];qty[o['symbol']]+=o['units']
        assert abs(cash-row['cash'])<1e-7 and qty==row['quantities']
        value=cash+sum(qty[s]*float(f.loc[:row['date'],'close'].iloc[-1]) for s,f in frames.items())
        assert abs(value-row['nav'])<1e-7
    assert abs(sum(e['pnl'] for e in ledger)-(nav.iloc[-1]-1e6))<1e-7
    return nav,ledger,orders,snapshots


class CashTests(unittest.TestCase):
    def test_partial_sell_keeps_last_lot(self):
        nav,ep,orders,snap=run({'A':frame()},{'A':[0,1,1,0,0,0,0]})
        self.assertEqual(snap[4]['quantities']['A'],100)
        self.assertEqual(nav.iloc[-1],999980.)
        self.assertEqual([o['units'] for o in orders],[100,100,-100,-100])
    def test_open_one_lot_and_mark(self):
        nav,ep,_,_=run({'A':frame(4)},{'A':[0,0,1,1]})
        self.assertEqual(len(ep),1);self.assertTrue(ep[0]['open'])
        self.assertEqual(ep[0]['pnl'],-5);self.assertEqual(ep[0]['hypothetical_exit_fee'],5)
    def test_rotation_uses_sale_cash(self):
        a=frame(volume=1e9);b=a.copy();b.loc[b.index[4]:,'open']=[20,30,40];b['close']=b.open;b['high']=b.open+1;b['low']=b.open-1
        nav,_,orders,_=run({'A':a,'B':b},{'A':[0,1,0,0,0,0,0],'B':[0,0,1,1,1,1,1]})
        self.assertGreater(nav.iloc[-1],3.9e6)
        self.assertEqual([o['symbol'] for o in orders[:3]],['A','A','B'])
    def test_cancel_unfilled_buy(self):
        _,_,orders,_=run({'A':frame(6)},{'A':[0,1,0,0,0,0]})
        self.assertEqual([o['units'] for o in orders],[100,-100])
    def test_cancel_buy_without_any_fill(self):
        f=frame(6);f.loc[f.index[2],'volume']=0
        nav,_,orders,snap=run({'A':f},{'A':[0,1,0,0,0,0]})
        self.assertEqual(orders,[]);self.assertEqual(snap[-1]['pending'],{})
        self.assertEqual(nav.iloc[-1],1e6)
    def test_blocked_sale_then_budget_retry(self):
        a=frame(8,1e9);a.loc[a.index[3],'volume']=0
        _,_,orders,_=run({'A':a,'B':frame(8,1e9)},{'A':[0,1,0,0,0,0,0,0],'B':[0,0,1,1,1,1,1,1]})
        self.assertTrue(any(o['symbol']=='B' and o['date']>str(a.index[3].date()) and o['units']>100 for o in orders))

class ModelTests(unittest.TestCase):
    def test_prefix_and_unit_invariance(self):
        rng=np.random.default_rng(42);ix=pd.bdate_range('2020-01-01',periods=240)
        c=pd.Series(np.exp(np.cumsum(rng.normal(.001,.02,240))),index=ix)
        v=pd.Series(np.exp(rng.normal(8,1,240)),index=ix)
        a=segment_frame(c,v)
        pd.testing.assert_frame_equal(segment_frame(c,v*0+100),segment_frame(c,v*0+100,joint=False))
        pd.testing.assert_frame_equal(a.iloc[:150],segment_frame(c.iloc[:150],v.iloc[:150]))
        np.testing.assert_allclose(a,segment_frame(c*100,v*1000),atol=1e-8,rtol=1e-7,equal_nan=True)
    def test_flat_is_neutral(self):
        ix=pd.bdate_range('2020-01-01',periods=100)
        a=segment_frame(pd.Series(10.,index=ix),pd.Series(100.,index=ix))
        self.assertTrue(a.strength.dropna().eq(0).all())

if __name__=='__main__':unittest.main()
