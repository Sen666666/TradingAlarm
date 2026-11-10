import unittest
from dataclasses import replace
from decimal import Decimal as D
from budget_service_v3 import (Asset, Charge, Claim, ContractError, Intent, PromotionProof,
                            RoundLimits, SharedBudget, WalletLimits)


def charge(cash='10', capital='9.9', slot='9.9', nominal='.5', fee='.6'):
    return Charge(*map(D, (cash, capital, slot, nominal, fee)))

def rlimits():
    return RoundLimits(D('1000'), D('20'), D('20'), D('40'), D('2.5'), 'SYNTHETIC:signal-close')

def wlimits(**changes):
    return replace(WalletLimits(D('1000'), D('1000'), D('100'), D('5'), D('20'), D('20'), True, 'SYNTHETIC:open-snapshot'), **changes)

def intent(oid='o1', stock='s1', rid='r1', sector='sector1', kind='INIT', pool='PROBE', c=None, slot=1):
    return Intent(oid, stock, rid, sector, kind, pool, c or charge(), slot if kind == 'INIT' else None, 'SYNTHETIC:AB-intention')

def asset(lot='lot1', stock='s1', rid='r1', sector='sector1', pool='PROBE', c=None, filled=1, known=True):
    return Asset(lot, stock, rid, sector, pool, c or charge(), filled, known)

def wallet(*, seed='100', flows=None, assets=(), claims=(), add_used=(), session=2):
    return SharedBudget(session=session, seed_cash=D(seed), cash_by_round=flows or {},
                        round_limits={f'r{i}': rlimits() for i in range(1, 20)},
                        assets=assets, claims=claims, add_used=add_used)

def allocate(w, order_id, limits=None):
    # All caps here are SYNTHETIC external input. This does not calculate real fees.
    return w.reserve_next(order_id, allocation_limits=limits or w._limits)

def good_proof(stock='s1', rid='r1'):
    return PromotionProof(stock, rid, 'SYNTHETIC:open-snapshot', D('1'), D('1'), True, True, 'SYNTHETIC:CP-only')

def ready(w, entries, limits=None, proofs=()):
    w.freeze_snapshot(limits or wlimits(), proofs)
    w.freeze_queue(entries, policy_ref='SYNTHETIC:externally-frozen-global-order')
    return w

