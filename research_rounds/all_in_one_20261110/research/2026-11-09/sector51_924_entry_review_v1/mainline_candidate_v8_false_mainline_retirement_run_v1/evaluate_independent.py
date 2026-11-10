"""Read-only output analysis. Never imports/executes strategy or loads its historical Data."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,hashlib,ast
O=Path(__file__).resolve().parent;ROOT=O.parent;C=ROOT/'mainline_candidate_v8_false_mainline_retirement';B=ROOT/'mainline_m7_downturn_cash_batch_v6'
INITIAL=D(1200000);ZERO=D(0);TOL=D('1e-16');REASON='FALSE_SECTOR_NON_MAINLINE_EXPANSION_RETIREMENT'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def near(a,b,label):assert abs(a-b)<TOL,(label,str(a),str(b))
def runner_review():
    ap=read(O/'CONTRACT_APPROVAL.json');qa=read(C/'SYNTHETIC_QA.json')
    assert ap['approved'] and ap['runner_sha256']==sha(O/'run.py')
    assert ap['engine_sha256']==sha(C/'engine.py')==qa['engine_sha256']=='0e9a3358c126ed0b9b4143c8dae44770c05bd9324f56a63bff160a7cd32c049f'
    assert ap['contract_sha256']==sha(C/'CONTRACT.md')==qa['contract_sha256']=='5392a375eb7dfd1652f6d11073a004f0df6da8a2003a758e934aee9121be143a'
    deps=read(C/'DEPENDENCY_SEAL.json')['hashes'];assert all(sha(p)==h for p,h in deps.items())
    source=(O/'run.py').read_text();ast.parse(source)
    assert "e=m.run_loop(m.Engine(data),checkpoint=False)" in source
    assert "data=m.Data(end='2024-10-31')" in source
    assert "assert not (O/'RUN_STARTED.json').exists()" in source
    assert 'source = m7.source' in (C/'engine.py').read_text()
    # Baseline atomic loop is rebased without modification. False skips only intermediate
    # assignment of pending/export/print; final pending assignment occurs unconditionally.
    loop=(ROOT/'mainline_candidate_v4_known_sector_fix_v2/engine.py').read_text().split('def run_loop(e,checkpoint=True,prefix=')[1].split("if __name__")[0]
    skipped=loop.split('if checkpoint and day(d)')[1].split('except Blocked')[0]
    assert 'e.pending=pending;e.export(' in skipped and "print('CHECKPOINT '" in skipped
    assert 'e.pending=pending;return e' in loop
    result=dict(result='PASS',runner_sha256=sha(O/'run.py'),candidate_sha256=sha(C/'engine.py'),contract_sha256=sha(C/'CONTRACT.md'),sealed_dependencies=len(deps),checkpoint_false='Skips intermediate snapshot export and print only; same economic method sequence and atomic rollback.',strategy_executed_by_evaluator=False)
    save('INDEPENDENT_RUNNER_REVIEW.json',result);return result

def evaluate(path,end):
    rows={n:read(path/(n+'.json')) for n in ['DAY_LEDGER','ORDERS','HOLDINGS','SECTOR_DAILY','EQUITY_EVENTS','CAPITAL_LOTS']}
    rows={n:[r for r in rr if r['day']<=end] for n,rr in rows.items()}
    led=rows['DAY_LEDGER'];orders=rows['ORDERS'];holdings=rows['HOLDINGS'];equity=rows['EQUITY_EVENTS'];sector=rows['SECTOR_DAILY']
    assert led and led[-1]['day']==end
    byday=lambda rr: {d:[r for r in rr if r['day']==d] for d in [x['day'] for x in led]}
    ob,hb,eb,sb=map(byday,[orders,holdings,equity,sector]);lots={};cash=INITIAL;recv=ZERO;fees=ZERO;peak=INITIAL;peakday=led[0]['day'];maxdd=ZERO;ddpeak=ddtrough=peakday
    for r in led:
        d=r['day']
        for o in ob[d]:
            q=int(o['qty']);p=D(o['price']);n=D(o['notional']);f=D(o['fee']);delta=D(o['cash_delta']);buy=o['side'].startswith('BUY')
            near(n,q*p,('order_notional',o['order_seq']));near(delta,-n-f if buy else n-f,('order_cash',o['order_seq']))
            cash+=delta;fees+=f
            if buy:
                assert o['lot_id'] not in lots;lots[o['lot_id']]=q
            else:
                allocations=o.get('lot_quantities') or {lid:lots[lid] for lid in o['lots']}
                assert sum(allocations.values())==q
                for lid,take in allocations.items():assert 0<take<=lots[lid];lots[lid]-=take
                lots={k:v for k,v in lots.items() if v}
        for ev in eb[d]:cash+=D(ev.get('cash_delta','0'));recv+=D(ev.get('receivable_delta','0'))
        hs=hb[d];near(sum((D(h['market_value']) for h in hs),ZERO),D(r['market_value']),('holdings_mv',d))
        assert {h['lot_id']:h['qty'] for h in hs}==lots,('daily_lot_inventory',d)
        near(cash,D(r['cash']),('daily_cash',d));near(recv,D(r['receivable']),('daily_receivable',d));near(fees,D(r['fees_paid']),('daily_fee',d))
        near(cash+recv+sum((D(h['market_value']) for h in hs),ZERO),D(r['NAV']),('daily_nav',d))
        near(sum((D(s['marked_net_pnl']) for s in sb[d]),ZERO),D(r['NAV'])-INITIAL,('sector_total_pnl',d))
        nav=D(r['NAV'])
        if nav>peak:peak=nav;peakday=d
        dd=1-nav/peak
        if dd>maxdd:maxdd=dd;ddpeak=peakday;ddtrough=d
    buys={o['lot_id']:o for o in orders if o['side'].startswith('BUY')}
    finalhold=hb[end];states={s['sector51']:s for s in sb[end]};exposure=defaultdict(lambda:ZERO);sector_exposure=defaultdict(lambda:ZERO)
    for h in finalhold:
        M=states[h['sector51']]['M'];label='MAINLINE' if M==1 else 'NON_MAINLINE' if M==0 else 'UNKNOWN';role=buys[h['lot_id']]['capital_role'];value=D(h['market_value']);exposure[label+'|'+role]+=value;sector_exposure[h['sector51']+'|'+label+'|'+role]+=value
    contrib={}
    for s in sb[end]:
        sec=s['sector51'];cashflow=sum((D(o['cash_delta']) for o in orders if o['sector51']==sec),ZERO)
        entitlement=sum((D(ev.get('receivable_delta','0')) for ev in equity if ev['sector51']==sec and D(ev.get('receivable_delta','0'))>0),ZERO)
        mv=sum((D(h['market_value']) for h in finalhold if h['sector51']==sec),ZERO)
        pnl=cashflow+entitlement+mv;near(pnl,D(s['marked_net_pnl']),('sector_independent_pnl',sec))
        contrib[sec]=dict(net_pnl=pnl,contribution_pct_initial=100*pnl/INITIAL,market_value=mv,trade_cashflow=cashflow,dividend_entitlement=entitlement)
    retiring=[o for o in orders if o['reason']==REASON]
    # Match subsequent same-stock BUY quantities FIFO to retired quantities. Descriptive only;
    # no invented counterfactual claim that every retirement or subsequent buy was mistaken.
    queues=defaultdict(list);pairs=[]
    for o in orders:
        if o['reason']==REASON:queues[o['sid']].append(dict(order=o,remaining=o['qty']))
        elif o['side'].startswith('BUY'):
            remaining=o['qty']
            for rt in queues[o['sid']]:
                if not remaining:break
                if not rt['remaining']:continue
                sell=rt['order'];q=min(remaining,rt['remaining']);remaining-=q;rt['remaining']-=q
                fees_alloc=D(sell['fee'])*q/sell['qty']+D(o['fee'])*q/o['qty']
                premium=(D(o['price'])-D(sell['price']))*q
                pairs.append(dict(sid=o['sid'],sector51=o['sector51'],retirement_day=sell['day'],rebuy_day=o['day'],retirement_order=sell['order_seq'],rebuy_order=o['order_seq'],matched_qty=q,same_round=sell['round_id']==o['round_id'],price_premium_including_slippage=premium,allocated_two_way_fees=fees_alloc,net_repurchase_cost=premium+fees_alloc))
    dates={r['day']:r for r in led};oct8=dates.get('2024-10-08')
    result=dict(end=end,days=len(led),NAV=D(led[-1]['NAV']),profit=D(led[-1]['NAV'])-INITIAL,return_pct=100*(D(led[-1]['NAV'])/INITIAL-1),cash=D(led[-1]['cash']),market_value=D(led[-1]['market_value']),max_close_drawdown_pct=100*maxdd,drawdown_peak_date=ddpeak,drawdown_trough_date=ddtrough,oct8=None if not oct8 else dict(NAV=D(oct8['NAV']),profit=D(oct8['NAV'])-INITIAL,return_pct=100*(D(oct8['NAV'])/INITIAL-1)),exposure=dict(exposure),sector_exposure=dict(sector_exposure),sector_contributions=contrib,selected_sector_contributions={k:v for k,v in contrib.items() if any(w in k for w in ['软件','半导体','光伏'])},retirement=dict(orders=len(retiring),shares=sum(o['qty'] for o in retiring),actual_net_cash=sum((D(o['cash_delta']) for o in retiring),ZERO),fees=sum((D(o['fee']) for o in retiring),ZERO),notional=sum((D(o['notional']) for o in retiring),ZERO)),trading=dict(orders=len(orders),buy_orders=sum(o['side'].startswith('BUY') for o in orders),sell_orders=sum(o['side'].startswith('SELL') for o in orders),orders_per_day=D(len(orders))/len(led),fees=fees,turnover_notional=sum((D(o['notional']) for o in orders),ZERO),reason_counts=dict(Counter(o['reason'] for o in orders))),retirement_rebuy=dict(label='Observed same-stock retirement then rebuy; executed raw-price spread and allocated fees only, not proof of mistaken exit or causal loss. Excludes hypothetical intervening dividends, corporate-action share changes, interest and opportunity costs.',matched_shares=sum(p['matched_qty'] for p in pairs),matched_legs=len(pairs),price_premium_including_slippage=sum((p['price_premium_including_slippage'] for p in pairs),ZERO),allocated_two_way_fees=sum((p['allocated_two_way_fees'] for p in pairs),ZERO),net_repurchase_cost=sum((p['net_repurchase_cost'] for p in pairs),ZERO),pairs=pairs),accounting_checks='PASS: daily order cash/notional, all lot quantities, cash, receivable, fees, holdings, NAV and sector PnL independently reconciled')
    return result

if __name__=='__main__':
    runner_review()
    if not (O/'RUN_STATUS.json').exists():
        print('RUNNER_REVIEW_PASS; result evaluation waiting for RUN_STATUS; no strategy started')
        raise SystemExit(0)
    status=read(O/'RUN_STATUS.json');end=status['last']['day'];base_end=read(B/'RUN_STATUS.json')['last']['day'];end=min(end,base_end)
    for path in [O/'once_20241031',B/'once_20241031']:
        hashes=read(path/'OUTPUT_HASHES.json');assert all(sha(path/n)==h for n,h in hashes.items() if n!='OUTPUT_HASHES.json')
    a=evaluate(O/'once_20241031',end);b=evaluate(B/'once_20241031',end)
    result=dict(comparison_end=end,M8_status=status,complete_matched_horizon=status['completed_horizon'] and end=='2024-10-31',M8=a,M7=b,delta={k:a[k]-b[k] for k in ['NAV','profit','return_pct','cash','market_value','max_close_drawdown_pct']},scope='Research only; no shared risk pool; matched certified endpoints only',input_hashes={str(p):sha(p) for p in [O/'run.py',C/'engine.py',C/'CONTRACT.md',O/'RUN_STATUS.json',O/'once_20241031/OUTPUT_HASHES.json',B/'once_20241031/OUTPUT_HASHES.json']})
    save('INDEPENDENT_M8_VS_M7.json',result)
    save('EVALUATION_SEAL.json',dict(evaluator_sha256=sha(__file__),runner_review_sha256=sha(O/'INDEPENDENT_RUNNER_REVIEW.json'),result_sha256=sha(O/'INDEPENDENT_M8_VS_M7.json')))
    print(json.dumps(dict(end=end,delta=result['delta'],M8_NAV=a['NAV'],M7_NAV=b['NAV'],accounting='PASS'),default=str))
