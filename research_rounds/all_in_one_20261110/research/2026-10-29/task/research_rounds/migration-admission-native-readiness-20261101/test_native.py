"""Actual native ledger callbacks, not Contract.fill/sell simulations."""
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import timedelta
import unittest, json, time, copy, tempfile
import native_adapter as N
J=N.J; D=J.D; O=N.O
F=J.W.load('native_readiness_authoritative_fixtures', J.O/'test_bridge.py')
T=F.T; BASE=F.BASE; DETAIL=[]

def account(decoupled=True):
    return N.enable(F.account(),decoupled=decoupled)

def win(i,x,**kwargs):
    kwargs.setdefault('eid',i.get('CP1_id') or i.get('budget_order') or 'core-native-window')
    return F.win(i,x,**kwargs)

def route(a,i,sector='S',raw=10):
    x,why=J.LR.preview(i,D(raw),a.fixture_state['factor'],T.RULE,T.MINIMUM)
    if why:return x,None,why
    at=i['clock'].earliest_execution_at;a.sync(at)
    a.current_nav=a.balance(at,a.market.marks(at,a.positions))['nav']
    fn=N.decoupled_route if type(a.budget) is N.DecoupledBudget else N.BASE.Runner.route
    r,why=fn(NS(sector_by_sid={i['sid']:sector}),a,i,x,at)
    return x,r,why

def buy(a,i,sector='S'):
    x,r,why=route(a,i,sector);assert not why,why
    F.reserve(a,i,x,r);f=a.fill_buy(i['sid'],win(i,x));assert f and f.shares==r[0]
    return x,r,f

def snapshot(a):
    return dict(cash=str(a.available),nav=a.budget.nav,resources=a.budget.resources(),
                lots=[(x.batch,x.stock,x.pool,x.role,x.qty,x.cost,x.floor,x.attempt) for x in a.budget.lots],
                orders=[(x.oid,x.stock,x.pool,x.role,x.qty,x.limit,x.status) for x in a.budget.orders.values()],
                consumed=sorted(a.budget.consumed),loss=a.budget.shared_loss)

def pending(a):
    i=F.intent(rid='old-probe');i.update(kind='core',role='core',CP1_id=None,CP1_trace=None,budget=D(4002),cap=400,risk_budget=D(2500))
    x,r,why=route(a,i);assert not why;assert r==(400,'probe')
    F.reserve(a,i,x,r)
    F.progress(a,'S',i['clock'].earliest_execution_at,'industry-second')
    bo=a.budget.orders[i['budget_order']];assert bo.status=='cancel_pending'
    return i,x,r,bo

