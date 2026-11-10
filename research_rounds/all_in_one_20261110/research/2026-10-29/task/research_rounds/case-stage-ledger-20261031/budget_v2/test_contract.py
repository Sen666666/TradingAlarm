"""v2-only contract tests; v1's 31 results are preserved separately, not claimed here."""
import json
import unittest
from pathlib import Path
from model import Contract, Evidence, Lot


def itoken(eid, day, sector='S', epoch='E'):
    return Evidence(eid, sector, 'industry_cp1', '21', max(0, day-1), day, day, epoch)


def stoken(m, eid, day, symbol='A', sector='S'):
    s = m.sectors[sector]
    return Evidence(eid, sector, 'stock_cp1', '21', max(0,day-1), day, day,
                    s.episode, symbol, s.attempt)


class V2Tests(unittest.TestCase):
    def fresh(self):
        m = Contract(exhausted_policy='record_only', shared_loss_budget=1)
        m.start('S', 'E', 0)
        return m

    def progress(self, m, day, sector='S', eid=None):
        eid = eid or f'{sector}-i{day}'
        t = itoken(eid, day, sector, m.sectors[sector].episode)
        if not m.sectors[sector].active:
            return m.industry(t, day)
        return m.industry(t, day, grant_id=eid, grant_capital=1000, grant_risk=100,
                          decision_batch=f'{sector}-decision-{day}', decision_bar=day)

    def buy(self, m, oid, day, qty=2, symbol='A', gid='S-i2', **kwargs):
        return m.request(oid, symbol, 'S', qty, 10, 9.9,
                         stoken(m, oid+'-cp1', day, symbol), day,
                         role='mobile', grant_id=gid, **kwargs)

    def ledger(self, m, gid):
        g, u = m.grants[gid], m.grant_usage(gid)
        for dim, limit in [('capital',g.capital_limit), ('risk',g.risk_limit)]:
            values=[u[x+'_'+dim] for x in ('filled','pending','remaining','expired')]
            self.assertTrue(all(x >= -1e-8 for x in values))
            self.assertAlmostEqual(sum(values), limit)

    def test_first_second_third_industry_receipt_probe_confirmed_expanded(self):
        m=self.fresh()
        self.progress(m,1)
        self.assertEqual(m.sectors['S'].level,0)
        self.assertEqual(m.sectors['S'].status,'probe')
        self.assertEqual(len(m.grants),0)
        self.progress(m,2)
        self.assertEqual(m.sectors['S'].level,1)
        self.assertEqual(m.grants['S-i2'].capital_limit,100)
        self.progress(m,3)
        self.assertEqual(m.sectors['S'].level,2)
        self.progress(m,4)
        self.assertEqual(m.sectors['S'].level,2)
        self.assertEqual(m.industry(itoken('S-i4',4),5),'rejected')
        same_day=Evidence('same-day-other','S','industry_cp1','21',3,4,4,'E')
        self.assertEqual(m.industry(same_day,5),'not_new_progress')

    def test_failure_same_e0_new_attempt_probe_but_old_20percent_blocks_new_probe(self):
        m=self.fresh()
        self.progress(m,1)
        m.request('core','CORE','S',2,10,9.9,bar=1,probe_request=True)
        m.fill('core',2,10)
        old_attempt=m.sectors['S'].attempt
        self.progress(m,2)
        self.progress(m,3)
        for i in range(9):
            self.assertEqual(self.buy(m,f'm{i}',3,symbol=f'M{i}',gid='S-i3'),'reserved')
            m.fill(f'm{i}',2,10)
        self.assertEqual(m.resources(sector='S')[0],200)
        snapshot=(m.cash,m.nav,m.resources(),[(x.batch,x.pool,x.role,x.cost,x.attempt) for x in m.lots],m.shared_loss)
        self.assertEqual(m.observe('S',4,failure=True,token=itoken('failed-bar-cp1',4)),'invalidated')
        self.assertEqual(snapshot,(m.cash,m.nav,m.resources(),[(x.batch,x.pool,x.role,x.cost,x.attempt) for x in m.lots],m.shared_loss))
        self.assertEqual(m.industry(itoken('failed-bar-cp1',4),5),'not_new_progress')
        self.progress(m,5)
        self.assertEqual(m.sectors['S'].episode,'E')
        self.assertNotEqual(m.sectors['S'].attempt,old_attempt)
        self.assertEqual(m.sectors['S'].level,0)
        self.assertIn('sector_capital',m.request('new-core','NEW','S',1,10,9.9,bar=5,probe_request=True))
        self.assertEqual(m.resources(sector='S')[0],200)
        self.assertTrue(all(x.attempt==old_attempt for x in m.lots))

    def test_async_fresh_stock_receipts_use_fixed_attempt_grant_not_daily_nav(self):
        m=self.fresh()
        self.progress(m,1);self.progress(m,2)
        m.end_batch('S-decision-2')
        self.assertTrue(m.grants['S-i2'].active)
        self.assertEqual(self.buy(m,'a',4),'reserved')
        m.fill('a',2,10)
        m.prices['A']=10.5
        self.assertEqual(m.nav,1001)
        self.assertEqual(self.buy(m,'b',8,symbol='B'),'reserved')
        m.fill('b',2,10)
        self.assertEqual(m.grants['S-i2'].capital_limit,100)
        self.assertEqual(m.grant_usage('S-i2')['remaining_capital'],60)
        self.ledger(m,'S-i2')
        stale=stoken(m,'unused-old-stock',4,'C')
        self.assertEqual(m.request('stale','C','S',1,10,9.9,stale,9,role='mobile',grant_id='S-i2'),'no_fresh_stock_signal')

    def test_old_receipt_and_core_role_renaming_cannot_resurrect_or_expand(self):
        m=self.fresh()
        self.progress(m,1);self.progress(m,2)
        old_token=stoken(m,'old-unconsumed',3)
        self.progress(m,4)
        self.assertFalse(m.grants['S-i2'].active)
        self.assertEqual(self.buy(m,'use-old',5,gid='S-i2'),'no_current_grant')
        self.assertEqual(m.request('renamed','A','S',3,10,9.9,stoken(m,'renamed-cp1',5),5,role='core',grant_id='S-i4'),'mobile_role_required')
        self.assertIn('sector_capital',m.request('probe-name','B','S',3,10,9.9,bar=5,probe_request=True))
        self.assertEqual(m.request('old-stock','A','S',1,10,9.9,old_token,5,role='mobile',grant_id='S-i4'),'no_fresh_stock_signal')
        self.assertEqual(m.industry(itoken('S-i2',2),5),'rejected')

    def test_replacement_snapshot_counts_old_pending_and_late_partial_fill(self):
        m=self.fresh()
        self.progress(m,1);self.progress(m,2)
        self.assertEqual(self.buy(m,'old-order',2,qty=8,order_expiry_bar=10),'reserved')
        self.progress(m,3)
        self.assertEqual(m.grants['S-i3'].capital_limit,120)
        self.assertEqual(m.grant_usage('S-i2')['expired_capital'],20)
        self.assertEqual(m.grant_usage('S-i2')['pending_capital'],80)
        for i in range(6):
            self.assertEqual(self.buy(m,f'new{i}',3,symbol=f'N{i}',gid='S-i3'),'reserved')
        self.assertEqual(m.resources()[2],200)
        m.fill('old-order',2,10,execution_bar=4)
        self.assertEqual(m.resources()[0],200)
        self.assertEqual(m.resources()[2],180)
        m.cancel('old-order')
        self.assertEqual(m.resources()[2],180)
        m.cancel_ack('old-order')
        self.assertEqual(m.resources()[2],120)
        self.assertEqual(m.grants['S-i3'].capital_limit,120)
        self.assertEqual(self.buy(m,'no-refill',5,symbol='EXTRA',gid='S-i3'),'grant_exhausted')
        self.ledger(m,'S-i2');self.ledger(m,'S-i3')
        m.sell('old-order',2,9)
        self.assertEqual(m.grant_usage('S-i2')['filled_capital'],20)
        self.assertEqual(m.shared_loss,2)

    def test_first_mobile_and_fresh_reentry_without_core_ignore_core_epoch_lock(self):
        m=self.fresh()
        self.progress(m,1);self.progress(m,2)
        self.assertEqual(m.request('locked-core','A','S',1,10,9.9,bar=3,probe_request=True,core_epoch_locked=True),'core_epoch_locked')
        self.assertEqual(self.buy(m,'first',3,core_epoch_locked=True),'reserved')
        m.fill('first',2,10)
        self.assertTrue(all(x.role=='mobile' for x in m.lots))
        m.sell('first',2,9)
        self.assertEqual(len(m.lots),0)
        reused=stoken(m,'first-cp1',4)
        self.assertEqual(m.request('repeat','A','S',2,10,9.9,reused,4,role='mobile',grant_id='S-i2',core_epoch_locked=True),'no_fresh_stock_signal')
        self.assertEqual(self.buy(m,'reentry',4,core_epoch_locked=True),'reserved')
        m.fill('reentry',2,10)
        self.assertEqual(m.shared_loss,2)
        self.assertGreater(m.shared_loss,m.loss_budget)
        self.ledger(m,'S-i2')

    def test_failure_preserves_partial_lot_and_cancel_pending_then_new_attempt_counts_old(self):
        m=self.fresh()
        self.progress(m,1);self.progress(m,2)
        self.buy(m,'old',2,qty=4,order_expiry_bar=8)
        m.fill('old',1,10)
        old_attempt=m.lots[0].attempt
        snapshot=(m.cash,m.nav,m.resources(),m.lots[0].role,m.lots[0].pool,m.lots[0].cost)
        m.observe('S',3,failure=True)
        self.assertEqual(m.orders['old'].status,'cancel_pending')
        self.assertEqual(snapshot,(m.cash,m.nav,m.resources(),m.lots[0].role,m.lots[0].pool,m.lots[0].cost))
        self.progress(m,4)
        self.assertIn('sector_capital',m.request('probe','P','S',1,10,9.9,bar=4,probe_request=True))
        m.fill('old',1,10,execution_bar=4)
        m.cancel_ack('old')
        self.assertTrue(all(x.attempt==old_attempt and x.pool=='confirmed' for x in m.lots))
        self.assertEqual(m.resources(sector='S')[0],20)
        self.assertIn('sector_capital',m.request('probe2','P','S',1,10,9.9,bar=4,probe_request=True))
        old_attempt_stock=Evidence('old-stock','S','stock_cp1','21',3,4,4,'E','A',old_attempt)
        self.progress(m,5)
        self.assertEqual(m.request('old-attempt-stock','A','S',1,10,9.9,old_attempt_stock,5,role='mobile',grant_id='S-i5'),'no_fresh_stock_signal')
        self.ledger(m,'S-i2')

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

    def test_loss_record_preserved_across_attempt_and_episode_no_ban(self):
        m=self.fresh()
        self.progress(m,1)
        m.request('p','A','S',1,10,9.9,bar=1,probe_request=True,fee_per_share=.1)
        m.fill('p',1,10)
        m.sell('p',1,8,fee=.1)
        self.assertAlmostEqual(m.shared_loss,2.2)
        m.observe('S',2,failure=True)
        self.progress(m,3)
        self.assertAlmostEqual(m.shared_loss,2.2)
        m.start('S','E2',4)
        self.progress(m,5)
        self.assertEqual(m.request('new','B','S',1,10,9.9,bar=5,probe_request=True),'reserved')
        self.assertAlmostEqual(m.losses[('S','E')],2.2)
        self.assertAlmostEqual(m.shared_loss,2.2)

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

    def test_probe_mobile_first_reentry_ignores_core_lock_receipt_not_reusable_across_pools(self):
        m=self.fresh()
        self.progress(m,1)
        self.assertEqual(m.request('no-signal','A','S',1,10,9.9,bar=2,
                                   probe_request=True,role='mobile',core_epoch_locked=True),'no_fresh_stock_signal')
        first=stoken(m,'first-probe-mobile-cp1',2)
        self.assertEqual(m.request('first','A','S',1,10,9.9,first,2,
                                   probe_request=True,role='mobile',core_epoch_locked=True),'reserved')
        m.fill('first',1,10)
        m.sell('first',1,9)
        self.assertEqual(len(m.lots),0)
        self.progress(m,3)
        reentry=stoken(m,'reentry-probe-mobile-cp1',3)
        self.assertEqual(m.request('reentry','A','S',1,10,9.9,reentry,3,
                                   probe_request=True,role='mobile',core_epoch_locked=True),'reserved')
        m.fill('reentry',1,10)
        self.assertEqual(m.request('double-spend-confirmed','A','S',1,10,9.9,reentry,3,
                                   role='mobile',grant_id='S-i3',core_epoch_locked=True),'no_fresh_stock_signal')
        self.assertEqual(m.request('double-spend-probe','A','S',1,10,9.9,reentry,3,
                                   probe_request=True,role='mobile',core_epoch_locked=True),'no_fresh_stock_signal')
        self.assertTrue(all(x.role=='mobile' and x.pool=='probe' for x in m.lots))
        self.assertEqual(m.shared_loss,1)

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
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(V2Tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    payload={'version':'v2','scope':'pure synthetic attempt/grant/budget contract, no historical PnL',
             'revision':'probe-mobile equal-opportunity interface added after original 13-test review',
             'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
             'passed':result.wasSuccessful(),'v1_tests_not_claimed_as_v2':31,
             'remaining_external_inputs':['industry protection events','E0 episode identities',
               'canonical CP1 evidence and original core eligibility/lock','stock protection and exit decisions',
               'legal order execution deadlines','grant request maxima and actual execution inputs']}
    Path(__file__).with_name('results.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,indent=2))
    raise SystemExit(not result.wasSuccessful())
