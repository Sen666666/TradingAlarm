"""Generated native scenarios and saved-row arithmetic; ZERO historical events."""
from native_risk import *
import unittest, argparse, subprocess, time
from dataclasses import asdict
from datetime import timezone
sys.path.insert(0, str(BASE))
import test_native as H
from state_hash import full_state_hash

ROOT = HERE / 'runs'


def setup(*, enabled=True, price=99, floor=94, star=False, n=1, mode='C10', sectors=None):
    r = Runner(mode, keep_approved_risk=enabled)
    ss = H.fixtures(r, n=n, price=price, floor=floor, star=star, sector=sectors)
    H.close(r, 0, H.packet(r, ss, 0, core=False), {'G': H.obs(r, 'G', 0)})
    return r, ss


def mark(r, sid, p, at):
    a = r.account
    a.mark(sid, p, at, a.market.sectors[sid], a.market.stars[sid])


def key(r, sid):
    return r.risk.key(r.active['certificate_id'], sid)


def native_economy(r, at):
    a = r.account
    return dict(bridge=a.bridge(at), fills=[asdict(f) for f in a.fills], trades=a.trades,
                audit=a.audit_log, positions={s:asdict(p) for s,p in a.positions.items()},
                buys={s:asdict(o) for s,o in a.buys.items()}, exits={s:asdict(o) for s,o in a.exits.items()},
                layers=a.layers, fees=a.fees_cny, available=a.available,
                settlements={s:asdict(v) for s,v in a.settlements.items()},
                callbacks=a.native_callbacks, policy=a.policy.exported())


