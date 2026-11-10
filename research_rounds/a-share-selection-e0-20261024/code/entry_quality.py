"""Describe actual funded entries using information already known at the time.

RS sign, signal age and support distance are diagnostics, never new filters.
"""
from pathlib import Path
import collections
import pandas as pd,numpy as np
from build_inputs import HERE,read,write,now,ref

def clean(x):return None if x is None or not np.isfinite(float(x)) else float(x)
def main():
 out=HERE/'entry-quality-v2';out.mkdir(exist_ok=False)
 prep={x['series_id']:x for x in read(HERE/'prepared-v2/manifest.json')['series']};meta=read(HERE/'inputs-v2/metadata.json');cache={}
 def data(sid):
  if sid not in cache:
   p=prep[sid];state=pd.read_parquet(HERE/'prepared-v2'/p['files']['states']['path']);signal=pd.read_parquet(HERE/'prepared-v2'/p['files']['signal']['path'],columns=['adjustment_factor','raw_close'])
   cache[sid]=(state,signal,np.flatnonzero(state.entered.eq(1).to_numpy()))
  return cache[sid]
 profiles=[]
 for aid in [x['account'] for x in read(HERE/'analysis-v2/summary.json') if not x['account'].startswith('B0')]:
  obj=read(HERE/'accounts-v2'/(aid+'.json'));orders={x['order_id']:x for x in obj['audit_log'] if x['kind']=='reserve'}
  firstfill={(x['receipt']['security_id'],x['receipt']['at']):x for x in obj['audit_log'] if x['kind']=='fill' and x['receipt']['side']=='buy'}
  campaigns=[x for x in read(HERE/'analysis-v2/campaigns.json') if x['account']==aid]
  for c in campaigns:
   fill=firstfill[(c['symbol'],c['entry_at'])];order=orders[fill['order_id']];decision=pd.Timestamp(order['decision_at']).tz_localize(None).normalize();day=pd.Timestamp(c['entry_at']).tz_localize(None).normalize();sid=c['symbol'];sector=meta[sid]['sector_id']
   s,g,entered=data(sid);i=s.index.searchsorted(decision,side='right')-1;assert i>=0
   row=s.iloc[i];assert bool(row.target),'Actual reserve without E0 qualification'
   ss,sg,se=data(sector);j=ss.index.searchsorted(decision,side='right')-1;sr=ss.iloc[j] if j>=0 else None
   if not aid.startswith('T0'):assert sr is not None and bool(sr.target),'Sector-gated reserve without sector qualification'
   fresh=s.index[i]==decision;sectorfresh=sr is not None and ss.index[j]==decision
   rank=clean(row.rs) if fresh else None;sectorrank=clean(sr.rs) if sectorfresh else None
   fp=g.index.searchsorted(decision,side='right')-1;quote=float(g.raw_close.iloc[fp]);floor=float(row.floor)/float(g.adjustment_factor.iloc[fp])
   prior=s.index.searchsorted(day,side='left')-1;current_factor_i=g.index.searchsorted(day,side='right')-1
   known_beforefill=float(s.floor.iloc[prior])/float(g.adjustment_factor.iloc[current_factor_i]) if prior>=0 else np.nan
   risk=(quote-floor)/quote if fresh else None;age=i-entered[entered<=i][-1] if len(entered[entered<=i]) else None
   profiles.append(dict(account=aid,symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],decision_date=str(decision.date()),first_fill_at=c['entry_at'],
    closed=c['closed'],campaign_net_return=c['net_return'],campaign_net_pnl=float(c['net_pnl']),stock_rs=rank,sector_rs=sectorrank,
    stock_rs_missing_or_stale=rank is None,sector_rs_missing_or_stale=sectorrank is None,sector_up_at_reservation=bool(sr.target) if sr is not None else None,
    known_support_raw=clean(floor) if fresh else None,close_to_support_fraction=clean(risk),observations_since_latest_E0_entry=int(age) if age is not None else None,
    raw_open_below_prior_known_support=bool(float(fill['raw_open'])<=known_beforefill) if np.isfinite(known_beforefill) else None,
    prior_known_support_at_fill=clean(known_beforefill),first_raw_open=float(fill['raw_open'])))
 pd.DataFrame(profiles).to_csv(out/'funded-entry-profiles.csv',index=False,encoding='utf-8-sig');write(out/'profiles.json',profiles)
 summary=[]
 for aid in sorted({x['account'] for x in profiles}):
  rows=[x for x in profiles if x['account']==aid];valid=[x for x in rows if x['stock_rs'] is not None];rs=[x for x in rows if x['sector_rs'] is not None];risks=[x['close_to_support_fraction'] for x in rows if x['close_to_support_fraction'] is not None];ages=[x['observations_since_latest_E0_entry'] for x in rows if x['observations_since_latest_E0_entry'] is not None]
  summary.append(dict(account=aid,actual_funded_campaigns=len(rows),stock_RS_known=len(valid),stock_RS_nonpositive=sum(x['stock_rs']<=0 for x in valid),
   stock_RS_missing_or_stale=sum(x['stock_rs_missing_or_stale'] for x in rows),sector_RS_known=len(rs),sector_RS_nonpositive=sum(x['sector_rs']<=0 for x in rs),
   median_close_to_support=float(np.median(risks)) if risks else None,p90_close_to_support=float(np.quantile(risks,.9)) if risks else None,
   median_E0_age_observations=float(np.median(ages)) if ages else None,p90_E0_age_observations=float(np.quantile(ages,.9)) if ages else None,
   first_raw_open_below_known_support=sum(x['raw_open_below_prior_known_support'] is True for x in rows)))
 write(out/'summary.json',dict(recorded_at=now(),rows=summary,known_at_policy='Reservation close state; actual first open tested against support known before the open with the causally known theoretical ex-date coordinate.',
  not_new_strategy_filters=True,account_runs_added=0,source_account=ref(HERE/'accounts-v2/provenance.json'),note='This sector account executor has no separate first-open support veto; this differs from the prior single-asset reference engine. E0 state and all four controls remain identical.'))
 print(summary,flush=True)

if __name__=='__main__':main()
