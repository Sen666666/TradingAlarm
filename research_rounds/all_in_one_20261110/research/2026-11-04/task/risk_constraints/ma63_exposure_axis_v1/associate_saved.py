"""Fixed benchmark/old-account date joins only, no model or account execution."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import json,hashlib
import pandas as pd
getcontext().prec=50
H=Path(__file__).resolve().parent;T=H.parent.parent;R=T/'risk_constraints';B=T/'benchmark_2022_2023';Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def resources(r):
    nav=D(r['nav']);risk=D(str(r['pool_probe'][1]))+D(str(r['pool_confirmed'][1]))
    return dict(NAV=nav,inventory=D(r['inventory']),exposure_pct=D(r['inventory'])/nav*100,nominal_risk=risk,nominal_risk_pct=risk/nav*100,
        available_cash=D(r['available']),available_cash_pct=D(r['available'])/nav*100,order_reserved=D(r['order_reserved']),settlement_locked=D(r['settlement_locked']),
        payable=D(r['payable']),sale_receivable=D(r['sale_receivable']),dividend_receivable=D(r['dividend_receivable']),held_stocks=len(r['positions']),pending_original_sell_requests=len(r['pending_sells']),pending_strategy_intents=r['pending_intents'])
def aggregate(rows,lag=False):
    p='lag_'if lag else'';held=[r for r in rows if D(r[p+'inventory'])>0];n=len(rows)
    def mean(key,rs=rows):return sum((D(r[p+key])for r in rs),Z)/len(rs)if rs else None
    return dict(days=n,held_days=len(held),flat_days=n-len(held),mean_inventory=mean('inventory'),mean_exposure_pct=mean('exposure_pct'),
        mean_nominal_risk=mean('nominal_risk'),mean_nominal_risk_pct=mean('nominal_risk_pct'),mean_available_cash_pct=mean('available_cash_pct'),
        held_days_mean_exposure_pct=mean('exposure_pct',held),held_days_mean_nominal_risk_pct=mean('nominal_risk_pct',held),
        peak_exposure_pct=max((D(r[p+'exposure_pct'])for r in rows),default=None),peak_nominal_risk_pct=max((D(r[p+'nominal_risk_pct'])for r in rows),default=None),
        mean_order_reserved=mean('order_reserved'),mean_settlement_locked=mean('settlement_locked'),mean_pending_strategy_intents=mean('pending_strategy_intents'),
        peak_pending_original_sell_requests=max((r[p+'pending_original_sell_requests']for r in rows),default=None),
        actual_wealth=sum((D(r['wealth_change'])for r in rows),Z)if lag else None,actual_buy_cash=sum((D(r['actual_buy_cash'])for r in rows),Z)if lag else None,
        actual_fees=sum((D(r['actual_fees'])for r in rows),Z)if lag else None,
        wealth_clock='attributed by previous known benchmarkCLOSE'if lag else'Not attributed by same-dayCLOSE. This aggregation is only a resource snapshot.')
def main():
    refs={'NO60':dict(money=R/'absolute_loss_2022_2023/NO60_2022_2023_DAILY.json',native=[R/'pvr_pool_results_2022/PVR_NO_CONFIRMED60_DAILY.json',R/'no60_continuation2023_finance/PVR_NO_CONFIRMED60_2023_DAILY.json']),
          'PVR':dict(money=R/'absolute_loss_2022_2023/PVR_2022_2023_DAILY.json',native=[R/'pvr_pool_results_2022/PVR_SLOT1_DAILY.json',R/'no60_continuation2023_finance/PVR_SLOT1_2023_DAILY.json'])}
    sources=[H/'PROTOCOL.txt',H/'associate_saved.py',B/'inputs/510300_history.csv',B/'prepare_inputs.py',B/'PROTOCOL.txt',B/'INPUT_FREEZE.json']+[p for r in refs.values()for p in [r['money'],*r['native']]];hashes={str(p):sha(p)for p in sources};save(H/'INPUT_FREEZE.json',dict(before_join=True,sources=hashes,scope='saved TR/MA63 + native snapshots/daywealth only; no new account/model/ledger'))
    hist=pd.read_csv(B/'inputs/510300_history.csv',index_col=0,parse_dates=True);assert hist.index.is_monotonic_increasing and hist.index.is_unique
    axes={};episodes={};last_axis=None;epid=None
    for i,(stamp,r)in enumerate(hist.iterrows()):
        day=str(stamp.date());prior=hist.iloc[i-1]if i else None;known=pd.notna(r.ma63)
        axis='unknown'if not known else'above'if r.signal_close>r.ma63 else'below'if r.signal_close<r.ma63 else'equal'
        assert bool(r['on'])==(axis=='above')
        slope='unknown'if not known or prior is None or pd.isna(prior.ma63)else'up'if r.ma63>prior.ma63 else'down'if r.ma63<prior.ma63 else'flat'
        if axis!=last_axis:
            epid=axis+':'+day;episodes[epid]=dict(episode_id=epid,price_axis=axis,raw_first_CLOSE=day,raw_last_CLOSE=day,
                true_upcross=(axis=='above'and last_axis in ['below','equal']),previous_axis=last_axis)
        episodes[epid]['raw_last_CLOSE']=day
        axes[day]=dict(day=day,signal_close=r.signal_close,MA63=r.ma63,price_axis=axis,MA63_slope=slope,axis_slope=axis+'_'+slope,episode_id=epid,previous_observed_CLOSE=None if i==0 else str(hist.index[i-1].date()))
        last_axis=axis
    joined=[];allgroups=[];months=[];episode_money=[];whole_wealth_residuals={}
    for arm,paths in refs.items():
        money=read(paths['money']);native={str(r['at'])[:10]:r for p in paths['native']for r in read(p)};assert len(money)==len(native)==484
        armrows=[];previous=None
        for i,r in enumerate(money):
            day=r['day'];a=axes[day];lag_a=axes[a['previous_observed_CLOSE']];snapshot=native[day];now=resources(snapshot)
            assert now['NAV']==D(r['NAV_end'])and now['inventory']==D(r['market_value'])and now['nominal_risk']==D(r['nominal_risk'])
            if previous is None:
                assert D(r['NAV_begin'])==D(1000000)and D(r['market_value'])==0 and D(r['actual_buy_cash'])==0
                lag=dict(now);lag.update(NAV=D(1000000),inventory=Z,exposure_pct=Z,nominal_risk=Z,nominal_risk_pct=Z,available_cash=D(1000000),available_cash_pct=D(100))
            else:lag=resources(previous)
            x=dict(arm=arm,day=day,benchmark_CLOSE=a,prior_benchmark_CLOSE=lag_a,**now,**{'lag_'+k:v for k,v in lag.items()},wealth_change=r['wealth_change'],actual_buy_cash=r['actual_buy_cash'],actual_fees=r['actual_fees'],ACT_at_OPEN=r['ACT_at_OPEN'],ACT_after_CLOSE=r['ACT_after_CLOSE'])
            armrows.append(x);joined.append(x);previous=snapshot
        for label in sorted({r['prior_benchmark_CLOSE']['axis_slope']for r in armrows}):allgroups.append(dict(arm=arm,clock='priorCLOSE_to_current_day',label=label,**aggregate([r for r in armrows if r['prior_benchmark_CLOSE']['axis_slope']==label],True)))
        for label in sorted({r['benchmark_CLOSE']['axis_slope']for r in armrows}):allgroups.append(dict(arm=arm,clock='sameCLOSE_snapshot_only',label=label,**aggregate([r for r in armrows if r['benchmark_CLOSE']['axis_slope']==label])))
        for month in sorted({r['day'][:7]for r in armrows}):
            rs=[r for r in armrows if r['day'].startswith(month)];monthgroups=[]
            for label in sorted({r['prior_benchmark_CLOSE']['axis_slope']for r in rs}):monthgroups.append(dict(label=label,**aggregate([r for r in rs if r['prior_benchmark_CLOSE']['axis_slope']==label],True)))
            assert sum((g['actual_wealth']for g in monthgroups),Z)==sum((D(r['wealth_change'])for r in rs),Z)
            months.append(dict(arm=arm,month=month,days=len(rs),original_month_wealth=sum((D(r['wealth_change'])for r in rs),Z),sameCLOSE_all_resources=aggregate(rs),prior_signal_groups=monthgroups))
        for eid,e in episodes.items():
            snap=[r for r in armrows if r['benchmark_CLOSE']['episode_id']==eid];following=[r for r in armrows if r['prior_benchmark_CLOSE']['episode_id']==eid]
            if not snap and not following:continue
            if e['price_axis']not in ['above','below','equal']:continue
            episode_money.append(dict(arm=arm,**e,left_censored_in_analysis=e['raw_first_CLOSE']<'2022-01-04',right_censored_at_source_end=e['raw_last_CLOSE']=='2023-12-29',
                snapshot_first=snap[0]['day']if snap else None,snapshot_last=snap[-1]['day']if snap else None,following_wealth_first=following[0]['day']if following else None,following_wealth_last=following[-1]['day']if following else None,
                sameCLOSE_snapshot=aggregate(snap),following_original_money=aggregate(following,True)))
        residual=sum((D(r['wealth_change'])for r in armrows),Z)-(D(money[-1]['NAV_end'])-D(money[0]['NAV_begin']))
        assert abs(residual)<D('.00000001');whole_wealth_residuals[arm]=residual
    save(H/'DAILY_ALIGNED.json',joined);save(H/'GROUPS_BY_AXIS_AND_SLOPE.json',allgroups);save(H/'ALL_24_MONTHS.json',months);save(H/'ALL_CONTINUOUS_RUNS.json',episode_money)
    assert len(months)==48 and all(sha(p)==v for p,v in hashes.items())
    save(H/'COMPLETED.json',dict(status='SAVED_MA63_EXPOSURE_CLOCK_ASSOCIATION',native_days_per_arm=484,arms=2,months_per_arm=24,source_post_exact=True,all_native_NAV_inventory_nominalrisk_fields_exact=True,all_month_group_wealth_bridges_exact=True,whole_saved_wealth_to_NAV_residuals=whole_wealth_residuals,whole_wealth_residual_limit_yuan='.00000001',new_models=0,new_accounts=0,new_ledgers=0,
        benchmark_formula='original510300 causalTR CLOSE/inclusive63mean; originalstoredfields, no recomputation',slope='diagnostic sign of successive storedMA63, flat separate; not original tradinggate',no_same_day_signal_PnL_attribution=True))
    print('MA63_EXPOSURE_AXIS_READY',len(joined),len(episode_money))
if __name__=='__main__':main()
