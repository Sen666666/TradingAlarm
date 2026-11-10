"""Read-only attribution of existing proxy ledgers. No strategy or order execution."""
import os,sys,json,gzip,csv,hashlib,copy
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
sys.dont_write_bytecode=True
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
SRC=R/'act_only_ablation_continuous_v1/run/pair'
OUT=Path(__file__).parent
Z=D(0); EPS=D('1e-8')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,o): (OUT/n).write_text(json.dumps(o,indent=2,ensure_ascii=False,default=str)+'\n')
def table(n,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/n).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def gz(p):
    with gzip.open(p,'rt') as f:return json.load(f)
source_paths=[SRC/f for f in ['PVR.json.gz','NOACT.json.gz','daily.jsonl.gz','balances.jsonl.gz']]
source_hashes={str(p):sha(p) for p in source_paths}
daily=defaultdict(list)
with gzip.open(SRC/'daily.jsonl.gz','rt') as f:
    for l in f:
        x=json.loads(l);daily[x['account']].append(x)
peaks={}
for arm,rows in daily.items():
    p=rows[0];best=(Z,p,p)
    for t in rows:
        if D(t['nav'])>D(p['nav']):p=t
        dd=D(t['nav'])/D(p['nav'])-1
        if dd<best[0]:best=(dd,p,t)
    peaks[arm]=best
# Only the original price readers are imported, never Account, Runner or context constructed.
sys.path.insert(0,str(R/'account_comparison_continuous_v1/inputs'))
import continuous_inputs as C
gl=C.J.M.E.FastMarket.__mro__[1].__init__.__globals__
manifest_path=C.J.M.P/'manifest.json'
records={x['series_id']:x for x in json.loads(manifest_path.read_text())['series']}
source_hashes[str(manifest_path)]=sha(manifest_path)
marks={};mark_rows=[]
for arm,(_,p,t) in peaks.items():
    for snap in [p,t]:
        day=snap['at'][:10]
        for sid in snap['positions']:
            if (day,sid) in marks:continue
            rec=records[sid];path=Path(rec['raw']['path']);actual_hash=sha(path)
            assert actual_hash==rec['raw']['sha256'],('raw hash',sid)
            source_hashes[str(path)]=actual_hash
            raw=gl['read_raw'](path,rec);valid=gl['eligible_prices'](raw).loc[:day]
            assert len(valid),('missing mark: UNKNOWN',day,sid)
            d=valid.index[-1].date().isoformat();price=D(str(valid.iloc[-1]['close']))
            events,_=gl['read_actions'](rec,manifest_path.parent)
            ap=Path(rec['adjustment']['actions']['path']);source_hashes[str(ap)]=sha(ap)
            intervening=[e for e in events if d<e['effective_date']<=day]
            for e in sorted(intervening,key=lambda e:e['effective_date']):
                price=(price-D(str(e.get('signal_cash_per_old_share',e['cash_per_old_share']))))/D(str(e.get('signal_split_ratio',e['split_ratio'])))
            assert price>0
            marks[day,sid]=price
            mark_rows.append(dict(day=day,sid=sid,mark=price,raw_observation_day=d,stale_calendar_days=(__import__('datetime').date.fromisoformat(day)-__import__('datetime').date.fromisoformat(d)).days,intervening_actions=len(intervening),raw_source=str(path),raw_sha256=actual_hash,evidence='NON-PIT; daily close valuation only; tradability UNKNOWN'))