class BudgetSyntheticTests(unittest.TestCase):
    def test_01_close_opportunities_are_not_cash_reservations(self):
        w = wallet(seed='10')
        entries = (intent('o1'), intent('o2', 's2', 'r2', 'sector2'))
        self.assertEqual(w.available_cash, D('10'))
        ready(w, entries)
        self.assertEqual(w.available_cash, D('10'))
        self.assertEqual(w.reservations, ())
        self.assertTrue(allocate(w, 'o1'))
        self.assertEqual(w.available_cash, D('0'))
        self.assertFalse(allocate(w, 'o2'))

    def test_02_ex_claim_does_not_fund_open_and_pay_is_next_open(self):
        w = wallet(seed='0')
        cl = Claim('claim1', 'old_stock', 'r9', D('10'), 'SYNTHETIC:registered-ex')
        w.record_claim(event_id='ex1', claim=cl)
        self.assertEqual(w.cash, D('0'))
        self.assertEqual(w.round_claims('r9'), D('10'))
        with self.assertRaises(ContractError):
            w.settle_claim(event_id='pay1', claim_id='claim1', value=D('10'), effective_session=3, source_ref='SYNTHETIC:pay-close')
        self.assertEqual(w.cash, D('0'))
        before = w.cash + w.round_claims('r9')
        w.settle_claim(event_id='pay1', claim_id='claim1', value=D('10'), effective_session=2, source_ref='SYNTHETIC:previous-pay-close')
        self.assertEqual(w.cash + w.round_claims('r9'), before)
        ready(w, (intent(),))
        self.assertTrue(allocate(w, 'o1'))

    def test_03_known_exits_release_cash_before_queue_and_t1_is_per_fill(self):
        old = asset('old', filled=1)
        today = asset('today', c=charge('5','4.9','4.9','.2','.3'), filled=2)
        w = wallet(seed='0', assets=(old, today))
        w.record_exit(event_id='sell-old', lot_id='old', net_cash=D('10'), source_ref='SYNTHETIC:whole-order-dated-fee')
        with self.assertRaisesRegex(ContractError, 'T\\+1'):
            w.record_exit(event_id='sell-new', lot_id='today', net_cash=D('5'), source_ref='SYNTHETIC:bad-same-day-sale')
        self.assertEqual([a.lot_id for a in w.assets], ['today'])
        ready(w, (intent('o2','s2','r2','sector2'),))
        self.assertTrue(allocate(w, 'o2'))

    def test_04_cash_includes_fee_and_risk_dimensions_are_distinct(self):
        cases = [
            (charge('20.01','20','20','1','1.1'), wlimits(), 'INITIAL_FEE_INCLUSIVE_CASH_BUDGET'),
            (charge('20','19.9','19.9','1','2.51'), wlimits(), 'ROUND_FEE_INCLUSIVE_RISK_CAP'),
            (charge(), wlimits(probe_nominal_risk_cap=D('.4')), 'GLOBAL_PROBE_NOMINAL_RISK_CAP'),
        ]
        for c, limits, expected in cases:
            with self.subTest(expected=expected):
                w=ready(wallet(), (intent(c=c),), limits)
                self.assertFalse(allocate(w, 'o1'))
                self.assertEqual(w.decisions[-1][1], expected)
                self.assertEqual(w.cash, D('100'))
        w=ready(wallet(seed='19.9'), (intent(c=charge('20','19.9','19.9','1','1.1')),))
        self.assertFalse(allocate(w, 'o1'))
        self.assertEqual(w.decisions[-1][1], 'INSUFFICIENT_UNRESERVED_CASH')
        effective = D('1199977.2')
        caps = WalletLimits(D('1200000'), effective, effective * D('.10'), D('5999.886'), D('24000'), None, True, 'SYNTHETIC:open-snapshot')
        self.assertLessEqual(D('5999.08'), caps.probe_nominal_risk_cap)
        self.assertEqual(caps.probe_nominal_risk_cap, effective * D('.005'))
        reference_round = RoundLimits(D('1200000'),D('24000'),D('24000'),D('48000'),D('3000'),'SYNTHETIC:boundary-close')
        def boundary_wallet(risks):
            many = tuple(asset(f'h{k}',f's{k}',f'r{k}',f'sector{k}',c=charge('10000','10000','10000',risk,'2000')) for k,risk in enumerate(risks,1))
            return SharedBudget(session=2,seed_cash=D('1200000'),cash_by_round={f'r{k}':D('-10000') for k in (1,2,3)},round_limits={f'r{k}':reference_round for k in (1,2,3,4)},assets=many)
        boundary_order=intent('boundary','s4','r4','sector4',c=charge('1','1','1','0','1'))
        w = ready(boundary_wallet(('1999.69','1999.69','1999.70')), (boundary_order,), caps)
        self.assertEqual(w.usage(pool='PROBE').nominal_risk,D('5999.08'))
        self.assertTrue(allocate(w, 'boundary', caps))
        w = ready(boundary_wallet(('2000','2000','1999.90')), (boundary_order,), caps)
        self.assertLess(w.usage(pool='PROBE').nominal_risk,D('6000'))
        self.assertFalse(allocate(w, 'boundary', caps))
        self.assertEqual(w.decisions[-1][1],'GLOBAL_PROBE_NOMINAL_RISK_CAP')
        with self.assertRaises(ContractError):
            replace(caps,probe_nominal_risk_cap=D('6000'))

    def test_05_partial_fill_and_cancel_pending_keep_all_obligations(self):
        full=charge('20','19.8','19.8','1','1.2')
        half=charge('10','9.9','9.9','.5','.6')
        w=ready(wallet(), (intent(c=full),))
        self.assertTrue(allocate(w, 'o1'))
        self.assertEqual(w.available_cash,D('80'))
        before=w.usage(pool='PROBE')
        w.record_fill(event_id='fill1',order_id='o1',lot_id='f1',filled=half,source_ref='SYNTHETIC:execution')
        self.assertEqual(w.cash,D('90'))
        self.assertEqual(w.available_cash,D('80'))
        self.assertEqual(w.usage(pool='PROBE'),before)
        w.request_cancel('o1')
        self.assertEqual(w.available_cash,D('80'))
        self.assertEqual(w.reservations[0].status,'cancel_pending')
        w.confirm_cancel(event_id='cancel1',order_id='o1')
        self.assertEqual(w.available_cash,D('90'))
        self.assertEqual(w.usage(pool='PROBE').capital,D('9.9'))
        with self.assertRaises(ContractError):
            w.confirm_cancel(event_id='cancel1',order_id='o1')

    def test_06_probe_and_industry_all_caps_include_held_live_and_cancel(self):
        first=intent('o1',sector='same')
        second=intent('o2','s2','r2','same',slot=2)
        w=ready(wallet(), (first,second), wlimits(probe_industry_all_capital_cap=D('19')))
        self.assertTrue(allocate(w, 'o1'));w.request_cancel('o1')
        self.assertFalse(allocate(w, 'o2'))
        self.assertEqual(w.decisions[-1][1],'INDUSTRY_ALL_CAPITAL_CAP')
        held=asset(pool='CORE',sector='same')
        w=ready(wallet(assets=(held,)), (second,), wlimits(probe_industry_all_capital_cap=D('19')))
        self.assertFalse(allocate(w, 'o2'))
        self.assertEqual(w.decisions[-1][1],'INDUSTRY_ALL_CAPITAL_CAP')
        w=ready(wallet(assets=(asset(),)), (intent('o2','s2','r2','sector2'),),wlimits(probe_capital_cap=D('19')))
        self.assertFalse(allocate(w, 'o2'))
        self.assertEqual(w.decisions[-1][1],'GLOBAL_PROBE_CAPITAL_CAP')

    def test_07_core_add_share_round_slot_risk_and_only_one_add(self):
        held=asset(pool='CORE',c=charge('20','19','35','1','2'))
        add=intent('add1',kind='ADD',pool='CORE',c=charge('10','1','6','.1','.2'))
        w=ready(wallet(assets=(held,)),(add,),wlimits(),proofs=(good_proof(),))
        self.assertFalse(allocate(w, 'add1'))
        self.assertEqual(w.decisions[-1][1],'ROUND_SLOT_CAP')
        held=replace(held,charge=charge('20','19','19','1','2.4'))
        w=ready(wallet(assets=(held,)),(add,),wlimits(),proofs=(good_proof(),))
        self.assertFalse(allocate(w, 'add1'))
        self.assertEqual(w.decisions[-1][1],'ROUND_FEE_INCLUSIVE_RISK_CAP')
        held=replace(held,charge=charge('10','9.9','9.9','.5','.6'))
        add=replace(add,charge=charge())
        second=replace(add,order_id='add2')
        w=ready(wallet(assets=(held,)),(add,second),proofs=(good_proof(),))
        self.assertTrue(allocate(w, 'add1'))
        w.record_fill(event_id='addfill',order_id='add1',lot_id='a2',filled=add.charge,source_ref='SYNTHETIC:add-fill')
        self.assertFalse(allocate(w, 'add2'))
        self.assertEqual(w.decisions[-1][1],'ADD_ALREADY_USED_OR_LIVE')
        for proof in (None, replace(good_proof(),close_net80=D('-1')), replace(good_proof(),open_net80=D('-1')), replace(good_proof(),fresh_cp_after_first_fill=False), replace(good_proof(),m3_true=False)):
            w=ready(wallet(assets=(held,)),(add,),proofs=() if proof is None else (proof,))
            self.assertFalse(allocate(w,'add1'))
            self.assertEqual(w.decisions[-1][1],'ADD_REQUIRES_CURRENT_ROUND_AB_PROOF')

        held=asset(pool='CORE',c=charge('20','30','30','.5','.6'))
        addon=intent('core-add',kind='ADD',pool='CORE',c=charge('5','5','5','.2','.3'))
        core_caps=wlimits(confirmed_industry_all_capital_cap=D('100'))
        w=ready(wallet(assets=(held,)),(addon,),core_caps,proofs=(good_proof(),))
        self.assertGreater(w.usage(sector='sector1').capital,core_caps.probe_industry_all_capital_cap)
        self.assertTrue(allocate(w,'core-add',core_caps))
        w=ready(wallet(assets=(held,)),(addon,),wlimits(confirmed_industry_all_capital_cap=None),proofs=(good_proof(),))
        self.assertFalse(allocate(w,'core-add'))
        self.assertEqual(w.decisions[-1][1],'CONFIRMED_INDUSTRY_CAP_NOT_FROZEN')
        probe=intent('probe-next','s2','r2','sector1',c=charge('1','1','1','.1','.2'),slot=2)
        w=ready(wallet(assets=(held,)),(probe,),core_caps)
        self.assertFalse(allocate(w,'probe-next',core_caps))
        self.assertEqual(w.decisions[-1][1],'INDUSTRY_ALL_CAPITAL_CAP')

    def test_08_external_queue_is_fixed_and_no_third_industry_refill(self):
        entries=(intent('z','s2','r2','sector2'),intent('a','s1','r1','sector1'))
        w=ready(wallet(seed='10'),entries)
        with self.assertRaises(ContractError):allocate(w, 'a')
        self.assertTrue(allocate(w, 'z'))
        self.assertFalse(allocate(w, 'a'))
        with self.assertRaises(ContractError):allocate(w, 'third')
        with self.assertRaises(ContractError):intent(slot=3)
        w=wallet();w.freeze_snapshot(wlimits())
        with self.assertRaises(ContractError):
            w.freeze_queue((intent(),intent('o2','s2','r2','sector1')),policy_ref='SYNTHETIC:duplicate-slot')
        self.assertEqual(w.available_cash,D('100'))

    def test_09_promotion_is_one_stock_full_round_evidence_not_sector(self):
        a1=asset();a2=asset('lot2','s2','r2','sector1')
        proof=PromotionProof('s1','r1','SYNTHETIC:open-snapshot',D('1'),D('2'),True,True,'SYNTHETIC:CP-proof-only')
        w=wallet(assets=(a1,a2));before=(w.cash,w.assets,w.claims)
        w.freeze_snapshot(wlimits(),(proof,));w.promote_stock('s1','r1')
        self.assertEqual([a.pool for a in w.assets],['CORE','PROBE'])
        self.assertEqual(w.cash,before[0]);self.assertEqual(w.claims,before[2])
        self.assertEqual(w.assets[0],replace(a1,pool='CORE'))
        with self.assertRaises(ContractError):w.promote_stock('s2','r2')
        for invalid in (replace(proof,close_net80=D('0')),replace(proof,open_net80=D('0')),replace(proof,fresh_cp_after_first_fill=False),replace(proof,m3_true=False)):
            w=wallet(assets=(a1,));w.freeze_snapshot(wlimits(),(invalid,))
            with self.assertRaises(ContractError):w.promote_stock('s1','r1')
        w=wallet(assets=(replace(a1,filled_session=2),));w.freeze_snapshot(wlimits(),(proof,))
        with self.assertRaises(ContractError):w.promote_stock('s1','r1')
        w=wallet(assets=(replace(a1,pool='CORE'),));w.freeze_snapshot(wlimits(),(proof,))
        with self.assertRaisesRegex(ContractError,'PROBE'):w.promote_stock('s1','r1')

    def test_10_old_round_dividend_never_enters_new_round_cash_or_claims(self):
        claim=Claim('oldclaim','s1','r9',D('100'),'SYNTHETIC:old-round-registered-stock')
        w=wallet(seed='1',flows={'r1':D('-1')},assets=(asset(),),claims=(claim,))
        self.assertEqual(w.round_claims('r1'),D('0'))
        w.settle_claim(event_id='oldpay',claim_id='oldclaim',value=D('100'),effective_session=2,source_ref='SYNTHETIC:old-pay')
        self.assertEqual(w.cash,D('100'));self.assertEqual(w.round_cash('r1'),D('-1'))
        self.assertEqual(w.round_cash('r9'),D('100'))
        proof=PromotionProof('s1','r1','SYNTHETIC:open-snapshot',D('-1'),D('-1'),True,True,'SYNTHETIC:new-round-negative')
        w.freeze_snapshot(wlimits(),(proof,))
        with self.assertRaises(ContractError):w.promote_stock('s1','r1')

    def test_11_unknown_retains_assets_allows_known_exit_and_claim_then_blocks_new(self):
        unknown=asset('unknown',known=False)
        known=asset('known','s2','r2','sector2')
        cl=Claim('c','s1','r1',D('2'),'SYNTHETIC:confirmed-old-claim')
        w=wallet(seed='0',assets=(unknown,known),claims=(cl,))
        w.record_exit(event_id='sell',lot_id='known',net_cash=D('10'),source_ref='SYNTHETIC:known-exit')
        w.settle_claim(event_id='pay',claim_id='c',value=D('2'),effective_session=2,source_ref='SYNTHETIC:confirmed-pay')
        self.assertEqual(w.cash,D('12'));self.assertEqual(w.assets,(unknown,))
        self.assertEqual(w.usage().capital,unknown.charge.capital)
        proof=PromotionProof('s1','r1','SYNTHETIC:open-snapshot',D('1'),D('1'),True,True,'SYNTHETIC:insufficient-because-UNKNOWN')
        w.freeze_snapshot(wlimits(),(proof,))
        with self.assertRaises(ContractError):w.promote_stock('s1','r1')
        w.freeze_queue((intent('o3','s3','r3','sector3'),),policy_ref='SYNTHETIC:frozen-order')
        self.assertFalse(allocate(w, 'o3'))
        self.assertEqual(w.decisions[-1][1],'UNCERTIFIED_EVIDENCE_FREEZE')
        self.assertEqual(w.assets,(unknown,))
        w=ready(wallet(),(intent(),),wlimits(nav_certified=False))
        self.assertFalse(allocate(w, 'o1'))

    def test_12_decimal_validation_duplicate_events_and_invalid_fill_are_atomic(self):
        for bad in (0.1,D('NaN'),D('Infinity'),D('-1')):
            with self.assertRaises(ContractError):Charge(bad,D('0'),D('0'),D('0'),D('0'))
        for field,value in (('initial_cash_budget','20.01'),('add_cash_budget','20.01'),('slot_cap','40.01'),('fee_risk_cap','2.5001')):
            with self.assertRaises(ContractError):replace(rlimits(),**{field:D(value)})
        with self.assertRaises(AttributeError):
            rlimits().signal_close_ref='SYNTHETIC:later-close-must-not-replace-first-close'
        w=ready(wallet(),(intent(),));self.assertTrue(allocate(w, 'o1'))
        before=(w.cash,w.available_cash,w.assets,w.reservations)
        with self.assertRaises(ContractError):
            w.record_fill(event_id='f',order_id='o1',lot_id='lot',filled=charge('11'),source_ref='SYNTHETIC:overfill')
        self.assertEqual((w.cash,w.available_cash,w.assets,w.reservations),before)
        w.record_fill(event_id='f',order_id='o1',lot_id='lot',filled=charge(),source_ref='SYNTHETIC:fill')
        self.assertEqual(w.cash,D('90'))
        with self.assertRaises(ContractError):
            w.record_fill(event_id='f',order_id='o1',lot_id='lot',filled=charge(),source_ref='SYNTHETIC:duplicate-fill')
        self.assertEqual(w.cash,D('90'))
        self.assertEqual(w.cash,w.seed_cash+sum((w.round_cash(f'r{i}') for i in range(1,20)),D('0')))

if __name__ == '__main__':
    unittest.main()
