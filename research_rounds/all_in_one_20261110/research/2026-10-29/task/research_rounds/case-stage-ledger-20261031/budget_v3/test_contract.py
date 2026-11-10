"""New v3 semantics and re-executed arithmetic regressions; no v2 result reuse."""
import json
import unittest
from pathlib import Path
from model import Contract, Evidence, Lot


def itoken(eid, day, sector='S', epoch='E'):
    return Evidence(eid, sector, 'industry_cp1', '21', max(0,day-1), day, day, epoch)


def stoken(m, eid, day, symbol='A', sector='S'):
    s=m.sectors[sector]
    return Evidence(eid, sector, 'stock_cp1', '21', max(0,day-1), day, day,
                    s.episode, symbol, s.attempt)


class V3Tests(unittest.TestCase):
    def fresh(self):
        m=Contract(exhausted_policy='record_only',shared_loss_budget=1)
        m.start('S','E',0)
        return m

    def progress(self,m,day,sector='S',eid=None):
        return m.industry(itoken(eid or f'{sector}-i{day}',day,sector,m.sectors[sector].episode),day)

    def buy(self,m,oid,day,qty=2,symbol='A',sector='S',**kwargs):
        return m.request(oid,symbol,sector,qty,10,9.9,stoken(m,oid+'-cp1',day,symbol,sector),
                         day,role='mobile',**kwargs)

    def test_industry_changes_stage_not_cash_orders_or_cumulative_credit(self):
        m=self.fresh()
        before=(m.cash,m.nav,m.resources())
        for day,level in [(1,0),(2,1),(3,2),(4,2)]:
            self.progress(m,day)
            self.assertEqual(m.sectors['S'].level,level)
            self.assertEqual(before,(m.cash,m.nav,m.resources()))
            self.assertEqual(len(m.orders),0)
        self.assertFalse(hasattr(m,'grants'))
        with self.assertRaises(TypeError):
            m.industry(itoken('old-api',5),5,grant_id='old-api')
        with self.assertRaises(TypeError):
            m.request('old-api','A','S',1,10,9.9,grant_id='old-api')

    def test_other_sectors_actual_sale_releases_capacity_for_still_valid_sector(self):
        lots=[Lot(f'other{i}',f'O{i}',f'OTHER{i}','old','confirmed',20,10,9.999) for i in range(3)]
        m=Contract(nav=1000,cash=400,prices={f'O{i}':10 for i in range(3)},lots=lots)
        m.start('S','E',0)
        self.progress(m,1);self.progress(m,2)
        self.assertEqual(self.buy(m,'before-sale',2,qty=10),'pool_capital')
        self.assertEqual(m.cash,400)
        self.assertEqual(len(m.orders),0)
        for i in range(3): m.sell(f'other{i}',20,10)
        self.assertEqual(m.cash,1000)
        self.assertEqual(m.sectors['S'].level,1)
        self.assertEqual(self.buy(m,'after-sale-fresh',3,qty=10),'reserved')
        self.assertEqual(m.resources()[2],100)
        m.fill('after-sale-fresh',10,10)
        self.assertEqual(m.resources('confirmed')[0],100)

    def test_same_sector_can_reinvest_actual_sale_with_fresh_signal_without_turnover_coupon(self):
        m=self.fresh()
        self.progress(m,1);self.progress(m,2)
        self.assertEqual(self.buy(m,'wrong',3,qty=10),'reserved')
        m.fill('wrong',10,10)
        m.sell('wrong',10,9)
        self.assertEqual(m.cash,990)
        duplicate=stoken(m,'wrong-cp1',4,'WRONG')
        self.assertEqual(m.request('renamed','WRONG','S',1,10,9.9,duplicate,4,role='mobile'),'no_fresh_stock_signal')
        self.assertEqual(self.buy(m,'fresh-better',4,qty=9,symbol='BETTER'),'reserved')
        m.fill('fresh-better',9,10)
        m.sell('fresh-better',9,9)
        self.assertEqual(self.buy(m,'third-fresh',5,qty=9,symbol='THIRD'),'reserved')
        m.fill('third-fresh',9,10)
        self.assertEqual(m.sectors['S'].last_evidence_time,2)
        self.assertEqual(m.shared_loss,19)
        self.assertGreater(100+90+90,.10*1000)  # Turnover exceeds capacity without simultaneous over-allocation.
        self.assertLessEqual(m.resources(sector='S')[0],.10*m.nav)

    def test_same_cash_requests_serialized_once_both_orders_no_expected_sale_credit(self):
        for sequence in [list(range(6)),list(reversed(range(6)))]:
            # Explicit passive legacy over-probe-cap holding. No new probe is admitted.
            lots=[Lot('legacy','OLD','LEGACY','old','probe',10,1,9.99)]
            m=Contract(nav=200,cash=100,prices={'OLD':10},lots=lots)
            accepted=[]
            for i in sequence:
                sector=f'S{i}'
                m.start(sector,'E',0)
                self.progress(m,1,sector);self.progress(m,2,sector)
                answer=self.buy(m,f'buy{i}',3,symbol=f'A{i}',sector=sector)
                if answer=='reserved': accepted.append(i)
                else: self.assertEqual(answer,'cash')
            self.assertEqual(accepted,sequence[:5])
            self.assertEqual(m.cash,100)
            self.assertEqual(m.resources()[2],100)
            self.assertEqual(m.cash-m.resources()[2],0)
            # Only an actual sell fill releases money, not confirmation or intent.
            m.sell('legacy',10,10)
            self.assertEqual(m.cash,200)
            last=sequence[-1]
            self.assertEqual(self.buy(m,'fresh-after-actual-sale',4,symbol=f'A{last}',sector=f'S{last}'),'reserved')
            self.assertEqual(m.resources()[2],120)
            self.assertLessEqual(m.resources('confirmed')[0],.60*m.nav)

    def test_receipt_cannot_be_reused_by_oid_pool_role_or_attempt_alias(self):
        m=self.fresh()
        self.progress(m,1)
        receipt=stoken(m,'canonical',2)
        self.assertEqual(m.request('probe-mobile','A','S',1,10,9.9,receipt,2,probe_request=True,
                                   role='mobile',core_epoch_locked=True),'reserved')
        m.fill('probe-mobile',1,10)
        m.sell('probe-mobile',1,10)
        self.progress(m,3)
        alias=stoken(m,'canonical',3)
        self.assertEqual(m.request('confirmed-new-oid','A','S',1,10,9.9,alias,3,role='mobile'),'no_fresh_stock_signal')
        self.assertEqual(m.request('renamed-core-confirmed','A','S',3,10,9.9,alias,3,role='core'),'mobile_role_required')
        m.observe('S',4,failure=True)
        self.progress(m,5)
        same_underlying_new_attempt=stoken(m,'canonical',6)
        self.assertEqual(m.request('attempt-alias','A','S',1,10,9.9,same_underlying_new_attempt,6,
                                   probe_request=True,role='mobile'),'no_fresh_stock_signal')
        self.assertEqual(self.buy(m,'genuine-new',6,probe_request=True,core_epoch_locked=True),'reserved')

    def test_failure_preserves_old_lots_pending_and_late_fill_without_reauthorization(self):
        m=self.fresh()
        self.progress(m,1);self.progress(m,2)
        self.buy(m,'pending',2,qty=4,order_expiry_bar=6)
        m.fill('pending',1,10)
        old_attempt=m.lots[0].attempt
        before=(m.cash,m.nav,m.resources(),[(x.batch,x.role,x.pool,x.cost,x.floor,x.attempt) for x in m.lots])
        m.observe('S',3,failure=True,token=itoken('same-observation',3))
        self.assertEqual(before,(m.cash,m.nav,m.resources(),[(x.batch,x.role,x.pool,x.cost,x.floor,x.attempt) for x in m.lots]))
        self.assertEqual(m.orders['pending'].status,'cancel_pending')
        self.assertEqual(self.buy(m,'not-allowed',4),'industry_invalidated')
        m.fill('pending',1,10,execution_bar=4)
        self.assertFalse(m.sectors['S'].active)
        self.assertTrue(all(x.attempt==old_attempt for x in m.lots))
        self.assertEqual(m.resources()[2],20)
        m.cancel_ack('pending')
        self.assertEqual(m.resources()[2],0)
        self.progress(m,5)
        self.assertEqual(m.sectors['S'].level,0)
        self.assertIn('sector_capital',m.request('new-probe','N','S',1,10,9.9,bar=5,probe_request=True))

    def test_multiple_failures_record_loss_across_attempts_and_episode_without_ban(self):
        m=self.fresh()
        self.progress(m,1)
        self.assertEqual(self.buy(m,'first',2,qty=1,probe_request=True),'reserved')
        m.fill('first',1,10);m.sell('first',1,8)
        first_attempt=m.sectors['S'].attempt
        m.observe('S',3,failure=True)
        self.progress(m,4)
        self.assertNotEqual(m.sectors['S'].attempt,first_attempt)
        self.assertEqual(self.buy(m,'second',5,qty=1,probe_request=True),'reserved')
        m.fill('second',1,10);m.sell('second',1,8)
        self.assertEqual(m.shared_loss,4)
        self.assertEqual(m.losses[('S','E')],4)
        m.start('S','E2',6)
        self.progress(m,7)
        self.assertEqual(self.buy(m,'third',8,qty=1,probe_request=True),'reserved')
        self.assertEqual(m.shared_loss,4)
        self.assertGreater(m.shared_loss,m.loss_budget)

    def test_probe_cap_is_total_sector_across_pool_migration_and_shared_across_sectors(self):
        m=self.fresh()
        self.progress(m,1)
        m.request('core','A','S',2,10,9.999,bar=1,probe_request=True)
        m.fill('core',2,10)
        before=(m.cash,m.nav,m.resources(),m.shared_loss)
        self.progress(m,2)
        self.assertEqual(before,(m.cash,m.nav,m.resources(),m.shared_loss))
        self.assertEqual(m.lots[0].pool,'confirmed')
        self.assertEqual(m.lots[0].role,'core')
        self.assertIn('sector_capital',m.request('fresh-core','B','S',1,10,9.999,bar=2,probe_request=True))
        for i in range(90):
            sector=f'T{i}'
            m.start(sector,'E',0)
            self.progress(m,1,sector)
            m.request(f'p{i}',sector,sector,2,10,9.999,bar=1,probe_request=True)
        self.assertEqual(m.resources('probe')[0],100)
        self.assertEqual(m.resources('confirmed')[0],20)

    def test_industry_receipt_before_episode_start_cannot_create_attempt(self):
        m=Contract()
        m.start('S','E',100)
        self.assertEqual(m.industry(itoken('pre-episode',1),100),'rejected')
        self.assertFalse(m.sectors['S'].active)
        self.assertEqual(m.sectors['S'].episode_started,100)
        self.assertEqual(m.request('blocked','A','S',1,10,9.9,bar=100,probe_request=True),'industry_invalidated')

    def test_late_first_industry_receipt_is_audit_only_not_probe_permission(self):
        m=self.fresh()
        self.assertEqual(m.industry(itoken('late-first',1),100),'late_evidence_audit_only')
        self.assertFalse(m.sectors['S'].active)
        self.assertEqual(m.request('blocked','A','S',1,10,9.9,bar=100,probe_request=True),'industry_invalidated')
        self.progress(m,100)
        self.assertEqual(m.sectors['S'].started,100)
        self.assertEqual(m.sectors['S'].episode_started,0)

    def test_known_fee_cap_and_migration_nav_conservation_regression(self):
        m=self.fresh()
        self.progress(m,1)
        self.assertIn('sector_capital',m.request('exact','A','S',2,10,9.9,bar=1,probe_request=True,fee_per_share=.1))
        self.assertEqual(m.request('under','A','S',1.99,10,9.9,bar=1,probe_request=True,fee_per_share=.1),'reserved')
        m.fill('under',1.99,10)
        self.assertLessEqual(m.resources(sector='S')[0],.02*m.nav)
        lots=[Lot('existing','C','OTHER','old','confirmed',1,580,579.9)]
        n=Contract(nav=1000,cash=420,prices={'C':580},lots=lots)
        n.start('S','E',0);self.progress(n,1)
        n.request('core','A','S',1,10,9.9,bar=1,probe_request=True)
        n.fill('core',1,10)
        n.start('T','E',0);self.progress(n,1,'T')
        self.assertEqual(n.request('fee','B','T',1,1,.99,bar=1,probe_request=True,fee_per_share=20),'reserved')
        before=(n.cash,n.nav,n.resources(),n.shared_loss)
        self.progress(n,2)
        self.assertEqual(n.sectors['S'].status,'confirmed_unfunded')
        self.assertEqual(before,(n.cash,n.nav,n.resources(),n.shared_loss))
        n.fill('fee',1,1)
        self.assertEqual(n.nav,980)
        self.assertEqual(n.resources('confirmed')[0],580)
        self.assertLessEqual(n.resources('confirmed')[0],.60*n.nav)

    def test_full_fill_wins_cancel_race_and_duplicate_ack_conservation_regression(self):
        m=self.fresh()
        self.progress(m,1)
        m.request('core','A','S',2,10,9.9,bar=1,probe_request=True,order_expiry_bar=2)
        self.progress(m,2)
        self.assertEqual(m.orders['core'].status,'cancel_pending')
        self.assertEqual(m.resources()[2],20)
        m.fill('core',2,10,execution_bar=2)
        self.assertEqual(m.lots[0].pool,'probe')
        before=(m.cash,m.nav,m.resources(),m.shared_loss)
        m.cancel_ack('core')
        m.cancel_ack('core')
        self.assertEqual(before,(m.cash,m.nav,m.resources(),m.shared_loss))
        self.assertEqual(m.lots[0].pool,'confirmed')
        self.assertEqual(m.lots[0].role,'core')

    def test_probe_core_mobile_share_total_two_percent_without_role_switch_credit(self):
        for roles in [('core','mobile'),('mobile','core')]:
            m=self.fresh()
            self.progress(m,1)
            for i,role in enumerate(roles):
                evidence=stoken(m,f'cp1-{i}',2,f'S{i}') if role=='mobile' else None
                self.assertEqual(m.request(f'o{i}',f'S{i}','S',1,10,9.9,evidence,2,
                                           probe_request=True,role=role),'reserved')
            self.assertEqual(m.resources(sector='S')[0],20)
            self.assertEqual(m.resources('probe')[0],20)
            for role in ('core','mobile'):
                evidence=stoken(m,f'extra-{role}',3,'EXTRA') if role=='mobile' else None
                self.assertIn('sector_capital',m.request(f'extra-{role}','EXTRA','S',.1,10,9.9,evidence,3,
                                                        probe_request=True,role=role))
            self.assertEqual(m.resources(sector='S')[0],20)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(V3Tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    payload={'version':'v3','semantics':'revolving live capacity; no cumulative turnover grant',
             'scope':'synthetic contract only, not historical returns or real engine admission',
             'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
             'passed':result.wasSuccessful(),'v2_15_results_are_not_v3_evidence':True,
             'external':['I eligibility','single-stock 10% and mobile-order 2% sizing',
                         'market protection and exit decisions','legal execution/clock','canonical receipts']}
    Path(__file__).with_name('results.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,indent=2))
    raise SystemExit(not result.wasSuccessful())