summaries=[];layer_rows=[];group_rows=[];cash_rows=[];round_rows=[];interval_trade_rows=[];event_rows=[]
for arm,(mdd,peak,trough) in peaks.items():
    account=gz(SRC/f'{arm}.json.gz');start=peak['at'];end=trough['at'];peaknav=D(peak['nav'])
    # Both actual peaks are before the first fill. Assert rather than silently generalize.
    assert not peak['positions'] and not peak['layers']
    assert all(D(peak[k])==0 for k in ['inventory','dividend_receivable','sale_receivable','fees_cny'])
    assert not any(x['at']<=start for x in account['trades'])
    birth={x['layer']:x for x in account['journal'] if x['kind']=='real_buy_fill'}
    finished_layers={x['id']:x for x in account['layers']}
    snap_layers={x['id']:x for x in trough['layers']}
    states={};stock_qty=defaultdict(int);sid_round=defaultdict(int)
    events=[]
    for i,x in enumerate(account['audit']):
        if x['kind']=='dividend_accrual':
            r=x['receivable'];events.append((r['ex_at'],-1,i,r))
    events += [(x['at'],0,i,x) for i,x in enumerate(account['journal']) if x['kind']=='actual_split']
    events += [(x['at'],1,i,x) for i,x in enumerate(account['trades'])]
    events.sort(key=lambda e:e[:3])
    for at,typ,idx,x in events:
        if at>end:break
        assert at>start,('events outside permitted interval',at,start)
        if typ==-1:
            sid=x['security_id'];keys=[k for k,s in states.items() if s['sid']==sid and s['qty']>0]
            qty=sum(states[k]['qty'] for k in keys);assert qty
            amount=D(x['net_local'])
            for k in keys:states[k]['dividend']+=amount*D(states[k]['qty'])/qty
            event_rows.append(dict(account=arm,at=at,kind='dividend_accrual',sid=sid,amount=amount,external_cash_paid='UNKNOWN',historical_terms='UNKNOWN'))
        elif typ==0:
            sid=x['sid'];keys=[k for k,s in states.items() if s['sid']==sid and s['qty']>0]
            rat=D(x['ratio']);target=int(D(sum(states[k]['qty'] for k in keys))*rat)
            qs=[int(D(states[k]['qty'])*rat) for k in keys]
            for j in range(target-sum(qs)):qs[j%len(qs)]+=1
            for k,q in zip(keys,qs):
                s=states[k];s['qty']=q
                if q==0:
                    s['realized_net']-=s['cost_net'];s['realized_gross']-=s['cost_gross']
                    s['split_writeoff_cost']+=s['cost_net'];s['cost_net']=s['cost_gross']=Z
            stock_qty[sid]=target
            event_rows.append(dict(account=arm,at=at,kind='split',sid=sid,amount=0,split_ratio=rat,target_shares=target,external_cash_paid='NOT_APPLICABLE',historical_terms='UNKNOWN'))
        else:
            sid=x['security_id'];fee=D(x['fees_cny']);gross=D(x['gross_cny'])
            interval_trade_rows.append(dict(account=arm,at=at,receipt_id=x['receipt_id'],sid=sid,side=x['side'],shares=x['shares'],gross_cny=gross,fees_cny=fee,execution_basis=x['execution_basis']))
            if x['side']=='buy':
                k=x['layer'];is_initial=stock_qty[sid]==0
                if is_initial:sid_round[sid]+=1
                b=birth[k]
                states[k]=dict(layer=k,sid=sid,kind=x['kind'],position_layer='initial' if is_initial else 'subsequent',role=b['role'],entry_pool=b['pool'],round_key=sid+':'+str(sid_round[sid]),opened=at,qty=x['shares'],buy_gross=gross,buy_fees=fee,sell_gross=Z,sell_fees=Z,cost_net=gross+fee,cost_gross=gross,realized_net=Z,realized_gross=Z,dividend=Z,net_cash=-gross-fee,split_writeoff_cost=Z)
                stock_qty[sid]+=x['shares']
            else:
                assert sum(p['shares'] for p in x['parts'])==x['shares']
                for part in x['parts']:
                    k=part['layer'];s=states[k];q=part['shares'];assert 0<q<=s['qty']
                    cg=s['cost_gross']*D(q)/s['qty'];cn=s['cost_net']*D(q)/s['qty']
                    sg=D(x['price'])*q;sf=fee*D(q)/x['shares'];net=D(part['net_cash'])
                    assert abs(sg-sf-net)<EPS
                    s['realized_gross']+=sg-cg;s['realized_net']+=net-cn
                    s['sell_gross']+=sg;s['sell_fees']+=sf;s['net_cash']+=net
                    s['cost_net']-=cn;s['cost_gross']-=cg;s['qty']-=q
                    stock_qty[sid]-=q
                    if s['qty']==0:s['closed_at']=at
    assert {s:q for s,q in stock_qty.items() if q}==trough['positions']
    for k,s in states.items():
        endpoint=snap_layers[k] if s['qty'] else finished_layers[k]
        assert endpoint['qty']==s['qty'] or s['qty']==0
        if s['qty']==0:assert endpoint['closed']<=end
        assert abs(D(endpoint['cash'])-s['net_cash'])<EPS,('cash layer',arm,k)
        assert abs(D(endpoint['dividend'])-s['dividend'])<EPS,('dividend layer',arm,k)
        inv=D(s['qty'])*marks.get((end[:10],s['sid']),Z)
        assert not s['qty'] or (end[:10],s['sid']) in marks
        s.update(inventory_at_trough=inv,unrealized_net=inv-s['cost_net'],unrealized_gross=inv-s['cost_gross'],fees=s['buy_fees']+s['sell_fees'])
        s['nav_contribution']=s['net_cash']+inv+s['dividend']
        assert abs(s['realized_net']+s['unrealized_net']+s['dividend']-s['nav_contribution'])<EPS
        assert abs(s['realized_gross']+s['unrealized_gross']+s['dividend']-s['fees']-s['nav_contribution'])<EPS
        s['round_status_at_trough']='OPEN' if stock_qty[s['sid']]>0 and s['round_key']==s['sid']+':'+str(sid_round[s['sid']]) else 'COMPLETE'
        layer_rows.append(dict(account=arm,peak_at=start,trough_at=end,peak_nav=peaknav,**s,nav_contribution_fraction=s['nav_contribution']/peaknav))
    total=lambda key:sum((s[key] for s in states.values()),Z)
    delta=D(trough['nav'])-D(peak['nav'])
    for key,expected in [('inventory_at_trough',D(trough['inventory'])),('fees',D(trough['fees_cny'])),('dividend',D(trough['dividend_receivable'])),('nav_contribution',delta),('net_cash',D(trough['available'])-D(peak['available']))]:
        assert abs(total(key)-expected)<EPS,(arm,key,total(key),expected)
    rounds=defaultdict(list)
    for s in states.values():rounds[s['round_key']].append(s)
    for key,ls in rounds.items():
        status=ls[0]['round_status_at_trough'];assert all(x['round_status_at_trough']==status for x in ls)
        round_rows.append(dict(account=arm,round_key=key,sid=ls[0]['sid'],status_at_trough=status,opened=min(x['opened'] for x in ls),closed_at=max(x.get('closed_at','') for x in ls) if status=='COMPLETE' else '',layers=len(ls),pnl=sum((s['nav_contribution'] for s in ls),Z),realized_net=sum((s['realized_net'] for s in ls),Z),unrealized_net=sum((s['unrealized_net'] for s in ls),Z),dividend=sum((s['dividend'] for s in ls),Z),denominator=peaknav))
    metrics=['buy_gross','sell_gross','net_cash','inventory_at_trough','cost_net','cost_gross','realized_net','realized_gross','unrealized_net','unrealized_gross','dividend','fees','nav_contribution']
    for grouping in [('position_layer',),('kind',),('role',),('entry_pool',),('position_layer','kind'),('entry_pool','role'),('position_layer','entry_pool','role')]:
        bins=defaultdict(list)
        for s in states.values():bins[tuple(s[k] for k in grouping)].append(s)
        contributions=Z
        for keys,ls in bins.items():
            values={m:sum((s[m] for s in ls),Z) for m in metrics}
            contributions+=values['nav_contribution']
            group_rows.append(dict(account=arm,grouping=' x '.join(grouping),group=' x '.join(keys),peak_at=start,trough_at=end,denominator_peak_nav=peaknav,layers=len(ls),live_layers_at_trough=sum(s['qty']>0 for s in ls),**values,contribution_fraction_of_peak=values['nav_contribution']/peaknav,fraction_of_total_drawdown_loss=-values['nav_contribution']/-delta))
        assert abs(contributions-delta)<EPS
    for k in ['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','fees_cny']:
        cash_rows.append(dict(account=arm,field=k,peak_value=peak[k],trough_value=trough[k],change=D(trough[k])-D(peak[k]),sign_in_NAV=-1 if k=='payable' else 0 if k=='fees_cny' else 1))
    closed=[r for r in round_rows if r['account']==arm and r['status_at_trough']=='COMPLETE']
    opened=[r for r in round_rows if r['account']==arm and r['status_at_trough']=='OPEN']
    summary=dict(account=arm,peak_at=start,trough_at=end,peak_nav=peaknav,trough_nav=D(trough['nav']),max_drawdown_fraction=mdd,nav_change=delta,days_in_interval=sum(start<x['at']<=end for x in daily[arm]),interval_definition='(actual peak timestamp, actual trough timestamp]',**{m:total(m) for m in metrics},closed_rounds_at_trough=len(closed),closed_round_net=sum((r['pnl'] for r in closed),Z),open_rounds_at_trough=len(opened),open_round_net=sum((r['pnl'] for r in opened),Z),cash_bridge_residual=delta-total('net_cash')-total('inventory_at_trough')-total('dividend'),net_bridge_residual=delta-total('realized_net')-total('unrealized_net')-total('dividend'),gross_bridge_residual=delta-total('realized_gross')-total('unrealized_gross')-total('dividend')+total('fees'),NON_PIT=True,actual_tradability='UNKNOWN',actual_external_dividend_payout='UNKNOWN')
    summaries.append(summary)
    print(json.dumps(summary,default=str,ensure_ascii=False),flush=True)
