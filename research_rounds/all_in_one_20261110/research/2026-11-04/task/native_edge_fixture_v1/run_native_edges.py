"""Native-account technical matching/action edges, never an economic arm."""
from pathlib import Path
from dataclasses import replace
from decimal import Decimal as D
import copy, hashlib, json, sys, time, traceback

O = Path(__file__).resolve().parent
T = O.parent
sys.path.insert(0, str(T/'capacity_cost_guard_v1'))
import capacity_adapter as C
A,N,J,L,IO = C.A,C.N,C.J,C.L,C.IO

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name, value): IO.write_json(O/name, J.W.canon(value))
def state(a, at):
    marks = a.market.marks(at, a.positions)
    bal = a.balance(at, marks)
    native_cash_components = sum((bal[k] for k in ['available','order_reserved','settlement_locked','sale_receivable','dividend_receivable']), D(0)) - bal['payable']
    inventory = sum((D(a.quantity(s))*marks[s].cny_price(at) for s in a.positions), D(0))
    assert inventory == bal['inventory'] and native_cash_components+inventory == bal['nav']
    trade_cash = sum(((-D(t['gross_cny'])-D(t['fees_cny'])) if t['side']=='buy' else D(t['gross_cny'])-D(t['fees_cny']) for t in a.trades), D(0))
    dividends = sum((D(x['receivable']['net_local']) if isinstance(x['receivable'],dict) else x['receivable'].net_local for x in a.audit_log if x['kind']=='dividend_accrual'), D(0))
    assert a.initial_cash+trade_cash+dividends+inventory == bal['nav']
    c = a.capacity_context(at)
    live = {x['id']:x['qty'] for x in a.layers if x['qty']}
    basis = {k:a.capacity_basis[k] for k in live if k in a.capacity_basis}
    return dict(at=at, balance=bal, independently_rebuilt_inventory=inventory, cash_from_original_trades=trade_cash,
                live=live, basis=basis, entry={k:a.capacity_entry[k]for k in basis}, cost_context=c)

class FixtureAccount(C.GuardAccount):
    def fill_buy(self,sid,window):
        order = self.buys.get(sid)
        if not self.edge_started and order is not None and order.remaining_shares>200 and window.capacity_shares>=200:
            self.edge_started = True
            before = self.capacity_context(window.at)
            original = order.remaining_shares
            one = replace(window, capacity_shares=100, event_id=window.event_id+'|EDGE_PART1', source_id=window.source_id+'|TECH_MATCH_CAP100')
            r1 = super().fill_buy(sid,one)
            assert r1 and r1.shares == 100 and sid in self.buys
            s1 = state(self,window.at)
            two = replace(window, capacity_shares=100, event_id=window.event_id+'|EDGE_PART2', source_id=window.source_id+'|TECH_MATCH_CAP100')
            r2 = super().fill_buy(sid,two)
            assert r2 and r2.shares == 100 and sid in self.buys
            s2 = state(self,window.at)
            ids = [self.trades[-2]['layer'], self.trades[-1]['layer']]
            assert all(self.capacity_basis[i] == D(t['gross_cny'])+D(t['fees_cny']) for i,t in zip(ids,self.trades[-2:]))
            self.edge_buy = dict(sid=sid, at=window.at, original_submitted_quantity=original,
                receipt1=r1, receipt2=r2, before=before, after_first=s1, after_second=s2, layers=ids,
                same_original_quote_price_fees_quantity_rule=True, only_capacity_and_event_ID_overridden=True)
            return r1
        return super().fill_buy(sid,window)

def clone(a):
    z = copy.copy(a)
    z.__dict__ = copy.deepcopy({k:v for k,v in a.__dict__.items()if k not in ('market','facts')})
    z.market,z.facts = a.market,a.facts
    z.__class__ = C.GuardAccount
    return z

