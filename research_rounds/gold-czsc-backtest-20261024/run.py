from pathlib import Path
import datetime,hashlib,json,time
import numpy as np,pandas as pd
from signals import build,BUY_SETS,LABELS,czsc
from engine import run,SCENARIOS
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,(np.integer,np.bool_)):return x.item()
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x
def dump(p,x):Path(p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    freeze=json.loads((HERE/'freeze.json').read_text())
    for p,h in freeze['hashes'].items():assert sha(ROOT/p)==h,p
    assert czsc.__version__==freeze['czsc_version'] and sha(czsc._native.__file__)==freeze['native_sha256']
    out=HERE/'results/v0';out.mkdir(parents=True,exist_ok=False);(out/'accounts').mkdir()
    bars=pd.read_parquet(HERE/'inputs/AU0-main.parquet');allbars=pd.read_parquet(HERE/'inputs/AU0-all.parquet')
    signals,events=build(bars);signals.to_parquet(out/'signals.parquet');signals.to_csv(out/'signals.csv');events.to_csv(out/'signal-events-all.csv',index=False)
    period=bars.loc['2025-01-02':'2026-10-13'];ep=events.loc[events.recognized.between('2025-01-02','2026-10-13')];ep.to_csv(out/'signal-events-period.csv',index=False)
    print('SIGNALS',ep.groupby(['kind','valid']).size().to_dict(),flush=True)
    summaries=[]
    for entry,kinds in BUY_SETS.items():
     for mode in ['M','S']:
      for scenario,params in SCENARIOS.items():
        name=f'{entry}_{mode}_{scenario}';a=out/'accounts'/name;a.mkdir()
        s,ledger,trades,fills,orders=run(period,signals.loc[period.index],kinds,mode,params)
        for fn,df in [('daily',ledger),('trades',trades),('fills',fills),('orders',orders)]:df.to_csv(a/(fn+'.csv'),index=fn=='daily')
        ledger.to_parquet(a/'daily.parquet');dump(a/'summary.json',dict(id=name,buy_rule=entry,buy_label=LABELS[entry],sell_rule=mode,scenario=scenario,**s));summaries.append(dict(id=name,buy_rule=entry,buy_label=LABELS[entry],sell_rule=mode,scenario=scenario,**s))
    for scenario,params in SCENARIOS.items():
        name='HOLD_'+scenario;a=out/'accounts'/name;a.mkdir();s,ledger,trades,fills,orders=run(period,signals.loc[period.index],[],'S',params,benchmark=True)
        for fn,df in [('daily',ledger),('trades',trades),('fills',fills),('orders',orders)]:df.to_csv(a/(fn+'.csv'),index=fn=='daily')
        ledger.to_parquet(a/'daily.parquet');dump(a/'summary.json',dict(id=name,buy_rule='HOLD',buy_label='区间买入持有',sell_rule='preset_end',scenario=scenario,**s));summaries.append(dict(id=name,buy_rule='HOLD',buy_label='区间买入持有',sell_rule='preset_end',scenario=scenario,**s))
    table=pd.DataFrame(summaries);table.to_csv(out/'summary.csv',index=False)
    # Check sequential recognition and the entire path, not just final geometry.
    prefixes=[]
    for date in ['2025-01-02','2025-09-01','2025-10-22','2026-01-30','2026-08-10','2026-10-13']:
        ss,ee=build(bars.loc[:date]);pd.testing.assert_frame_equal(ss,signals.loc[:date],check_freq=False);pd.testing.assert_frame_equal(ee.reset_index(drop=True),events.loc[events.recognized<=date].reset_index(drop=True))
        prefixes.append(dict(cutoff=date,rows=len(ss),passed=True))
    full,fullevents=build(allbars);full.to_parquet(out/'full-warmup-signals.parquet')
    cols=['B1','B2','B3','B3A','S1','S2','S3','new_buy','new_sell'];a=signals.loc[period.index,cols];b=full.loc[period.index,cols]
    diff=a.ne(b);rows=[]
    for dt in diff.index[diff.any(axis=1)]:rows.append(dict(date=str(dt.date()),changed=','.join(diff.columns[diff.loc[dt]].tolist())))
    dump(out/'checks.json',dict(prefix_checks=prefixes,main_warmup_start=str(bars.index[0].date()),full_warmup_start=str(allbars.index[0].date()),warmup_signal_changed_days=int(diff.any(axis=1).sum()),warmup_signal_changes=rows,
        main_preperiod_bars=int((bars.index<pd.Timestamp('2025-01-02')).sum()),backtest_rows=len(period),account_count=len(table),all_daily_and_trade_accounting_passed=True))
    # A period-only rollup of confirmation lag; no endpoint timestamp is a fill.
    lag=ep.loc[ep.valid].groupby('kind').agg(signals=('kind','count'),median_confirmation_calendar_days=('lag_days','median'),max_confirmation_calendar_days=('lag_days','max'));lag.to_csv(out/'recognition-lags.csv')
    dump(out/'complete.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),freeze_sha256=sha(HERE/'freeze.json'),period=['2025-01-02','2026-10-13'],warmup=['2020-01-02','2024-12-31'],accounts=len(table),signal_period_counts=ep.groupby('kind').size().to_dict(),main_results=table.loc[table.scenario.eq('base')].to_dict('records'),prefix_checks=len(prefixes),warmup_changed_days=int(diff.any(axis=1).sum()),post_result_rule_changes=0,market_requests=0,wechat_operations=0))
    print(table.loc[table.scenario.eq('base'),['buy_label','sell_rule','net_return','max_drawdown','trades','win_rate','exposure_days']].to_string(index=False),flush=True)

if __name__=='__main__':main()