for p,h in source_hashes.items():assert sha(p)==h,('source modified',p)
save('SUMMARY.json',summaries)
table('MDD_PEAK_TROUGH.csv',summaries)
table('CASH_BALANCE_BRIDGE.csv',cash_rows)
table('LAYER_CONTRIBUTIONS.csv',layer_rows)
table('GROUP_CONTRIBUTIONS.csv',group_rows)
table('ROUND_STATUS_AT_TROUGH.csv',round_rows)
table('INTERVAL_TRADES.csv',interval_trade_rows)
table('INTERVAL_EQUITY_EVENTS.csv',event_rows)
table('ENDPOINT_MARKS.csv',mark_rows)
save('SOURCE_SHA256.json',source_hashes)
save('CHECKS.json',dict(status='PASS',source_unchanged=True,cash_share_dividend_cost_replay_pass=True,bridge_tolerance=str(EPS),all_group_partitions_conserve_NAV=True,source_daily_rows={a:len(v) for a,v in daily.items()},interval_trades=len(interval_trade_rows),layers=len(layer_rows),no_strategy_run=True,no_new_data_fetch=True,NON_PIT=True,actual_tradability='UNKNOWN'))
lines=['# Exact peak-to-trough attribution','','This is an attribution of existing daily proxy ledgers, not a strategy backtest or evidence of tradable fills. All sources are NON-PIT and actual tradability remains UNKNOWN.','','## Scope and accounting','','The maximum drawdown is computed from the complete daily NAV path. Each attribution then uses only events in (its actual peak timestamp, its actual trough timestamp]. Both actual peaks happen to be the initial empty account on 2022-01-04. Neither uses a full-test closed-round cohort.','','Net-cost convention: delta NAV = delta realized sale PnL (sold shares allocated buy and sell fees) + delta unrealized mark PnL (remaining cost includes unsold buy fees) + dividend accrual. Fees are already included and must not be deducted again.','','Gross-cost convention: delta NAV = gross realized sale PnL + gross unrealized mark PnL + dividend accrual - all interval trading fees. Dividends are booked receivables, not verified cash payouts. Splits preserve total remaining cost and change quantities; fractional-share treatment follows the original ledger, not invented cash compensation.','','## Results','']
for s in summaries:
    lines += [f"### {s['account']}",f"Peak {s['peak_at']}: CNY {s['peak_nav']}; trough {s['trough_at']}: CNY {s['trough_nav']}.",f"Drawdown CNY {s['nav_change']}, fraction {s['max_drawdown_fraction']}.",f"Net bridge: {s['realized_net']} + {s['unrealized_net']} + {s['dividend']} = {s['nav_change']}.",f"Gross bridge: {s['realized_gross']} + {s['unrealized_gross']} + {s['dividend']} - {s['fees']} = {s['nav_change']}.",f"Rounds complete by trough: {s['closed_rounds_at_trough']}, net {s['closed_round_net']}; rounds still open at trough: {s['open_rounds_at_trough']}, net {s['open_round_net']}.",""]
