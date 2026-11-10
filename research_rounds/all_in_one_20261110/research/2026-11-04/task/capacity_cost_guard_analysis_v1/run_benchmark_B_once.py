"""One root-granted diagnostic reference; unchanged frozen simulate() body."""
from pathlib import Path
from datetime import datetime, timezone
import csv, gzip, hashlib, importlib.util, inspect, json, sys, time
from decimal import Decimal as D
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
TASK=HERE.parent
OUT=HERE/'benchmark_B_2025_26'
ORIGINAL=TASK/'benchmark_2022_2023'
OLD2024=ORIGINAL/'continuation2024'
R=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research')
CAL=TASK/'pvr_pool_feasibility/runs/2025_26/pair/daily.jsonl.gz'
START, END='2025-07-01','2026-06-30'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,z): Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n')
def read(p): return json.loads(Path(p).read_text())

def main():
    begin=time.monotonic()
    assert not OUT.exists(), 'No automatic rerun or overwrite of economic reference'
    OUT.mkdir(); I=OUT/'inputs'; I.mkdir(); (OUT/'daily').mkdir(); (OUT/'logs').mkdir()
    save(OUT/'GRANT_BINDING.json',dict(root_grant='One fresh1m 2025Jul1–2026Jun30 MA63/BH/CASH reference; unchanged simulate/protocol; no downloads, not a native-strategy optimization', received_before_any_account_event=True, source_card=str(HERE/'BENCHMARK_B_READINESS_AND_CARD.txt')))
    freeze=read(ORIGINAL/'RUN_FREEZE.json')
    assert sha(ORIGINAL/'run_benchmarks.py')==freeze['sources'][str(ORIGINAL/'run_benchmarks.py')]
    sys.path.insert(0,str(R)); import portfolio_data as P
    assets,_=P.load_assets({'USHJ510300':('broad','equity')}); a=assets['USHJ510300']
    raw=a['raw'].loc[:END].copy(); signal=a['signal'].loc[:END].copy()
    with gzip.open(CAL,'rt') as h: days=sorted({str(json.loads(x)['at'])[:10] for x in h})
    assert len(days)==242 and days[0]==START and days[-1]==END
    calendar=pd.DatetimeIndex(days); calendar.name='date'
    assert calendar.difference(raw.index).empty and raw.index.is_unique and raw.index.is_monotonic_increasing
    full=raw.copy(); full['volume_shares']=raw.volume*100; full['signal_close']=signal.close
    full['ma63']=signal.close.rolling(63,min_periods=63).mean()
    full['on']=full.signal_close.gt(full.ma63)&full.ma63.notna()
    full['adv20_prior_shares']=full.volume_shares.shift().rolling(20,min_periods=20).mean()
    overlap=[]
    for oldp in (ORIGINAL/'inputs/510300_history.csv',OLD2024/'inputs/510300_history.csv'):
        old=pd.read_csv(oldp,index_col='date',parse_dates=True)
        errors={c:float((old[c]-full.loc[old.index,c]).abs().max()) for c in old.columns if c!='on'}
        for c in ('open','close','high','low','volume','volume_shares'):
            assert np.array_equal(old[c].to_numpy(),full.loc[old.index,c].to_numpy()),(oldp,c)
        assert old.on.equals(full.loc[old.index,'on'])
        assert max(errors.values())<1e-12
        overlap.append(dict(source=str(oldp),rows=len(old),raw_price_volume_exact=True,on_exact=True,numeric_CSV_roundtrip_errors=errors))
    oldp=OLD2024/'inputs/510300_history.csv'; oldbytes=oldp.read_bytes()
    assert oldbytes.endswith(b'\n')
    tail=full.loc[full.index>'2024-12-31'].to_csv(header=False,float_format='%.15g').encode()
    (I/'510300_history.csv').write_bytes(oldbytes+tail)
    assert (I/'510300_history.csv').read_bytes()[:len(oldbytes)]==oldbytes
    full.loc[calendar].to_csv(I/'510300_B_daily.csv',float_format='%.15g')
    pd.DataFrame({'date':days}).to_csv(I/'calendar.csv',index=False)
    actions=read(OLD2024/'inputs/510300_actions.json')
    actions['dividends']+=sorted([dict(e,source='local EastmoneyF10',entitlement='previous-close inventory',known_for_signal='ex-date close only') for e in a['dividends'] if '2025-01-01'<=e['ex_date']<=END],key=lambda x:x['ex_date'])
    assert not [e for e in a['splits'] if e['date']<=END]
    actions['splits']=[]; save(I/'510300_actions.json',actions)
    spec=importlib.util.spec_from_file_location('frozen_ETF_baseline_B',ORIGINAL/'run_benchmarks.py')
    B=importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
    body=inspect.getsource(B.simulate)
    sources=[Path(__file__),HERE/'BENCHMARK_B_READINESS_AND_CARD.txt',HERE/'BENCHMARK_B_READINESS.json',OUT/'GRANT_BINDING.json',ORIGINAL/'run_benchmarks.py',ORIGINAL/'RUN_FREEZE.json',OLD2024/'inputs/510300_history.csv',OLD2024/'inputs/510300_actions.json',R/'portfolio_data.py',R/'portfolio-protocol.json',R/'data/tencent-sh510300-raw.json',R/'data/eastmoney-fhsp-510300.html',CAL]
    input_freeze=dict(at_UTC=datetime.now(timezone.utc).isoformat(),before_any_benchmark_simulation=True,scope=[START,END],days=len(days),first_possible_fill='2025-07-02 OPEN',initial_cash='1000000',no_annual_reset=True,old2024_serialized_prefix_bytes_exact=True,overlap=overlap,simulate_body_SHA256=hashlib.sha256(body.encode()).hexdigest(),dividends_in_window=[e for e in actions['dividends'] if START<=e['ex_date']<=END],splits=[],execution_verified=False,sources={str(p):sha(p) for p in sources},inputs={str(p):sha(p) for p in I.glob('*')})
    save(OUT/'INPUT_FREEZE.json',input_freeze)
    history=pd.read_csv(I/'510300_history.csv',index_col='date',parse_dates=True)
    assert history.index.is_unique and history['on'].dtype==bool
    save(OUT/'RUNNING_ONCE.json',dict(started_UTC=datetime.now(timezone.utc).isoformat(),root_granted=True,simulate_body_unchanged=True))
    results={}; completed=[]
    for name in ('BUY_HOLD','MA63_90'):
        daily,fills,orders,signals,last=B.simulate(history,calendar,actions,name)
        daily.to_csv(OUT/'daily'/f'{name}.csv',index=False)
        for kind,z in [('fills',fills),('orders',orders),('signals',signals),('terminal',last)]: save(OUT/'logs'/f'{name}_{kind}.json',z)
        results[name]=dict(B.metric(daily),fills=len(fills),execution_verified=False,execution_basis='unchanged raw OPEN daily proxy; dated halt/limit/queue/auction states unverified')
        completed.append(name); save(OUT/'COMPLETED_ARMS.json',completed)
    cash=pd.DataFrame(dict(date=days,NAV='1000000',cash='1000000',market_value='0',fee='0'))
    cash.to_csv(OUT/'daily/CASH.csv',index=False); results['CASH']=dict(B.metric(cash),reference_only=True)
    periods=[]
    for name in results:
        frame=pd.read_csv(OUT/'daily'/f'{name}.csv'); frame['date']=pd.to_datetime(frame.date); nav=frame.NAV.astype(float)
        for frequency in ('Y','Q','M'):
            for period,ix in frame.groupby(frame.date.dt.to_period(frequency)).groups.items():
                pos=list(ix); first=pos[0]; initial=1e6 if first==0 else float(nav.iloc[first-1]); last=float(nav.iloc[pos[-1]])
                peak=np.maximum.accumulate(np.r_[initial,nav.iloc[pos]])[1:]
                periods.append(dict(benchmark=name,frequency=frequency,period=str(period),start=str(frame.date.iloc[first].date()),end=str(frame.date.iloc[pos[-1]].date()),starting_NAV=initial,ending_NAV=last,return_pct=(last/initial-1)*100,period_DD_pct=float(np.max(1-nav.iloc[pos].to_numpy()/peak)*100)))
    pd.DataFrame(periods).to_csv(OUT/'PERIODS.csv',index=False)
    for p,h in dict(input_freeze['sources'],**input_freeze['inputs']).items(): assert sha(p)==h,('source/input changed',p)
    save(OUT/'RESULTS.json',dict(scope='independent simple references only; no native guard candidate',dates=[START,END],days=242,initial_cash=1000000,no_annual_reset=True,results=results,independent_audit='PENDING',seconds=time.monotonic()-begin))
    save(OUT/'OUTPUT_SHA256.json',{str(p):sha(p) for folder in ('daily','logs') for p in (OUT/folder).glob('*')})
    print(json.dumps(dict(seconds=time.monotonic()-begin,results=results),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
