"""Secondary constraints and selected-vs-population diagnostics, no new trades."""
from common import *
import pandas as pd
import collections

def main():
 out=HERE/'enriched';out.mkdir(exist_ok=False);df=pd.read_parquet(HERE/'detail/all-daily-traces.parquet');meta=read(OLD/'inputs-v2/metadata.json');manifest={r['series_id']:r for r in read(OLD/'inputs-v2/input-manifest.json')['series']};rules=read(OLD/'inputs-v2/market-rules.json');cal=sorted(set(x[:10] for x in rules['calendars']['A'] if x[:10]<=END));di={d:i for i,d in enumerate(cal)}
 for sid in IDS:
  r=manifest[sid];p=Path(r['raw']['path']);assert sha(p)==r['raw']['sha256'];raw=pd.read_parquet(p);raw.index=pd.DatetimeIndex(pd.to_datetime(raw.trade_date if 'trade_date' in raw else raw.index));q=df.symbol.eq(sid)
  price=df.loc[q,'date'].map(raw.close.rename(index=lambda d:str(d.date())));minimum=[]
  for day in df.loc[q,'date']:
   v=[v for v in rules['quantity_versions'][sid] if v['from']<=day and (v['to'] is None or day<=v['to'])];assert len(v)==1;minimum.append(v[0]['rule']['buy_minimum'])
  df.loc[q,'raw_close']=price.to_numpy();df.loc[q,'minimum_buy_shares']=minimum
 df['minimum_lot_notional']=df.raw_close*df.minimum_buy_shares;df['initial_cap_upper']=df.nav*.15;df['minimum_lot_exceeds_cap']=df.minimum_lot_notional>df.initial_cap_upper;df['minimum_lot_exceeds_unlost_cap']=df.minimum_lot_notional>150000
 df.to_parquet(out/'all-daily-traces.parquet',index=False)
 q=df.loc[df.event&df.account.eq('IX__S0_base')];summary=q.groupby('symbol').agg(events=('event','size'),cap_infeasible=('minimum_lot_exceeds_cap','sum'),even_unlost_cap_infeasible=('minimum_lot_exceeds_unlost_cap','sum')).reset_index();summary.to_csv(out/'minimum-lot-summary.csv',index=False)
 camps=pd.read_csv(SRC/'analysis/campaigns.csv');closed=camps.loc[camps.closed].copy();closed['exit_date']=closed.exit_at.str[:10];exits={(aid,day):set(g.symbol) for (aid,day),g in closed.groupby(['account','exit_date'])}
 snaps=read(HERE/'detail/rejected-event-snapshots.json');lookup={(r.account,r.date,r.symbol):r for _,r in df.iterrows()};rs=[]
 for x in snaps:
  row=lookup[x['account'],x['date'],x['symbol']];n=di[x['date']]+1;nxt=cal[n] if n<len(cal) else None;ex=exits.get((x['account'],nxt),set());removed=[o for o in x['occupancy'] if o['exit_latched'] and o['symbol'] in ex];remain=[o for o in x['occupancy'] if o not in removed];sect=meta[x['symbol']]['sector_id'];cap=6 if x['allocation']=='S1' else 2;maxsec=1 if x['allocation']=='S1' else 3
  fit=len(remain)<6 and sum(o['sector_id']==sect for o in remain)<cap and (sect in {o['sector_id'] for o in remain} or len({o['sector_id'] for o in remain})<maxsec)
  x.update(raw_close=row.raw_close,minimum_buy_shares=row.minimum_buy_shares,minimum_lot_notional=row.minimum_lot_notional,initial_cap_upper=row.initial_cap_upper,minimum_lot_exceeds_cap=bool(row.minimum_lot_exceeds_cap),pending_exit_count=sum(o['exit_latched'] for o in x['occupancy']),next_market_day=nxt,actually_closed_latched_next_day=[o['symbol'] for o in removed],capacity_fits_after_actual_latched_exits=bool(fit),has_warm_or_weaker_unlatched_hold=any(o['has_position'] and not o['exit_latched'] and o['grade'] is not None and o['grade']<2 for o in x['occupancy']))
  rs.append(x)
 write(out/'rejected-event-snapshots.json',rs)
 rows=[]
 for sid in IDS:
  a=[x for x in rs if x['account']=='IX__S0_base' and x['symbol']==sid]
  rows.append(dict(symbol=sid,blocked_events=len(a),with_pending_exit=sum(x['pending_exit_count']>0 for x in a),capacity_relief_after_actual_next_exit=sum(x['capacity_fits_after_actual_latched_exits'] for x in a),capacity_relief_and_minlot_fits=sum(x['capacity_fits_after_actual_latched_exits'] and not x['minimum_lot_exceeds_cap'] for x in a),has_lower_than_warm_held=sum(x['has_warm_or_weaker_unlatched_hold'] for x in a)))
 pd.DataFrame(rows).to_csv(out/'capacity-relief-summary.csv',index=False)
 # Deterministic explanatory cases, selected after outcomes and never used in rules.
 cases=[];wanted=[('688256.SH','2023-03-13'),('688256.SH','2025-01-07'),('300308.SZ','2024-02-06')]
 for sid in IDS:
  a=[x for x in rs if x['account']=='IX__S0_base' and x['symbol']==sid and x['date']>='2025-01-01' and x['sector_rank_all_up']==1]
  if a:wanted.append((sid,a[0]['date']))
 for sid,day in wanted:
  x=next(x for x in rs if x['account']=='IX__S0_base' and x['symbol']==sid and x['date']==day);cases.append(x)
 write(out/'explanatory-cases.json',cases)
 labels=pd.read_parquet(HERE/'cohort-v1/all-event-labels.parquet');assert not labels.duplicated(['date','symbol']).any();prof=pd.read_csv(SRC/'analysis/entry-profiles.csv');prof=prof.loc[prof.account.str.endswith('_base')].copy();prof['date']=prof.decision_date
 merged=prof.merge(labels,on=['date','symbol'],how='left',validate='many_to_one',indicator=True,suffixes=('','_label'));assert merged['_merge'].eq('both').all();merged['holding_sessions']=merged.apply(lambda x:di.get(str(x.entry_at)[:10],np.nan),axis=1)
 cc={(x.account,x.symbol,x.entry_at):x for _,x in camps.iterrows()};merged['holding_sessions']=[(di[str(cc[(x.account,x.symbol,x.entry_at)].exit_at)[:10]]-di[x.entry_at[:10]]) if cc[(x.account,x.symbol,x.entry_at)].closed else None for _,x in merged.iterrows()]
 merged.to_parquet(out/'selected-event-labels.parquet',index=False);stats=[]
 for scope,start in [('full','2015-01-01'),('recent','2023-01-01')]:
  for (aid,mode,alloc),g in merged.loc[merged.date.ge(start)].groupby(['account','entry_scheme','allocation']):
   for horizon in [21,63]:
    v=g[f'ret{horizon}'].dropna();early=g.loc[g.holding_sessions.lt(horizon)&g[f'ret{horizon}'].notna()];futuretail=early.loc[early[f'ret{horizon}'].ge(.3)]
    stats.append(dict(scope=scope,account=aid,mode=mode,allocation=alloc,horizon=horizon,actual_cycles=len(g),complete_labels=len(v),fixed_endpoint_mean=v.mean(),fixed_endpoint_median=v.median(),fixed_endpoint_p90=v.quantile(.9),fixed_endpoint_up_fraction=v.gt(0).mean(),median_actual_holding_sessions=g.holding_sessions.median(),closed_actual_mean_return=g.loc[g.closed,'net_return'].mean(),closed_actual_median_return=g.loc[g.closed,'net_return'].median(),early_closed_count=len(early),future_tail_after_early_exit=len(futuretail),those_actual_below_tail=int(futuretail.net_return.lt(.3).sum())))
 pd.DataFrame(stats).to_csv(out/'selected-price-vs-exit.csv',index=False);write(out/'selected-price-vs-exit.json',stats)
 write(out/'receipt.json',dict(recorded_at=now(),passed=True,new_accounts=0,actual_cycle_price_labels_joined=len(merged),unmatched_actual_cycles=0,price_label_interpretation='potential subsequent price paths, no assumed cash or feasible trades; not a zero-cost backtest',capacity_relief_interpretation='only a capacity fact after actual next-day preexisting exits; no guarantee of priority, money or execution',minimum_lot_interpretation='frozen quantity mapping times observed raw close; excluding fees, an optimistic lower bound'))
 print(summary.to_string(index=False));print(pd.DataFrame(rows).to_string(index=False));print(pd.DataFrame(stats).query("scope=='recent' and allocation=='S0'").to_string(index=False),flush=True)
 print('CASE LOTS',[(x['date'],x['name'],x['minimum_lot_notional'],x['initial_cap_upper'],x['capacity_fits_after_actual_latched_exits']) for x in cases],flush=True)
if __name__=='__main__':main()