lines += ['## Group definitions','','- position_layer=initial means the first executed layer after the stock position was flat. subsequent means a later layer in the same uninterrupted holding round. This is independently reconstructed, not inferred from kind.','- kind=core/add is the original strategy kind. An initial layer can be kind=add.','- entry_pool=probe/confirmed and role=core/mobile come from the immutable real_buy_fill journal, not end-of-test metadata that can migrate. These are birth-cohort attributions, not dynamic time spent in each pool.','- Every partition uses the same peak NAV CNY 1,200,000. Contribution fractions sum to that arm’s exact MDD. Fraction of total drawdown loss uses the same whole-interval loss within each arm; it is not a return on that group’s investment.','- Closed/open round status is determined at the trough. An open round’s contribution includes already sold sublayers, partial sales, remaining marked inventory and accrued dividends. It is not the same as the unrealized mark bucket.','','## Files','','MDD_PEAK_TROUGH.csv / SUMMARY.json: endpoint and both PnL conventions. GROUP_CONTRIBUTIONS.csv: conserving partitions. LAYER_CONTRIBUTIONS.csv: complete layer evidence. ROUND_STATUS_AT_TROUGH.csv: trough-specific holding rounds. INTERVAL_TRADES.csv and INTERVAL_EQUITY_EVENTS.csv: exact interval inputs. ENDPOINT_MARKS.csv: validated raw mark sources. CASH_BALANCE_BRIDGE.csv: balance-sheet change. SOURCE_SHA256.json and CHECKS.json: audit.','','No original files were edited, no strategy was executed, no data fetched, no new intraday signal inferred. Source agreement proves model accounting, not actual historical settlement or market executability.']
(OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
save('OUTPUT_SHA256.json',{p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print('COMPLETE',str(OUT),flush=True)
