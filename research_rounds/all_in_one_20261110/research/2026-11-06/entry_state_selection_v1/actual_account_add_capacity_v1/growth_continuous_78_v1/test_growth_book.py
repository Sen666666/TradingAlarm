import unittest
from decimal import Decimal as D
from growth_book import GrowthBook,PendingLedger,principal,layer_profit,growth_allowed,Z

def buy(q,price,layer,order=None,fee=0):
    return dict(kind='real_buy_fill',sid='S',shares=q,price=D(str(price)),fees=D(str(fee)),layer=layer,budget_order=order or str(layer))
def sale(q,price,parts,fee=0):
    net=D(str(price))*q-D(str(fee))
    return dict(kind='real_sell_fill',sid='S',shares=q,price=D(str(price)),fees=D(str(fee)),parts=[dict(layer=k,shares=n,net_cash=net*D(n)/q) for k,n in parts])
class TestCosts(unittest.TestCase):
    def init(self,seed=10,add=20):
        b=GrowthBook();b.apply(buy(100,seed,1),lambda r:D(100));b.apply(buy(100,add,2),lambda r:D(100));return b
    def test_high_cost_sale_delta_negative(self):
        b=self.init();b.apply(sale(50,15,[(2,50)]));s=b.states['S']
        self.assertEqual((s.layer_cost,s.avg_cost,s.delta,s.H),(D(2000),D(2250),D(-250),D(250)))
        self.assertEqual(layer_profit(150,16,0,s.layer_cost)-layer_profit(150,16,0,s.avg_cost),-s.delta)
        self.assertEqual(s.buy_cash,s.retired_cost+s.layer_cost)
    def test_low_cost_sale_delta_positive_and_profit_disagrees(self):
        b=self.init();b.apply(sale(100,11,[(1,100)]));s=b.states['S']
        self.assertEqual((s.layer_cost,s.avg_cost,s.delta,s.H),(D(2000),D(1500),D(500),Z))
        avg=layer_profit(100,17,0,s.avg_cost);actual=layer_profit(100,17,0,s.layer_cost)
        self.assertGreater(avg,0);self.assertLess(actual,0)
        self.assertFalse(growth_allowed(100,100,avg,actual,D(1),Z,Z,Z,D(1),D(100)))
    def test_fee_allocated_once_and_partial_resale(self):
        b=GrowthBook();b.apply(buy(100,10,1,fee=5),lambda r:D(100));b.apply(buy(200,20,2,fee=5),lambda r:D(100))
        b.apply(sale(150,19,[(1,50),(2,100)],fee=6));s=b.states['S']
        self.assertEqual(s.sell_cash,D(2844))
        self.assertEqual(s.retired_cost,D('2505'))
        self.assertEqual(s.realized,D(339))
        self.assertEqual(s.H,D('106.5'))
        oldH=s.H;b.apply(sale(100,22,[(2,100)],fee=5));self.assertEqual(s.H,oldH)
        liquidation=layer_profit(s.qty,12,5,s.layer_cost)
        self.assertEqual(s.realized+liquidation,s.sell_cash+(D(s.qty)*12*D('.9995')-5)-s.buy_cash)
    def test_protection_raises_only_L(self):
        b=self.init();b.apply(sale(50,15,[(2,50)]));s=b.states['S'];lot=s.lots[2];h=s.H
        lower=principal(lot.cost,lot.qty,10,5);upper=principal(lot.cost,lot.qty,19,5)
        self.assertLess(upper,lower);self.assertEqual(s.H,h)
    def test_split_matches_native_allocation(self):
        b=GrowthBook();b.apply(buy(101,10,1),lambda r:D(100));b.apply(buy(101,20,2),lambda r:D(100))
        before=b.states['S'].layer_cost;b.apply(dict(kind='actual_split',sid='S',ratio=D('1.5')))
        s=b.states['S'];self.assertEqual([x.qty for x in s.lots.values()],[152,151]);self.assertEqual(s.layer_cost,before);self.assertEqual(s.R0,D(100));self.assertEqual(s.delta,0)
    def test_split_zero_layer_is_unknown(self):
        b=GrowthBook();b.apply(buy(1,10,1),lambda r:D(100));b.apply(buy(1,20,2),lambda r:D(100));b.apply(dict(kind='actual_split',sid='S',ratio=D('.5')))
        self.assertIn('SPLIT_ZERO_LAYER_COST_REQUIRES_AUDIT',b.states['S'].unknown)
    def test_round_reset_only_after_flat(self):
        b=self.init();b.apply(sale(200,8,[(1,100),(2,100)]));self.assertGreater(b.states['S'].H,0)
        b.apply(buy(100,9,3),lambda r:D(50));s=b.states['S'];self.assertEqual(s.number,2);self.assertEqual(s.H,0);self.assertEqual(s.R0,50);self.assertFalse(s.lots[3].added)
    def test_multifill_seed_is_unknown_not_budget_growth(self):
        b=GrowthBook();b.apply(buy(100,10,1,'order'),lambda r:D(100));b.apply(buy(100,10,2,'order'),lambda r:D(100))
        self.assertIn('MULTIFILL_ORDER_REQUIRES_SEED_CONTRACT_AUDIT',b.states['S'].unknown)
        self.assertEqual(b.states['S'].R0,D(100))
    def test_pending_partial_and_ack(self):
        p=PendingLedger();p.reserve('o',200,4000,10);old=p.risk('o',18,5)
        p.fill('o',100,2000,5);half=p.risk('o',18,5);self.assertLess(half,old)
        p.request_cancel('o');self.assertEqual(p.risk('o',18,5),half)
        p.ack('o');self.assertFalse(p.orders)
    def test_partial_fill_P_to_L_only_extra_separate_sale_minimum_fee(self):
        p=PendingLedger();p.reserve('o',200,4000,5)
        before=p.risk('o',18,5)
        p.fill('o',100,2000,5)
        remaining=p.risk('o',18,5);live=principal(D(2005),100,18,5)
        # Separate remaining-order/live-layer stop estimates each pay a minimum fee.
        self.assertEqual(remaining+live-before,5)
        p.request_cancel('o');self.assertEqual(p.risk('o',18,5),remaining)
        p.ack('o');self.assertEqual(live,principal(D(2005),100,18,5))
    def test_pending_split_preserves_monetary_reserve(self):
        p=PendingLedger();p.reserve('o',100,1000,5);before=p.risk('o',8,5)
        p.split('o',2)
        self.assertEqual(p.orders['o']['qty'],200)
        self.assertEqual(p.orders['o']['gross']+p.orders['o']['fee'],1005)
        self.assertEqual(p.risk('o',4,5),before)
    def test_seed_pending_still_reserves_cash(self):
        p=PendingLedger();p.reserve('o',100,1000,5,added=False)
        self.assertEqual(p.risk('o',1,5),0);self.assertEqual(p.orders['o']['gross']+p.orders['o']['fee'],1005)
    def test_initial_trial_exempt_and_add_no_minimum_waiver(self):
        self.assertTrue(growth_allowed(100,0,-1,-1,-1,100,100,100,100,0,False))
        self.assertFalse(growth_allowed(100,100,10,10,1,0,0,0,30,100))
        self.assertFalse(growth_allowed(200,100,1000,1000,990,0,0,0,30,100))
    def test_seed_loss_is_not_hidden_in_H(self):
        b=self.init(seed=20,add=10);b.apply(sale(100,15,[(1,100)]));s=b.states['S']
        self.assertEqual(s.H,0);self.assertEqual(s.H_all,500);self.assertEqual(s.realized,-500)
        # No slippage in this pure identity; engine separately charges dated fees.
        self.assertEqual(D(1500)-s.layer_cost,500)
        self.assertEqual(s.realized+D(1500)-s.layer_cost,0)
    def test_added_loss_moves_U_and_H_without_double_count(self):
        b=self.init();s=b.states['S'];U_before=D(15)*s.qty-s.layer_cost;H_before=s.H
        b.apply(sale(50,15,[(2,50)]));s=b.states['S'];U_after=D(15)*s.qty-s.layer_cost
        self.assertEqual(U_after-s.H,U_before-H_before)
    def test_mixed_added_profit_does_not_cancel_loss_debt(self):
        b=GrowthBook();b.apply(buy(100,10,1),lambda r:D(100));b.apply(buy(100,20,2),lambda r:D(100));b.apply(buy(100,10,3),lambda r:D(100))
        s=b.states['S'];before=D(15)*s.qty-s.layer_cost-s.H
        b.apply(sale(200,15,[(2,100),(3,100)]));s=b.states['S']
        self.assertEqual(s.H,500);self.assertEqual(s.realized,0)
        self.assertEqual(D(15)*s.qty-s.layer_cost-s.H,before-D(500))
    def test_realized_and_open_profit_independent_of_cost_attribution(self):
        b=self.init();b.apply(sale(50,15,[(2,50)]));s=b.states['S'];net=D(s.qty)*16-5
        self.assertEqual(s.realized+(net-s.layer_cost),s.avg_realized+(net-s.avg_cost))
        self.assertEqual(s.realized-s.avg_realized,s.delta)
    def test_growth_not_permanent_R0_cap(self):
        self.assertTrue(growth_allowed(100,100,200,200,190,0,0,0,180,100))

if __name__=='__main__':unittest.main(verbosity=2)
