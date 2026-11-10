"""Independent scalar checks of explanatory joins, prices and source identity."""
from common import *
import pandas as pd

def main():
 checks=[];labels=pd.read_parquet(HERE/'cohort-v1/all-event-labels.parquet');cal=pd.DatetimeIndex(sorted(set(x[:10] for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A'] if x[:10]<=END)));ci={d:i for i,d in enumerate(cal)}
 stocks=sorted(labels.symbol.unique());sample=sorted(set(IDS+[stocks[i] for i in np.linspace(0,len(stocks)-1,12,dtype=int)]));n=0;missing=0
 for sid in sample:
  f=pd.read_parquet(SRC/'signals'/f'{sid}.parquet');g=labels.loc[labels.symbol.eq(sid)]
  for k in sorted(set([0,len(g)//2,len(g)-1])):
   r=g.iloc[k];dt=pd.Timestamp(r.date);i=ci[dt]
   for h in [21,63]:
    expected=np.nan
    if i+h<len(cal) and cal[i+1] in f.index and cal[i+h] in f.index:expected=float(f.loc[cal[i+h],'close']/f.loc[cal[i+1],'open']-1)
    value=r[f'ret{h}']
    if pd.isna(expected):assert pd.isna(value);missing+=1
    else:assert abs(value-expected)<1e-12,(sid,r.date,h,value,expected)
    n+=1
 checks.append(dict(name='future_price_labels_scalar_market_calendar_endpoints',passed=True,sources=len(sample),checks=n,unknown_endpoints_kept=missing))
 tr=pd.read_parquet(HERE/'enriched/all-daily-traces.parquet');assert len(tr)==919*3*16 and not tr.duplicated(['account','date','symbol']).any();assert not tr.loc[tr['mode'].eq('W23'),'event'].any();assert tr.loc[tr.event,'q'].notna().all();checks.append(dict(name='trace_rows_and_zero_strict_events',passed=True,rows=len(tr)))
 actual=pd.read_csv(HERE/'detail/actual-focus-campaigns.csv');src=pd.read_csv(SRC/'analysis/campaigns.csv');old=pd.read_csv(OLD/'analysis-v2/campaigns.csv');old.account='E0__'+old.account;source=pd.concat([src,old],ignore_index=True)
 for _,a in actual.iterrows():
  q=source.loc[source.account.eq(a.account)&source.symbol.eq(a.symbol)&source.entry_at.eq(a.entry_at)];assert len(q)==1;b=q.iloc[0];assert abs(a.net_pnl-b.net_pnl)<1e-8 and abs(a.net_return-b.net_return)<1e-12
 assert not actual.loc[actual.entry_at.str[:10].ge('2025-01-01')].shape[0]
 checks.append(dict(name='actual_cycles_identical_to_audited_sources_and_no_2025_plus_positions',passed=True,cycles=len(actual)))
 snaps=read(HERE/'enriched/rejected-event-snapshots.json');bykey={(r.account,r.date,r.symbol):r for _,r in tr.iterrows()}
 for x in snaps:
  q=bykey[x['account'],x['date'],x['symbol']];assert bool(q.event) and q.q is True and not q.held and not q.accepted
  assert x['minimum_lot_exceeds_cap']==(x['raw_close']*x['minimum_buy_shares']>x['initial_cap_upper'])
 checks.append(dict(name='rejected_snapshot_identity_and_raw_minimum_lot_bound',passed=True,snapshots=len(snaps)))
 paths=read(SRC/'complete.json')['artifacts'];bad=[p for p,h in paths.items() if sha(ROOT/p)!=h];assert not bad,bad
 reg=read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in reg.items());initial=read(HERE/'initial-freeze.json')['sha256'];assert all(sha(ROOT/p)==h for p,h in initial.items())
 checks.append(dict(name='all_old_round_and_pinned_inputs_unchanged',passed=True,old_round_files=len(paths),E0_R_R1_files=len(reg),initial_pins=len(initial)))
 write(HERE/'validation.json',dict(recorded_at=now(),passed=True,new_accounts=0,old_results_unchanged=True,algorithm_changes=0,checks=checks));print(checks,flush=True)
if __name__=='__main__':main()