class Cases(unittest.TestCase):
    records = {}

    def keep(self, name, r, at, **extra):
        r.assert_observers()
        x = dict(state=r.observable(at), extra=extra, full_state_hash=full_state_hash(r))
        self.records[name] = x
        IO.write_json(ROOT / (name+'.json'), x, encoder=encode)

    def test01_off_same_native_event_stream_as_frozen_runner(self):
        frozen = M.Runner('C_BATCH20')
        off = Runner('C_BATCH20', keep_approved_risk=False)
        for r in (frozen, off):
            ss = H.fixtures(r, n=3)
            H.close(r, 0, H.packet(r, ss, 0), {'G':H.obs(r,'G',0)})
            mark(r, ss[0], 105, H.op(1))
            r.event(H.op(1), is_open=True)
            H.close(r, 1, H.packet(r, ss, 1, receipt=False, core=False), {})
        self.assertEqual(digest(native_economy(frozen,H.cl(1))), digest(native_economy(off,H.cl(1))))
        self.assertFalse(off.risk.approvals)
        self.keep('01_off_identity',off,H.cl(1), native_economic_stream_equal=True)

    def test02_no_gap_on_off_native_identity(self):
        states=[]
        for enabled in (False,True):
            r,ss=setup(enabled=enabled,n=3,sectors=lambda j:'S'+str(j),mode='C_BATCH20')
            r.event(H.op(1),is_open=True)
            states.append(digest(native_economy(r,H.op(1))))
            self.keep('02_no_gap_'+str(enabled),r,H.op(1))
        self.assertEqual(*states)

    def test03_real_price_floor_calibrated_gap_scenarios(self):
        # Actual prior audit p0/f0/open prices; synthetic one-stock cash state.
        rows=json.loads((HERE.parent/'g-s-C-approved-risk-execution-readonly-20261102/ALL_POSITIVE_C_AUTHORIZATIONS.json').read_text())['2025_26-C10']
        chosen=[('柳工','2025-07-22'),('徐工机械','2025-07-22'),('中联重科','2025-07-22'),('千方科技','2025-07-11'),('汇绿生态','2025-07-01'),('平安电工','2025-07-04'),('广生堂','2025-07-30')]
        summary=[]
        for name,day in chosen:
            xs=[x for x in rows if ''.join(x['name'].split())==name and x['signal_at'].startswith(day)]
            self.assertEqual(len(xs),1,(name,day))
            x=xs[0];actual=x['actual_order'];p0=D(x['decision_mark']);f0=D(x['decision_effective_floor']);p1=D(actual['reserved_price'])/(ONE+LR.SLIP)
            native=[]
            for enabled in (False,True):
                r,ss=setup(enabled=enabled,price=p0,floor=f0,star=x['sid'].startswith('688'))
                sid=ss[0];q0=r.active['Q'][sid];mark(r,sid,p1,H.op(1));r.event(H.op(1),is_open=True)
                q=r.account.quantity(sid);native.append(q)
                if enabled and q:
                    z=r.risk.approvals[key(r,sid)]
                    self.assertLessEqual(z['spent'],z['approved']['R0'])
                if enabled:self.keep('03_'+name,r,H.op(1),calibration_source=x['sid'],synthetic_Q0=q0,original_saved_Q0=x['approved_qty'],actual_saved_qty=actual['fill_qty'],synthetic_actual_qty=q)
            if name in ('柳工','徐工机械','平安电工','广生堂'):
                self.assertLess(native[1],native[0],(name,native))
            else:self.assertEqual(native[1],native[0],(name,native))
            summary.append(dict(name=name,fixture_off=native[0],fixture_on=native[1],historical_PnL_inferred=False))
        IO.write_json(ROOT/'03_PRICE_SCENARIOS.json',summary,encoder=encode)

    def test04_partial_same_R0_permanent_shrink_zero_fill_and_cancel(self):
        r,ss=setup(price=100,floor=95,star=True);sid=ss[0]
        r.event(H.op(1),is_open=True,capacities={sid:0});a=r.account;o=a.buys[sid];k=key(r,sid);q0=o.remaining_shares
        self.assertEqual(r.risk.approvals[k]['spent'],0)
        f=r.apply_window('buy',sid,H.win(r,sid,H.op(1)+timedelta(minutes=1),'buy',450,'partial450'))
        self.assertEqual(f.shares,450);spent=r.risk.approvals[k]['spent'];self.assertGreater(spent,0)
        mark(r,sid,110,H.op(1)+timedelta(minutes=2))
        r.apply_window('buy',sid,H.win(r,sid,H.op(1)+timedelta(minutes=2),'buy',50,'gap-partial50'))
        remaining=a.buys[sid].remaining_shares
        self.assertLess(remaining,q0-500);spent2=r.risk.approvals[k]['spent']
        mark(r,sid,100,H.op(1)+timedelta(minutes=3))
        r.apply_window('buy',sid,H.win(r,sid,H.op(1)+timedelta(minutes=3),'buy',0,'zero-after-shrink'))
        self.assertEqual(a.buys[sid].remaining_shares,remaining)
        self.assertEqual(r.risk.approvals[k]['spent'],spent2)
        cash=a.available;reserve=a.buys[sid].remaining_budget_cny+a.buys[sid].fee_reserved_cny
        a.request_buy_cancel(sid);self.assertEqual(a.available,cash)
        r.assert_observers();a.ack_buy_cancel(sid);self.assertEqual(a.available,cash+reserve)
        self.assertEqual(r.risk.approvals[k]['spent'],spent2)
        self.assertEqual(r.risk.approvals[k]['remaining'],0)
        i=r.active_intents[sid]
        with self.assertRaises(ValueError):a.submit_fixed(i,H.op(1)+timedelta(minutes=4),use='G',role='mobile',q=q0,cid=r.active['certificate_id'])
        self.keep('04_partial_no_refund',r,H.op(1)+timedelta(minutes=4),remaining_before_cancel=remaining,cash_pending_cancel=cash)

    def test05_actual_window_price_bounds_before_native_fill(self):
        r,ss=setup(price=100,floor=95,star=True);sid=ss[0]
        r.event(H.op(1),is_open=True,capacities={sid:0});a=r.account;before=a.buys[sid].remaining_shares
        # Same market preview, execution window at a different real known price.
        at=H.op(1)+timedelta(minutes=1)
        w=T.window(sid,D('110'),at,100000,fees=a.market.fees(sid,at),rule=a.market.quantity(sid,at),eid='real-price110',raw_open=D('109.95'),sellable_at=H.op(2),cash_due_at=at)
        f=r.apply_window('buy',sid,w)
        self.assertLess(f.shares,before)
        z=r.risk.approvals[key(r,sid)];self.assertLessEqual(z['spent'],z['approved']['R0'])
        cb=[x for x in a.native_callbacks if x['kind']=='amend_before_fill'][-1]
        self.assertLessEqual(f.shares,cb['q'])
        self.assertLessEqual(F(cb['q'])*(F(w.execution_price)-F(z['approved']['f0'])),z['approved']['R0'])
        self.keep('05_actual_window_price',r,at,pre_fill_atomic_qty=cb['q'],actual_price=w.execution_price)

    def test06_STAR_min200_retry_no_refund_partial50_legal(self):
        r,ss=setup(price=450,floor=440,star=True);sid=ss[0];mark(r,sid,500,H.op(1))
        r.event(H.op(1),is_open=True);a=r.account;z=r.risk.approvals[key(r,sid)]
        self.assertEqual(a.quantity(sid),0);self.assertEqual(z['remaining'],0);self.assertEqual(z['spent'],0)
        mark(r,sid,450,H.op(1)+timedelta(minutes=1));i=r.active_intents[sid]
        self.assertEqual(a.submit_fixed(i,H.op(1)+timedelta(minutes=1),use='G',role='mobile',q=r.active['Q'][sid],cid=r.active['certificate_id'])['q'],0)
        self.keep('06_STAR_new200_rejected',r,H.op(1)+timedelta(minutes=1))
        r,ss=setup(price=100,floor=95,star=True);sid=ss[0];r.event(H.op(1),is_open=True,capacities={sid:0});a=r.account;q=a.buys[sid].remaining_shares
        r.apply_window('buy',sid,H.win(r,sid,H.op(1)+timedelta(minutes=1),'buy',q-50,'STAR-first'))
        self.assertEqual(a.buys[sid].remaining_shares,50)
        f=r.apply_window('buy',sid,H.win(r,sid,H.op(1)+timedelta(minutes=2),'buy',50,'STAR-last50'))
        self.assertEqual(f.shares,50);self.keep('06_STAR_same_partial50',r,H.op(1)+timedelta(minutes=2))

    def test07_split_pending_partial_currency_R0_unchanged(self):
        r,ss=setup(price=100,floor=95,star=True);sid=ss[0];r.event(H.op(1),is_open=True,capacities={sid:0});a=r.account;q=a.buys[sid].remaining_shares;k=key(r,sid)
        r.apply_window('buy',sid,H.win(r,sid,H.op(1)+timedelta(minutes=1),'buy',q-50,'before-split'))
        R0=r.risk.approvals[k]['approved']['R0'];spent=r.risk.approvals[k]['spent'];at=H.op(1)+timedelta(minutes=2)
        kw=dict(event_id='risk-split2',sid=sid,ratio=D(2),at=at,new_shares_sellable_at=H.op(2));r.event(at,actions=[kw]);self.assertEqual(a.buys[sid].remaining_shares,100)
        self.assertEqual(r.risk.approvals[k]['approved']['R0'],R0);self.assertEqual(r.risk.approvals[k]['spent'],spent)
        f=r.apply_window('buy',sid,H.win(r,sid,at+timedelta(minutes=1),'buy',100,'after-split'))
        self.assertEqual(f.shares,100);self.assertEqual(a.quantity(sid),2*q)
        self.assertEqual(r.risk.approvals[k]['spent'],R0)
        self.keep('07_split_same_currency',r,at+timedelta(minutes=1))

    def test08_core_and_T_not_assigned_fictional_R0(self):
        for core in (False,True):
            r=Runner();ss=H.fixtures(r,1,price=50,floor=10,sector='S');rows=H.packet(r,ss,0,core=core);rows[ss[0]]['cp_floor']=D('49.8')
            H.close(r,0,rows,{'S':H.obs(r,'S',0)});r.event(H.op(1),is_open=True)
            self.assertFalse(r.risk.approvals);self.assertEqual(len(r.account.layers),1)
            self.assertEqual(next(iter(r.account.capital_meta.values()))['purpose'],'T')
            self.keep('08_T_'+str(core),r,H.op(1))
        r=Runner();ss=H.fixtures(r,1,price=20,floor=19,sector='S');H.close(r,0,H.packet(r,ss,0),{'S':H.obs(r,'S',0)})
        r.event(H.op(1),is_open=True,capacities={ss[0]:0});o=r.account.buys[ss[0]]
        self.assertEqual(r.account.supports[o.order_id]['role'],'core');self.assertFalse(r.risk.orders);self.assertFalse(r.account.policy.consumed)
        self.keep('08_core_zero_fill',r,H.op(1))

    def test09_early_shrink_releases_for_later_original_C_candidates(self):
        by=[]
        for enabled in (False,True):
            r,ss=setup(enabled=enabled,n=4,price=99,floor=89,sectors=lambda j:'S'+str(j))
            original=dict(r.active['Q']);mark(r,ss[0],140,H.op(1));r.event(H.op(1),is_open=True)
            qs={s:r.account.quantity(s) for s in ss};by.append(qs)
            self.assertTrue(all(qs[s]<=original[s] for s in ss))
            self.keep('09_downstream_'+str(enabled),r,H.op(1),approved_Q=original,filled_Q=qs)
        self.assertLess(by[1][ss[0]],by[0][ss[0]])
        self.assertGreater(by[1][ss[-1]],by[0][ss[-1]])

    def test10_old_funding_exits_NOT_cancelled_after_new_order_shrink(self):
        r=Runner('C_BATCH20');ss=H.fixtures(r,9)
        H.close(r,0,H.packet(r,ss,0),{'G':H.obs(r,'G',0)});r.event(H.op(1),is_open=True)
        new=H.fixtures(r,4,'B','NEW')
        H.close(r,1,H.packet(r,ss,1,receipt=False,core=False),{'NEW':H.obs(r,'NEW',1)})
        pr={s:(100+j,) for j,s in enumerate(ss)};pr.update({s:(j,) for j,s in enumerate(new)})
        H.close(r,2,H.packet(r,ss+new,2,core=False,priorities=pr),{'NEW':H.obs(r,'NEW',2,105)},{'NEW':200,**{s:50 for s in set(r.account.market.sectors.values()) if s!='NEW'}})
        a=r.account;D0=copy.deepcopy(r.active['D']);duties=copy.deepcopy(a.exit_duties);self.assertTrue(D0)
        old_sellq=sum(o.remaining_target for o in a.exits.values());cash=a.available
        for s in new:mark(r,s,500,H.op(3))
        r.event(H.op(3),is_open=True)
        sold=sum(f.shares for f in a.fills if f.side=='sell')
        self.assertEqual(sold,old_sellq);self.assertTrue(all(a.quantity(s)==0 for s in new));self.assertEqual(r.active['D'],D0)
        self.assertGreater(a.available,cash);self.assertFalse(any(x.get('kind')=='funding_exit_cancel_ack' for x in a.audit_log))
        self.keep('10_D_not_cancelled',r,H.op(3),sold_old_qty=sold,new_buys=0,idle_cash_after_old_sale=a.available,original_D=D0)

    def test11_cross_process_restore_and_wrong_switch_reject(self):
        r,ss=setup(price=100,floor=95,star=True);sid=ss[0];r.event(H.op(1),is_open=True,capacities={sid:0})
        r.apply_window('buy',sid,H.win(r,sid,H.op(1)+timedelta(minutes=1),'buy',450,'restore-partial'))
        cp=ROOT/'checkpoints'/'partial.pkl';r.checkpoint(cp);at=H.op(1)+timedelta(minutes=1);expected=full_state_hash(r);out=ROOT/'checkpoints'/'child.json'
        subprocess.run([sys.executable,'-B',str(HERE/'restore_check.py'),str(cp),str(out),at.isoformat()],check=True,capture_output=True,text=True)
        self.assertEqual(json.loads(out.read_text())['full_state_hash'],expected)
        rr=Runner.restore(cp);self.assertEqual(full_state_hash(rr),expected)
        for z in (r,rr):
            mark(z,sid,110,H.op(1)+timedelta(minutes=2));z.apply_window('buy',sid,H.win(z,sid,H.op(1)+timedelta(minutes=2),'buy',100000,'after-restore'))
        self.assertEqual(full_state_hash(r),full_state_hash(rr))
        side=cp.with_suffix('.provenance.json');old=side.read_bytes();x=json.loads(old);x['binding']['approved_risk_switch']=False;IO.write_json(side,x)
        with self.assertRaises(ValueError):Runner.restore(cp)
        IO.write_bytes(side,old);self.keep('11_restart',r,H.op(1)+timedelta(minutes=2),old_prefix_immutable=True)

    def test12_tampered_R0_atomic_reject_and_unsupported_split(self):
        r,ss=setup();sid=ss[0];z=r.risk.approvals[key(r,sid)];z['approved']['R0']+=1
        before=full_state_hash(r)
        with self.assertRaises(ValueError):r.event(H.op(1),is_open=True)
        self.assertEqual(full_state_hash(r),before)
        r,ss=setup();sid=ss[0];before=full_state_hash(r);at=H.op(1)-timedelta(minutes=1)
        with self.assertRaisesRegex(ValueError,'unsubmitted C approval'):
            r.event(at,actions=[dict(event_id='unsupported-unsubmitted',sid=sid,ratio=D('1.4'),at=at,new_shares_sellable_at=H.op(2))])
        self.assertEqual(full_state_hash(r),before)
        self.keep('12_atomic_unsupported',r,H.cl(0),history_events=0)

    def test13_floor_rise_no_spent_credit_refund_and_fresh_independent(self):
        r,ss=setup(price=100,floor=95,star=True);sid=ss[0];r.event(H.op(1),is_open=True);k=key(r,sid);spent=r.risk.approvals[k]['spent'];oldfloor=r.account.layers[0]['floor']
        mark(r,sid,110,H.cl(1));rows=H.packet(r,ss,1,core=False);rows[sid]['cp_floor']=D(108)
        H.close(r,1,rows,{})
        self.assertGreater(r.account.layers[0]['floor'],oldfloor)
        self.assertEqual(r.risk.approvals[k]['spent'],spent)
        self.assertEqual(r.risk.approvals[k]['remaining'],0)
        if r.active and r.active['certificate_id']+'|'+sid in r.risk.approvals:
            new=r.risk.approvals[key(r,sid)]
            self.assertNotEqual(new['approved']['receipt'],r.risk.approvals[k]['approved']['receipt'])
            self.assertEqual(new['spent'],0)
        self.keep('13_floor_raise_not_refund',r,H.cl(1),native_old_floor=oldfloor,native_new_floor=r.account.layers[0]['floor'])

    def test14_gap_below_floor_not_free_risk(self):
        r,ss=setup(price=100,floor=95,star=True);sid=ss[0];mark(r,sid,94,H.op(1));r.event(H.op(1),is_open=True)
        self.assertFalse(r.account.layers);self.assertEqual(r.risk.approvals[key(r,sid)]['spent'],0)
        self.keep('14_gap_no_zero_risk',r,H.op(1))

    def test15_all_saved_rows_arithmetic_not_account_replay(self):
        arms=json.loads((HERE.parent/'g-s-C-approved-risk-execution-readonly-20261102/ALL_POSITIVE_C_AUTHORIZATIONS.json').read_text())
        counts={}
        for arm,rows in arms.items():
            c=0
            for x in rows:
                o=x['actual_order']
                if not o:continue
                q0=x['approved_qty'];p0=D(x['decision_preview_price']);f0=D(x['decision_effective_floor']);q=o['pre_fill_amend_qty'];p=D(o['reserved_price']);floor=D(o['effective_floor'])
                R=F(q0)*(F(p0)-F(f0));raw=min(q0,q,int(R//(F(p)-F(floor)))) if p>floor else 0
                rule=T.QuantityRule(**x['original_dated_quantity_rule']);bound=rule.buy_floor(raw)
                self.assertEqual(bound,o['static_risk_keep_upper_qty'],(x['name'],arm,bound,o['static_risk_keep_upper_qty']))
                c+=1
            counts[arm]=c
        IO.write_json(ROOT/'15_saved_arithmetic.json',dict(rows=counts,historical_events=0,not_native_reconstruction=True))

    def test16_fractional_ratio_split_same_raw_currency_domain(self):
        r,ss=setup(price=99.4,floor=91,star=True);sid=ss[0]
        r.event(H.op(1),is_open=True,capacities={sid:0});a=r.account;q=a.buys[sid].remaining_shares
        self.assertEqual(q,1005)
        r.apply_window('buy',sid,H.win(r,sid,H.op(1)+timedelta(minutes=1),'buy',q-50,'split14-first'))
        k=key(r,sid);R=r.risk.approvals[k]['approved']['R0'];spent=r.risk.approvals[k]['spent'];at=H.op(1)+timedelta(minutes=2)
        r.event(at,actions=[dict(event_id='split14',sid=sid,ratio=D('1.4'),at=at,new_shares_sellable_at=H.op(2))])
        self.assertEqual(a.buys[sid].remaining_shares,70)
        self.assertEqual(r.risk.approvals[k]['spent'],spent);self.assertEqual(r.risk.approvals[k]['approved']['R0'],R)
        w=H.win(r,sid,at+timedelta(minutes=1),'buy',70,'split14-last')
        f=r.apply_window('buy',sid,w);self.assertEqual(f.shares,70)
        self.assertEqual(r.risk.approvals[k]['spent'],R)
        before=full_state_hash(r);self.assertIsNone(r.apply_window('buy',sid,w));self.assertEqual(full_state_hash(r),before)
        self.keep('16_split14_idempotent',r,at+timedelta(minutes=1))



def main():
    global ROOT
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT);args=p.parse_args();ROOT=args.out;ROOT.mkdir(parents=True,exist_ok=True)
    start=datetime.now(timezone.utc).isoformat();IO.write_json(ROOT/'STARTED.json',dict(at=start,source=Runner().source_binding(),scope='generated synthetic native only',historical_events=0))
    began=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    out=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),seconds=time.monotonic()-began,started_at=start,completed_at=datetime.now(timezone.utc).isoformat(),historical_account_events=0,records=list(Cases.records))
    IO.write_json(ROOT/'RESULTS.json',out);print(json.dumps(out));return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