class NativeTests(unittest.TestCase):
    def test_static_minimal_source_diff_and_unchanged_execution(self):
        self.assertTrue(N.static_contract()['passed'])
        for cls in (N.CoupledRunner,N.DecoupledRunner):
            self.assertIs(cls.opening,J.Runner.opening);self.assertIs(cls.planning,J.Runner.planning)

    def test_pending_probe_kept_while_different_stock_confirmed_real_fill(self):
        a=account();i,x,r,bo=pending(a);old=(bo.qty,bo.limit,bo.floor,bo.pool,a.buys['A'].remaining_shares)
        reserve_before=a.budget.resources('probe')[2]
        j=F.intent(rid='new-different-stock',sid='B');y,s,why=route(a,j)
        self.assertIsNone(why);self.assertEqual(s[1],'confirmed');F.reserve(a,j,y,s)
        self.assertEqual(old,(bo.qty,bo.limit,bo.floor,bo.pool,a.buys['A'].remaining_shares))
        self.assertEqual(a.budget.resources('probe')[2],reserve_before)
        f=a.fill_buy('B',win(j,y));self.assertIsNotNone(f)
        self.assertIn('new-different-stock',a.budget.consumed)
        self.assertEqual(a.budget.orders[j['budget_order']].status,'filled')
        self.assertEqual(bo.status,'cancel_pending');a.assert_budget_view(f.at)
        DETAIL.append(dict(case='old_pending_new_confirmed',old_pending=old,new_fill=f.shares,
                           new_pool=s[1],native_journal=J.W.canon(a.journal)))

    def test_coupled_mode_keeps_old_gate_and_no_speculative_consume(self):
        a=account(False);pending(a)
        j=F.intent(rid='coupled-test',sid='B');y,s,why=route(a,j)
        # A small probe may remain possible; confirmed is unavailable in coupled mode.
        self.assertTrue(s is None or s[1]=='probe')
        if s is None:self.assertNotIn('coupled-test',a.budget.consumed)

    def test_cancel_request_does_not_release_until_native_ack(self):
        a=account();i,x,r,bo=pending(a);before=(a.available,a.budget.resources('probe')[2])
        a.budget.cancel(i['budget_order'])
        self.assertEqual(before,(a.available,a.budget.resources('probe')[2]))
        a.cancel_buy('A');a.sync(i['clock'].earliest_execution_at)
        self.assertEqual(bo.status,'cancelled');self.assertEqual(bo.qty,0)
        self.assertEqual(a.budget.resources('probe')[2],0);self.assertGreater(a.available,before[0])

    def test_late_partial_fill_then_ack_and_later_legal_migration(self):
        a=account();i,x,r,bo=pending(a);at=i['clock'].earliest_execution_at
        f=a.fill_buy('A',win(i,x,capacity=100));self.assertEqual(f.shares,100)
        self.assertEqual(bo.qty,300);self.assertEqual(bo.status,'cancel_pending')
        self.assertEqual(a.budget.lots[0].pool,'probe');self.assertFalse(a.budget.migrate('S'))
        before=(a.available,a.budget.nav,a.budget.shared_loss)
        a.cancel_buy('A');a.sync(at)
        self.assertEqual(a.quantity('A'),100);self.assertEqual(a.budget.lots[0].pool,'confirmed')
        self.assertEqual(a.budget.lots[0].role,'core');self.assertEqual(a.budget.shared_loss,before[2])
        F.journal_bridge(a,at)

    def test_full_fill_wins_cancel_race_once_and_preserves_role(self):
        a=account();i,x,r,bo=pending(a);a.fill_buy('A',win(i,x))
        self.assertEqual(a.quantity('A'),400);self.assertEqual(bo.qty,0)
        self.assertEqual(a.budget.lots[0].pool,'confirmed');self.assertEqual(a.budget.lots[0].role,'core')
        before=snapshot(a);a.budget.cancel_ack(i['budget_order']);a.pools_from_model()
        self.assertEqual(before,snapshot(a))

    def test_real_partial_fee_is_incremental_one_order_minimum(self):
        a=account();F.progress(a,'S',BASE,'confirm')
        i=F.intent(rid='partial');i.update(budget=D(4002),cap=400)
        x,r,why=route(a,i);self.assertIsNone(why);F.reserve(a,i,x,r);at=i['clock'].earliest_execution_at
        f=a.fill_buy('A',win(i,x,capacity=100));self.assertEqual(f.fees_cny,D(5))
        f2=a.fill_buy('A',win(i,x,capacity=100,at=at+timedelta(days=1),eid='partial-two'))
        self.assertEqual(f2.fees_cny,D(0));self.assertEqual(a.fees_cny,D(5))
        a.cancel_buy('A');a.sync(at+timedelta(days=1));self.assertEqual(a.quantity('A'),200)
        F.journal_bridge(a,at+timedelta(days=1))

    def test_native_tplus1_actual_inventory_no_same_day_sell(self):
        a=account();F.progress(a,'S',BASE,'confirm');i=F.intent();x,r,f=buy(a,i)
        at=f.at;clock=T.admission.Clock(at+timedelta(minutes=1),at+timedelta(minutes=2),at.date())
        a.sell('A',clock,T.quote(),[z['id'] for z in a.live('A')],'native_T1_fixture')
        same_session=at+timedelta(minutes=2)
        w=T.window(sid='A',price=10,at=same_session,fees=T.MINIMUM,eid='same-day-sell',cash_due_at=same_session)
        self.assertIsNone(a.fill_exit('A',w));self.assertEqual(a.quantity('A'),r[0])
        later=at+timedelta(days=1)
        f2=a.fill_exit('A',T.window(sid='A',price=10,at=later,fees=T.MINIMUM,eid='T1-sell',cash_due_at=later))
        self.assertIsNotNone(f2);self.assertEqual(a.quantity('A'),0);a.settle_due(later);a.sync(later)
        F.journal_bridge(a,later)

    def test_partial_pending_split_fill_cancel_same_units_no_receipt_reissue(self):
        a=account();i,x,r,bo=pending(a);at=i['clock'].earliest_execution_at
        a.fill_buy('A',win(i,x,capacity=100));before=(a.available,a.budget.nav,a.budget.resources()[2],a.fees_cny,set(a.budget.consumed))
        a.split(event_id='partial-native-split',sid='A',ratio=D(2),at=at,new_shares_sellable_at=at+timedelta(days=1))
        a.fixture_state.update(price=D(5),factor=D(2));a.sync(at)
        self.assertEqual(a.quantity('A'),200);self.assertEqual(bo.qty,600)
        self.assertAlmostEqual(bo.limit,float(x['price']/2));self.assertAlmostEqual(bo.floor,4.95)
        self.assertEqual(a.available,before[0]);self.assertAlmostEqual(a.budget.nav,before[1]);self.assertAlmostEqual(a.budget.resources()[2],before[2])
        a.fill_buy('A',win(i,x,capacity=100,at=at+timedelta(days=1),price=x['price']/2,raw=5,eid='split-partial'))
        a.cancel_buy('A');a.sync(at+timedelta(days=1));self.assertEqual(a.quantity('A'),300)
        self.assertEqual(a.fees_cny,before[3]);self.assertEqual(set(a.budget.consumed),before[4]);F.journal_bridge(a,at+timedelta(days=1))

    def test_whole_transfer_capacity_fail_smaller_new_order_and_later_native_sale(self):
        a=account();F.legacy(a,'OTHER','X',59000,pool='confirmed');F.legacy(a,'OLD','S',1900,pool='probe')
        F.progress(a,'S',BASE,'S-confirm');self.assertFalse(a.budget.migrate('S'))
        before=a.budget.resources('probe')[0];remaining=.60*a.budget.nav-a.budget.resources('confirmed')[0]
        j=F.intent(rid='small-new',sid='B');j.update(budget=D(5010),cap=500)
        x,r,why=route(a,j);self.assertIsNone(why);self.assertEqual(r[1],'confirmed')
        F.reserve(a,j,x,r);a.fill_buy('B',win(j,x));self.assertEqual(a.budget.resources('probe')[0],before)
        self.assertFalse(a.budget.migrate('S'));later_remaining=.60*a.budget.nav-a.budget.resources('confirmed')[0]
        f=F.sell(a,'OTHER',BASE+timedelta(days=2));a.settle_due(f.at);a.sync(f.at)
        snapshot_before=(a.available,a.budget.nav,a.budget.resources(),a.budget.shared_loss)
        self.assertTrue(a.budget.migrate('S'));a.pools_from_model()
        self.assertEqual(snapshot_before,(a.available,a.budget.nav,a.budget.resources(),a.budget.shared_loss))
        self.assertTrue(all(z.pool=='confirmed' for z in a.budget.lots if z.stock=='OLD'))
        DETAIL.append(dict(case='whole_transfer_priority',old_probe=before,remaining_before_new=remaining,
                           new_actual_gross=float(x['price']*r[0]),remaining_after_new=later_remaining,
                           later_real_sale=float(f.gross_cny),later_migration=True))

    def test_combined_sector_and_pool_caps_still_block_and_old_probes_count(self):
        a=account();F.legacy(a,'OLD','S',9900,pool='confirmed');F.legacy(a,'P','S',100,pool='probe')
        F.progress(a,'S',BASE,'confirm');j=F.intent(rid='sector-full',sid='B')
        _,r,why=route(a,j);self.assertIsNone(r);self.assertIn('sector_capital',why);self.assertNotIn(j['CP1_id'],a.budget.consumed)
        b=account();F.legacy(b,'OLD-X','X',31000,pool='confirmed');F.legacy(b,'OLD-Y','Y',29000,pool='confirmed')
        F.progress(b,'S',BASE,'confirm');j=F.intent(rid='pool-full',sid='B')
        _,r,why=route(b,j);self.assertTrue(r is None or r[1]=='probe')

    def test_native_clean_exit_fresh_reentry_old_receipt_not_reusable(self):
        a=account();F.progress(a,'S',BASE,'confirm');i=F.intent(rid='once');x,r,f=buy(a,i)
        sf=F.sell(a,'A',BASE+timedelta(days=2));a.settle_due(sf.at);a.sync(sf.at)
        stale=F.intent(at=BASE+timedelta(days=4),rid='once');_,r,why=route(a,stale)
        self.assertIsNone(r);self.assertEqual(why,'no_fresh_stock_CP1')
        fresh=F.intent(at=BASE+timedelta(days=4),rid='genuine-new');a.core_epoch['A']=fresh['epoch']
        _,r,_=buy(a,fresh);self.assertIsNotNone(r);self.assertEqual(a.jmeta[a.layers[-1]['id']]['role'],'mobile')

    def test_exit_request_and_unsettled_proceeds_not_spendable_until_real_settlement(self):
        a=account();F.progress(a,'S',BASE,'confirm');F.legacy(a,'OLD','X',90000,pool='confirmed')
        clock=T.admission.Clock(BASE+timedelta(days=1),BASE+timedelta(days=2),(BASE+timedelta(days=1)).date())
        a.sell('OLD',clock,T.quote(sid='OLD'),[z['id'] for z in a.live('OLD')],'native_settlement_fixture')
        before=a.available;resources=a.budget.resources()
        i=F.intent(at=BASE+timedelta(days=1),rid='before-real-sale');_,r,why=route(a,i)
        self.assertIsNone(r);self.assertEqual(a.available,before);self.assertEqual(a.budget.resources(),resources)
        due=BASE+timedelta(days=5)
        fill=a.fill_exit('OLD',T.window(sid='OLD',at=clock.earliest_execution_at,price=10,fees=T.MINIMUM,eid='native-delayed-cash',cash_due_at=due))
        self.assertIsNotNone(fill);a.sync(fill.at);self.assertEqual(a.available,before)
        self.assertGreater(a.budget.receivable_equity,0)
        i=F.intent(at=BASE+timedelta(days=3),rid='unsettled-cannot-spend');_,r,why=route(a,i)
        self.assertIsNone(r);self.assertIn('cash',why)
        a.settle_due(due);a.sync(due)
        i=F.intent(at=due,rid='settled-fresh');x,r,why=route(a,i)
        self.assertIsNone(why);F.reserve(a,i,x,r);a.assert_budget_view(i['clock'].earliest_execution_at)
        DETAIL.append(dict(case='native_settlement',cash_before=str(before),sale_gross=str(fill.gross_cny),cash_after_settlement=str(a.available),fresh_reserved=r))

    def test_no_order_failed_candidate_retains_previous_legal_migration_reservation(self):
        a=account();F.legacy(a,'OLD','S',1000,pool='probe');F.progress(a,'S',BASE,'confirm')
        first=F.intent(rid='admitted',sid='B');x,r,_=route(a,first);F.reserve(a,first,x,r);before=snapshot(a)
        bad=F.intent(rid='not-affordable',sid='C');bad.update(budget=D(100),cap=10)
        _,r,why=route(a,bad);self.assertIsNone(r);self.assertIsNotNone(why)
        self.assertEqual(before,snapshot(a));self.assertTrue(all(z.pool=='confirmed' for z in a.budget.lots if z.stock=='OLD'))

    def test_corrupt_budget_representation_still_fails(self):
        a=account();i,x,r,bo=pending(a);bo.limit+=123/bo.qty
        with self.assertRaises(AssertionError):a.sync(i['clock'].earliest_execution_at)

    def test_decoupled_native_partial_pending_checkpoint_policy_identity(self):
        a=account();i,x,r,bo=pending(a);at=i['clock'].earliest_execution_at
        a.fill_buy('A',win(i,x,capacity=100))
        def pair(account):
            p=N.DecoupledRunner.__new__(N.DecoupledRunner)
            p.accounts={'B':account};p.integration_policy=p.policy_mode;p.source_freeze=N.source_freeze()
            return p
        p=pair(a);p.assert_native_wiring();before=snapshot(a)
        with tempfile.TemporaryDirectory(prefix='native-MD1-checkpoint-',dir='/tmp') as tmp:
            root=Path(tmp)
            with N.IO.atomic_runner_outputs(p,N.BASE.L,root,canonicalize=J.W.canon):p.checkpoint(root,at)
            restored=pair(account())
            with N.IO.atomic_runner_outputs(restored,N.BASE.L,root/'restore',canonicalize=J.W.canon):
                self.assertEqual(restored.restore(root/'checkpoint.pkl'),at)
            self.assertEqual(snapshot(restored.accounts['B']),before)
            self.assertEqual(restored.accounts['B'].budget.orders[i['budget_order']].status,'cancel_pending')
            restored.accounts['B'].cancel_buy('A');restored.accounts['B'].sync(at)
            self.assertEqual(restored.accounts['B'].quantity('A'),100)
            self.assertEqual(restored.accounts['B'].budget.lots[0].pool,'confirmed')
            wrong=N.CoupledRunner.__new__(N.CoupledRunner);wrong.accounts={'B':account(False)}
            wrong.integration_policy=wrong.policy_mode;wrong.source_freeze=N.source_freeze()
            with self.assertRaises(ValueError):
                with N.IO.atomic_runner_outputs(wrong,N.BASE.L,root/'wrong',canonicalize=J.W.canon):wrong.restore(root/'checkpoint.pkl')
            DETAIL.append(dict(case='native_partial_checkpoint',generation_identity=json.loads((root/'checkpoint.provenance.json').read_text())['engine_identity'],partial_pending_state_exact=True,real_cancel_after_restore=True,wrong_policy_rejected=True))

if __name__=='__main__':
    t=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeTests))
    N.IO.write_json(O/'NATIVE_GATE.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),seconds=time.monotonic()-t,details=DETAIL,native_execution_callbacks=True,budget_synthetic_fill_or_sell_used=False,new_historical_policy_paths=0),encoder=J.C.encoded)
    raise SystemExit(not result.wasSuccessful())
