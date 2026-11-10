"""Reconcile stored fills independently; do not import the account engine."""
from pathlib import Path
import json,hashlib,datetime
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'results/v0'
fr=json.loads((HERE/'freeze.json').read_text())
for p,h in fr['hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
assert hashlib.sha256(Path(fr['native_path']).read_bytes()).hexdigest()==fr['native_sha256']
s=pd.read_csv(OUT/'summary.csv');bars=pd.read_parquet(HERE/'inputs/AU0-main.parquet').loc['2025-01-02':'2026-10-13'];checks=[]
for _,row in s.iterrows():
    base=OUT/'accounts'/row.id;fills=pd.read_csv(base/'fills.csv');trades=pd.read_csv(base/'trades.csv');daily=pd.read_parquet(base/'daily.parquet')
    cash=1.;quantity=0.;nav=[];fee_sum=slip_sum=0.
    for dt,b in bars.iterrows():
        ff=fills.loc[fills.date.eq(str(dt.date()))]
        for _,fill in ff.iterrows():
            sign=1 if fill.side=='buy' else -1
            assert (sign*(fill.price-fill.raw_price))>=0
            cash-=sign*fill.quantity*fill.price+fill.fee;quantity+=sign*fill.quantity;fee_sum+=fill.fee;slip_sum+=fill.slippage
            if fill.signal_date not in ['preset_window_start','preset_window_end']:
                signal=pd.Timestamp(fill.signal_date);lag=bars.index.get_loc(dt)-bars.index.get_loc(signal)
                assert lag==fr['scenarios'][row.scenario]['delay'],(row.id,dt,lag)
                assert fill.raw_price==bars.loc[dt,'open']
            else:assert (fill.raw_price==b.close if fill.signal_date=='preset_window_end' else fill.raw_price==b.open)
        nav.append(cash+quantity*b.close)
    np.testing.assert_allclose(nav,daily.nav,rtol=1e-12,atol=1e-12)
    assert abs(quantity)<1e-12
    dd=1-np.array(nav)/np.maximum.accumulate(np.r_[1.,nav])[1:]
    assert abs(dd.max()-row.max_drawdown)<1e-12 and abs(nav[-1]-1-row.net_return)<1e-12
    assert abs(fee_sum-row.fees)<1e-12 and abs(slip_sum-row.slippage)<1e-12
    ret=[]
    for j,(_,trade) in enumerate(trades.iterrows()):
        buy,sell=fills.iloc[2*j],fills.iloc[2*j+1];assert buy.side=='buy' and sell.side=='sell'
        paid=buy.quantity*buy.price+buy.fee;received=sell.quantity*sell.price-sell.fee
        assert abs(received/paid-1-trade.net_return)<1e-12;ret.append(received/paid)
        assert pd.Timestamp(trade.endpoint)<pd.Timestamp(trade.entry_date)
    assert abs(np.prod(ret)-nav[-1])<1e-12
    checks.append(dict(account=row.id,days=len(daily),trades=len(trades),fills=len(fills),passed=True))
for mode in ['M','S']:
 for scenario in fr['scenarios']:
    a=pd.read_parquet(OUT/'accounts'/f'B2_{mode}_{scenario}'/'daily.parquet');b=pd.read_parquet(OUT/'accounts'/f'B23_{mode}_{scenario}'/'daily.parquet');pd.testing.assert_frame_equal(a,b)
ep=pd.read_csv(OUT/'signal-events-period.csv');assert (pd.to_datetime(ep.recognized)>=pd.to_datetime(ep.endpoint)).all()
assert len(s)==39 and all(x['days']==428 for x in checks)
result=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,accounts=checks,frozen_files_unchanged=len(fr['hashes']),native_unchanged=True,confirmed_signal_not_backdated=True,B2_B23_all_scenarios_paths_identical=True,initial_cash=1.,initial_position=0.,window_days=428,
    limits='Independent stored-fill bookkeeping; does not certify continuous contract roll construction or true exchange executability.')
with (OUT/'independent-audit.json').open('x') as fp:json.dump(result,fp,ensure_ascii=False,indent=2);fp.write('\n')
print('independent audit passed:',len(checks),'accounts,',sum(x['fills'] for x in checks),'fills')
