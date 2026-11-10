import unittest
import numpy as np
import pandas as pd
from a_stock_campaign_shadow import simulate


class ShadowTests(unittest.TestCase):
    def bundle(self):
        shape=(8,2)
        b={k:np.full(shape,v,dtype=float) for k,v in [('close',100.),('open',100.),('atr',1.),('momentum',1.)]}
        b.update({k:np.full(shape,v,dtype=bool) for k,v in [('active',True),('execute',True),('exit',False),('entry',False),('gate',True)]})
        b['dates']=pd.bdate_range('2022-01-03',periods=8).to_numpy();b['names']=np.array(['a','b'])
        return b

    def test_next_open_ranking_capacity_and_no_future_close_leak(self):
        b=self.bundle();b['entry'][0]=True;b['atr'][:,1]=2
        _,p,o,_,_=simulate(b,max_positions=1,guard=False)
        self.assertEqual(len(o),1);self.assertEqual(o[0]['symbol'],'a');self.assertEqual(o[0]['date'],'2022-01-04')
        self.assertGreaterEqual(p.cash.min(),0)
        changed={k:v.copy() for k,v in b.items()};changed['close'][5:]=1000
        _,pp,oo,_,_=simulate(changed,max_positions=1,guard=False)
        self.assertEqual(o,oo);pd.testing.assert_frame_equal(p.iloc[:4],pp.iloc[:4])

    def test_blocked_exit_persists_and_stale_marks_never_create_cash(self):
        b=self.bundle();b['entry'][0,0]=True;b['close'][2:,0]=90.;b['execute'][3:5,0]=False
        b['close'][4:,0]=110.;b['open'][5,0]=93.
        _,_,orders,closed,_=simulate(b,guard=False)
        self.assertEqual(orders[1]['date'],'2022-01-10');self.assertEqual(orders[1]['price'],93.)
        self.assertEqual(len(closed),1)
        b['execute'][3:,0]=False;b['active'][3:,0]=False
        m,p,o,c,s=simulate(b,guard=False)
        self.assertEqual(len(c),0);self.assertEqual(s[0]['mark_date'],'2022-01-05')
        self.assertEqual(p.cash.iloc[-1],p.cash.iloc[0]);self.assertGreater(m['terminal_stale_value'],0)
        self.assertTrue(s[0]['pending_exit'])

    def test_unfilled_entry_is_revalidated_not_queued(self):
        b=self.bundle();b['entry'][0,0]=True;b['execute'][1,0]=False
        _,_,orders,_,_=simulate(b,guard=False)
        self.assertEqual(orders,[])

    def test_drawdown_guard_cannot_fill_blocked_liquidation(self):
        b=self.bundle();b['entry'][0]=True;b['atr'][:]=.1
        b['close'][2:]=1.;b['open'][3:]=1.;b['execute'][3:]=False
        m,p,_,c,s=simulate(b)
        self.assertLess(m['max_shadow_drawdown'],-.16)
        self.assertGreater(m['halted_sessions'],0);self.assertEqual(len(c),0)
        self.assertTrue(all(r['pending_exit'] for r in s))

    def test_full_risk_sensitivity_skips_cap_truncated_entry(self):
        b=self.bundle();b['entry'][0]=True;b['atr'][:]=.1
        _,_,partial,_,_=simulate(b,guard=False)
        _,_,full,_,_=simulate(b,guard=False,full_entry_risk=True)
        self.assertGreater(len(partial),0);self.assertEqual(full,[])

    def completion_bundle(self):
        b=self.bundle();b['entry'][0,0]=True;b['entry'][1:3,1]=True
        b['close'][1:,0]=125.;b['open'][2:,0]=127.;b['exit'][2,0]=True
        b['open'][3:,1]=101.;b['close'][3:,1]=101.
        return b

    def test_completion_keeps_original_budget_and_stop(self):
        b=self.completion_bundle();_,_,o,_,s=simulate(b,guard=False,complete_initial=True,cost_bps=0)
        buys=[x for x in o if x['symbol']=='b' and x['side']=='buy']
        self.assertEqual(len(buys),2);first,add=buys
        self.assertEqual(first['kind'],'initial');self.assertEqual(add['kind'],'completion')
        self.assertEqual(add['date'],'2022-01-06')
        self.assertEqual(first['risk_budget'],add['risk_budget']);self.assertEqual(first['stop'],add['stop'])
        self.assertAlmostEqual(sum(x['quantity']*(x['price']-x['stop']) for x in buys),first['risk_budget'])
        self.assertAlmostEqual(s[0]['initial_risk'],first['risk_budget'])
        self.assertGreaterEqual(add['price'],first['price'])

    def test_completion_never_averages_down_or_ignores_pending_exit(self):
        b=self.completion_bundle();b['open'][3,1]=99.
        _,_,o,_,_=simulate(b,guard=False,complete_initial=True)
        self.assertFalse(any(x.get('kind')=='completion' for x in o))
        b=self.completion_bundle();b['exit'][2,1]=True;b['execute'][3,1]=False
        _,_,o,_,_=simulate(b,guard=False,complete_initial=True)
        self.assertFalse(any(x.get('kind')=='completion' for x in o))
        self.assertEqual(next(x['date'] for x in o if x['symbol']=='b' and x['side']=='sell'),'2022-01-07')

    def test_completion_revalidates_prior_signal(self):
        b=self.completion_bundle();b['entry'][2,1]=False
        _,_,o,_,_=simulate(b,guard=False,complete_initial=True)
        self.assertFalse(any(x.get('kind')=='completion' for x in o))


if __name__=='__main__':unittest.main()