def main():
    assert not (O/'STARTED.json').exists(), 'distinct attempt required after failure'
    sources = {str(p.resolve()):sha(p)for p in [Path(__file__),T/'capacity_cost_guard_v1/guard.py',T/'capacity_cost_guard_v1/capacity_adapter.py',T/'capacity_cost_guard_v1/run_partial_fixture.py']}
    save('STARTED.json',dict(scope='TECHNICAL_NATIVE_MATCHING_AND_SPLIT_CALLBACK_ONLY_NOT_HISTORICAL_STRATEGY',sources=sources))
    started = time.monotonic()
    N.configure_scores()
    old = A.S.O
    try:
        A.S.O = O/'input-readiness'
        shared,receipts,cp,states,ir,identity = A.S.inputs('2022')
    finally: A.S.O = old
    # Keep the next actual OPEN available; run only the initial two CLOSEs.
    shared,receipts,kw = A.S.physical_inputs(shared,receipts,cp,states,ir,'2022-01-06')
    J.START,J.END = '2022-01-01','2022-01-05'
    r = C.Runner(shared,receipts,arms=['G20'],**kw)
    r.source_freeze = sources
    a = r.accounts['G20'];a.__class__=FixtureAccount;a.edge_started=False
    with IO.atomic_runner_outputs(r,L,O,canonicalize=J.W.canon):
        assert r.run_prepared(O,120,end=J.END)
    assert a.edge_started
    a.__class__=C.GuardAccount
    sid = a.edge_buy['sid']
    close_at=N.N.iso('2022-01-05T15:10:00+08:00') if hasattr(N,'N') else J.M.N.iso('2022-01-05T15:10:00+08:00')
    # Use the existing original clock/quote and exit callback, not a sell engine.
    clock = a.facts.packet(close_at,'I')[0]
    quote = a.market.quote(sid,close_at)
    ids = [x['id']for x in a.live(sid)]
    assert len(ids)==2 and a.quantity(sid)==200
    before_exit = state(a,close_at)
    a.sell(sid,clock,quote,ids,'TECHNICAL_PARTIAL_EXIT_FIXTURE')
    open_at = clock.earliest_execution_at
    win = a.market.window(sid,open_at,'sell',1)
    assert win is not None and win.sell_allowed
    partial = replace(win,capacity_shares=100,event_id=win.event_id+'|EDGE_SELL_PART',source_id=win.source_id+'|TECH_MATCH_CAP100')
    before = {x['id']:x['qty']for x in a.live(sid)}
    basis_before = dict(a.capacity_basis)
    sell = a.fill_exit(sid,partial)
    assert sell and sell.shares==100 and a.quantity(sid)==100 and sid in a.exits
    after_exit = state(a,open_at)
    parts = a.trades[-1]['parts']
    for p in parts:
        expected = basis_before[p['layer']]*(D(1)-D(p['shares'])/D(before[p['layer']]))
        assert a.capacity_basis[p['layer']] == expected
    # Native split callbacks only. Original marks/facts intentionally remain
    # unchanged: no post-CA economic NAV continuity is asserted or fabricated.
    split_results = []
    for ratio,name in [(D(2),'SURVIVING_DOUBLE'),(D('.001'),'FRACTION_ZERO')]:
        z=clone(a); quantities={x['id']:x['qty']for x in z.live(sid)}
        bases={i:z.capacity_basis[i]for i in quantities};entries={i:z.capacity_entry[i]for i in quantities}
        z.split(event_id='TECH_CALLBACK_'+name,sid=sid,ratio=ratio,at=open_at,new_shares_sellable_at=open_at)
        live={x['id']:x['qty']for x in z.live(sid)}
        for i,q0 in quantities.items():
            q1=next(x['qty']for x in z.layers if x['id']==i)
            assert z.capacity_entry[i] == entries[i]/ratio
            assert z.capacity_basis[i] == (bases[i]if q1 else D(0))
        z.check()
        split_results.append(dict(name=name,ratio=ratio,before_qty=quantities,after_live=live,
            before_basis=bases,after_basis={i:z.capacity_basis[i]for i in quantities},
            before_entry=entries,after_entry={i:z.capacity_entry[i]for i in quantities},
            fractional_policy=z.fractional_split_policy,new_native_action_audits=[x for x in z.audit_log if str(x.get('event_id','')).startswith('TECH_CALLBACK_')],
            native_callback_only=True, post_CA_economic_NAV_continuity_NOT_TESTED=True))
    save('ACTUAL_NATIVE_EDGE_PROOF.json',dict(passed=True,buy=a.edge_buy,before_exit=before_exit,
        actual_partial_sell=sell,sell_parts=parts,after_exit=after_exit,split_callbacks=split_results,
        scope='Historical-price/native-ledger technical capacity overrides; not strategy account results',
        real_native_cash_qty_NAV_basis_bridges_checked_before_and_after_matching=True,
        split_callback_cost_units_only=True,post_CA_economic_NAV_continuity_NOT_TESTED=True))
    save('NATIVE_ACCOUNT_AFTER_EDGE.json',dict(trades=a.trades,audit=a.audit_log,journal=a.journal,layers=a.layers,metadata=a.jmeta,observer_basis=a.capacity_basis,observer_entry=a.capacity_entry,capacity_events=a.capacity_events))
    for p,h in sources.items(): assert sha(p)==h
    save('DONE.json',dict(passed=True,seconds=time.monotonic()-started,actual_native_partial_buy=2,actual_native_partial_sell=1,
        actual_native_split_callbacks=2,new_financial_strategy_arms=0,source_post_exact=True))
    print('NATIVE_EDGES_PASS',time.monotonic()-started,flush=True)

if __name__=='__main__':
    try: main()
    except BaseException:
        save('FAILED.json',dict(reason=traceback.format_exc(),no_silent_repeat=True))
        raise
