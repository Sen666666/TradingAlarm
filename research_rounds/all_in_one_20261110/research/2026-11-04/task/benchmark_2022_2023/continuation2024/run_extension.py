"""Two authorized2024 continuation benchmarks only; original parents read-only."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
import csv,hashlib,json
import numpy as np,pandas as pd
import extension_adapter as A
O,P,I=A.O,A.P,A.O/'inputs'
NAMES=('BUY_HOLD','MA63_90')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).parent.mkdir(exist_ok=True,parents=True);Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def period(frame,begin,end,base):
    z=frame[frame.date.between(begin,end)];assert len(z)
    nav=z.NAV.astype(float).to_numpy();b=float(base);peak=np.maximum.accumulate(np.r_[b,nav])[1:]
    return dict(start=str(z.date.iloc[0]),end=str(z.date.iloc[-1]),starting_NAV=b,ending_NAV=float(nav[-1]),return_pct=(nav[-1]/b-1)*100,period_DD_pct=float((1-nav/peak).max()*100))
def concatenate_daily(name,tail):
    old=P/'daily'/f'{name}.csv';raw=old.read_bytes();assert raw.endswith(b'\n')
    header=next(csv.reader(old.open()));assert list(tail.columns)==header
    combined=O/'daily_2022_2024'/f'{name}.csv';combined.parent.mkdir(exist_ok=True)
    combined.write_bytes(raw+tail.to_csv(index=False,header=False).encode())
    assert combined.read_bytes()[:len(raw)]==raw
    return combined
def main():
    assert not(O/'RESULTS_2024.json').exists(),'completed continuation never silently repeated'
    available=read(O/'INPUT_AVAILABILITY.json');assert available['available'] and available['before_new_account_events']
    for f,h in dict(available['sources'],**available['inputs']).items():assert sha(f)==h,('source/input drift',f)
    assert sha(O/'PARENT_STATE.json')==available['parent_state_sha256']
    A.write_sources()
    local=[Path(__file__),O/'extension_adapter.py',O/'CONTINUATION_CARD.txt',O/'INPUT_AVAILABILITY.json',O/'PARENT_STATE.json',O/'derived_continuation_function.py.txt',O/'CONTINUATION_SOURCE_DIFF.patch']
    freeze={str(p):sha(p) for p in local};save(O/'RUN_FREEZE.json',dict(before_account_events=True,at_UTC=datetime.now(timezone.utc).isoformat(),sources=freeze))
    history=pd.read_csv(I/'510300_history.csv',index_col='date',parse_dates=True);calendar=pd.DatetimeIndex(pd.read_csv(I/'calendar2024.csv').date);actions=read(I/'510300_actions.json')
    results={};periods=[];phases=[];proof={};(O/'daily_2024').mkdir(exist_ok=True)
    for name in NAMES:
        parent=A.restore_parent(name)
        new,fills,orders,signals,terminal=A.simulate(history,calendar,actions,name,parent)
        assert len(new)==242 and new.date.iloc[0]=='2024-01-02' and new.date.iloc[-1]=='2024-12-31'
        assert not any(f['day']<'2024-01-02' for f in fills)
        if name=='BUY_HOLD':assert not fills and terminal['shares']==parent['shares']==200500
        new.to_csv(O/'daily_2024'/f'{name}.csv',index=False)
        combinedpath=concatenate_daily(name,new);full=pd.read_csv(combinedpath);assert len(full)==726
        for kind,values in [('fills',fills),('orders',orders),('signals',signals)]:
            old=read(P/'logs'/f'{name}_{kind}.json');combined=old+values
            assert combined[:len(old)]==old
            save(O/'logs_2024'/f'{name}_{kind}.json',values);save(O/'logs_2022_2024'/f'{name}_{kind}.json',combined)
        last=new.iloc[-1]
        terminal.update(previous_on=signals[-1]['on'],orderid=max([parent['orderid']]+[int(x['id'].rsplit('-',1)[1]) for x in orders if'id'in x]),
            NAV=last.NAV,global_peak=str(max([parent['global_peak']]+[D(v) for v in new.NAV])),cumulative_fee=last.cumulative_fee,cursor='2024-12-31',origin='2022-01-04')
        save(O/'logs_2024'/f'{name}_terminal.json',terminal)
        summary=A.BASE.metric(full)
        year=period(new,'2024-01-02','2024-12-31',parent['NAV'])
        year.update(fees_2024=float(new.fee.astype(float).sum()),dividend_accrued_2024=float(new.dividend_accrued.astype(float).sum()),
            dividend_paid_2024=float(new.dividend_paid.astype(float).sum()),worst_carried_global_DD_pct=float(new.drawdown.astype(float).max()*100),
            mean_exposure_pct=float((new.market_value.astype(float)/new.NAV.astype(float)).mean()*100),new_fills=len(fills))
        results[name]=dict(year2024=year,cumulative2022_2024=summary,execution_verified=False)
        oldperiod=pd.read_csv(P/'PERIODS.csv',dtype=str);oldperiod=oldperiod[oldperiod.benchmark.eq(name)]
        periods+=oldperiod.to_dict('records')
        nd=new.copy();nd['date_dt']=pd.to_datetime(nd.date)
        for freq in ('Y','Q','M'):
            for label,part in nd.groupby(nd.date_dt.dt.to_period(freq)):
                first=int(part.index[0]);base=parent['NAV'] if first==0 else D(new.NAV.iloc[first-1])
                value=period(new,part.date.iloc[0],part.date.iloc[-1],base);periods.append(dict(benchmark=name,frequency=freq,period=str(label),**value))
        for label,start,end in [('pre924','2024-01-02','2024-09-23'),('924_to_yearend','2024-09-24','2024-12-31')]:
            first=int(new.index[new.date.ge(start)][0]);base=parent['NAV'] if first==0 else D(new.NAV.iloc[first-1])
            phases.append(dict(benchmark=name,phase=label,**period(new,start,end,base)))
        detail=new[new.date.between('2024-09-02','2024-10-15')]
        detail.to_csv(O/f'{name}_924_daily.csv',index=False)
        signalwindow=[x for x in signals if '2024-09-02'<=x['day']<='2024-10-15']
        fillwindow=[x for x in fills if '2024-09-02'<=x['day']<='2024-10-15']
        orderwindow=[x for x in orders if '2024-09-02'<=x['at']<='2024-10-15']
        save(O/f'{name}_924_clock.json',dict(signals=signalwindow,fills=fillwindow,orders=orderwindow,event_labels_never_in_policy=True))
        proof[name]=dict(parent_cash=str(parent['cash']),parent_shares=parent['shares'],parent_NAV=str(parent['NAV']),
            parent_global_peak=str(parent['global_peak']),parent_cumulative_fee=str(parent['cumulative_fee']),parent_previous_on=parent['previous_on'],
            old484daily_bytes_prefix_exact=True,all_old_fill_order_signal_records_exact=True,old_days_recomputed=0,new_days=242,new_fills=len(fills),fresh_initialization=False)
    pd.DataFrame(periods).to_csv(O/'PERIODS_2022_2024.csv',index=False)
    q=pd.DataFrame(periods);q[q.frequency.eq('Q')].to_csv(O/'ALL_12_QUARTERS.csv',index=False)
    pd.DataFrame(phases).to_csv(O/'FIXED_924_PHASES.csv',index=False)
    # Only arithmetic continuation of the non-tradable index reference.
    oldindex=pd.read_csv(P/'daily/HS300_PRICE_INDEX.csv',dtype=str);ix=pd.read_csv(I/'HS300_2024_daily.csv');units=D(oldindex.synthetic_units.iloc[-1]);indexnav=ix.close.map(lambda v:units*D(str(v)))
    indexref=pd.DataFrame(dict(date=ix.date,NAV=indexnav.map(str),index_close=ix.close,reference_only=True));indexref.to_csv(O/'HS300_2024_REFERENCE.csv',index=False)
    cumulative=np.r_[oldindex.NAV.astype(float).to_numpy(),indexref.NAV.astype(float).to_numpy()];peak=np.maximum.accumulate(np.r_[1e6,cumulative])[1:]
    indexstats=dict(reference_only=True,year2024_return_pct=(float(indexnav.iloc[-1])/float(oldindex.NAV.iloc[-1])-1)*100,
        cumulative_return_pct=(float(indexnav.iloc[-1])/1e6-1)*100,cumulative_DD_pct=float((1-cumulative/peak).max()*100),no_new_trading_simulation=True)
    for f,h in dict(available['sources'],**available['inputs']).items():assert sha(f)==h
    for f,h in freeze.items():assert sha(f)==h
    assert sha(O/'PARENT_STATE.json')==available['parent_state_sha256']
    save(O/'PARENT_AND_OVERLAP_PROOF.json',dict(passed=True,details=proof,old_source_state_and_input_SHA_unchanged=True,body_inverse_exact=True))
    save(O/'RESULTS_2024.json',dict(scope='two frozen own-state benchmark continuations only; no new PVR path',calendar=['2024-01-02','2024-12-31'],new_days_per_account=242,
        cumulative_dates=['2022-01-04','2024-12-31'],cumulative_days=726,no_annual_reset=True,results=results,HS300_reference=indexstats,independent_audit='pending'))
    print(json.dumps(dict(results=results,HS300_reference=indexstats),ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
