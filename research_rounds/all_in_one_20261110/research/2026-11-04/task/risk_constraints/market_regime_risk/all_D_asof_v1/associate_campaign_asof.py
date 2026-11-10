"""Saved stock-ledger asof classification only; no financial or strategy engine."""
from pathlib import Path
from decimal import Decimal as D, getcontext
import json, gzip, hashlib
import pandas as pd
getcontext().prec = 50
H=Path(__file__).resolve().parent;T=H.parents[2];R=T/'risk_constraints';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
    structural=T/'ar6_native_feasibility/market_recovery_three_state/structural_walk_v1/DAILY.json'
    smp=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';sm={r['symbol']:r for r in read(smp)}
    refs={'two_year':dict(book=T/'pvr_pool_feasibility/continuation2023/run-2023/pair/B.json.gz',qty=[R/'pvr_pool_results_2022/PVR_NO_CONFIRMED60_DAILY.json',R/'no60_continuation2023_finance/PVR_NO_CONFIRMED60_2023_DAILY.json']),
          'strong':dict(book=T/'pvr_pool_feasibility/runs/2025_26/pair/B.json.gz',qty=[R/'pvr_pool_results_2025_26/PVR_NO_CONFIRMED60_DAILY.json'])}
    sources=[structural,smp,H/'PROTOCOL.txt',H/'associate_campaign_asof.py']+[p for r in refs.values()for p in [r['book'],*r['qty']]]
    pre={str(p):sha(p)for p in sources};save(H/'INPUT_FREEZE.json',dict(before_sums=True,source_sha256=pre,scope='All v1 D dates; pure saved-ledger sum with original quote-domain inventory bridge; no new model or account'))
    st=read(structural);facts={};rows=[];daily=[];errors=[]
    for window,ref in refs.items():
        ds={str(r['at'])[:10]:r for p in ref['qty']for r in read(p)}
        dates=sorted(r['day']for r in st if r['requested_state']=='D'and r['day']in ds)
        with gzip.open(ref['book'],'rt')as f:b=json.load(f)
        events=[]
        for i,t in enumerate(b['trades']):events.append((str(t['at']),1,i,'trade',t))
        for i,a in enumerate(b['audit']):
            if a['kind']=='split':events.append((str(a['at']),0,i,'split',a))
            elif a['kind']=='dividend_accrual':events.append((str(a['receivable']['ex_at']),0,i,'dividend',a['receivable']))
        events.sort(key=lambda x:x[:3]);state={};ptr=0
        for day in dates:
            cutoff=day+' 15:10:00+08:00'
            while ptr<len(events)and events[ptr][0]<=cutoff:
                at,_,_,kind,e=events[ptr];ptr+=1;sid=e.get('security_id',e.get('sid'));x=state.setdefault(sid,dict(qty=Z,cash=Z,div=Z,buy_cash=Z,sell_net=Z,number=0,start=None,unknown=[]))
                if kind=='trade':
                    qty=D(str(e['shares']));gross=D(e['gross_cny']);fee=D(e['fees_cny'])
                    if e['side']=='buy':
                        if x['qty']==0:x.update(cash=Z,div=Z,buy_cash=Z,sell_net=Z,number=x['number']+1,start=at,unknown=[])
                        x['qty']+=qty;x['cash']-=gross+fee;x['buy_cash']+=gross+fee
                    else:x['qty']-=qty;x['cash']+=gross-fee;x['sell_net']+=gross-fee
                    assert x['qty']>=0,(sid,at,'negative original ledger quantity')
                elif kind=='split':
                    q=x['qty']*D(e['ratio'])
                    if q!=q.to_integral_value():x['unknown'].append('unsupported_noninteger_saved_split')
                    x['qty']=q
                else:
                    assert e['currency']=='CNY'
                    if x['qty']>0:x['div']+=D(e['net_local'])
                    else:errors.append(dict(window=window,day=at,sid=sid,reason='recognized_dividend_without_current_equity_campaign'))
            snap=ds[day];groups={c:dict(stocks=0,marked_inventory=Z,campaign_net_sum=Z)for c in ['profit','loss','zero','unknown']};known_inventory=Z
            for sid,qty0 in snap['positions'].items():
                qty=D(str(qty0));x=state.get(sid);unknown=[] if x is not None else ['no_current_saved_campaign']
                if x is not None:
                    unknown+=x['unknown']
                    if x['qty']!=qty:unknown.append('native_quantity_differs_from_ledger')
                if sid not in facts:
                    p=Path(sm[sid]['refs']['facts']);assert sha(p)==sm[sid]['output_sha256'][str(p)];sources.append(p);facts[sid]=pd.read_parquet(p,columns=['raw_close'])
                price=facts[sid].loc[:day].tail(1);mark=None if price.empty else D(str(price.raw_close.iloc[0]));value=None if mark is None else qty*mark
                if mark is None or not mark.is_finite()or mark<=0:unknown.append('original_asof_quote_unknown')
                if value is not None:known_inventory+=value
                net=None if unknown else x['cash']+x['div']+value
                category='unknown'if net is None else'profit'if net>0 else'loss'if net<0 else'zero'
                g=groups[category];g['stocks']+=1
                if value is not None:g['marked_inventory']+=value
                if net is not None:g['campaign_net_sum']+=net
                rows.append(dict(window=window,day=day,sid=sid,qty=qty,raw_mark=mark,quote_day=None if price.empty else str(price.index[-1].date()),marked_inventory=value,classification=category,campaign_start=None if x is None else x['start'],campaign_number=None if x is None else x['number'],asof_net_trade_cash=None if x is None else x['cash'],asof_recognized_dividend=None if x is None else x['div'],asof_campaign_economic_net=net,unknown_reasons=unknown))
            residual=D(snap['inventory'])-known_inventory
            assert abs(residual)<D('.00000001'),(window,day,'original inventory bridge mismatch',residual)
            assert sum(g['stocks']for g in groups.values())==len(snap['positions'])
            keep=groups['profit']['marked_inventory'];exit_value=sum((groups[c]['marked_inventory']for c in ['loss','zero','unknown']),Z)
            daily.append(dict(window=window,day=day,NAV=snap['nav'],old_actual_inventory=snap['inventory'],old_held_stocks=len(snap['positions']),actual_flat=not bool(snap['positions']),groups=groups,all_exit_inventory=D(snap['inventory']),loss_or_unproven_exit_inventory=exit_value,profitable_inventory_kept_under_old_stock_protection=keep,inventory_bridge_residual=residual,all_amounts_are_static_original_CLOSE_not_orders_or_CF=True))
    save(H/'ALL_D_STOCK_ASOF.json',rows);save(H/'ALL_D_DAILY.json',daily);save(H/'RECOGNITION_SCOPE_EXCEPTIONS.json',errors)
    summary=[]
    for window in refs:
        rr=[r for r in daily if r['window']==window];held=[r for r in rr if not r['actual_flat']]
        sums={k:sum((D(r[k])for r in rr),Z)for k in ['all_exit_inventory','loss_or_unproven_exit_inventory','profitable_inventory_kept_under_old_stock_protection']}
        summary.append(dict(window=window,D_closes=len(rr),held_D_closes=len(held),flat_D_closes=len(rr)-len(held),classified_stock_closes=sum(r['old_held_stocks']for r in rr),
            repeated_yuan_CLOSE_sums=sums,mean_over_held_D_closes={k:v/len(held)if held else None for k,v in sums.items()},
            unknown_stock_closes=sum(r['groups']['unknown']['stocks']for r in rr),profit_stock_closes=sum(r['groups']['profit']['stocks']for r in rr),loss_stock_closes=sum(r['groups']['loss']['stocks']for r in rr),zero_stock_closes=sum(r['groups']['zero']['stocks']for r in rr),
            scope='Repeated daily stock exposures, not unique capital, avoidable loss or simulated action.'))
    save(H/'SUMMARY.json',summary)
    transitions={'2022-01-20','2022-09-30','2026-03-23','2026-06-08'};save(H/'FOUR_V1_D_TRANSITION_SNAPSHOTS.json',[r for r in daily if r['day']in transitions])
    assert all(sha(p)==h for p,h in pre.items());save(H/'SOURCE_MANIFEST.json',{str(p):sha(p)for p in sources})
    save(H/'COMPLETED.json',dict(status='PURE_SAVED_LEDGER_CURRENT_STOCK_CAMPAIGN_ASOF',D_closes=len(daily),stock_closes=len(rows),new_models=0,new_accounts=0,new_RiskBooks=0,terminal_layer_net_used=False,all_original_inventory_bridges_exact_within_1e_8_yuan=True,stock_campaign_dividend_recognition_exceptions=len(errors),source_post_exact=True))
    print('ALL_V1_D_ASOF_READY',len(daily),len(rows))
if __name__=='__main__':main()
