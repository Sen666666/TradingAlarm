"""Tie predeclared ex-post winner windows to actual holdings and gate receipts."""
from pathlib import Path
import collections,json
import pandas as pd,numpy as np
from build_inputs import HERE,read,write,now,ref

def reason(counts,participated):
 if participated:return 'actual_position_participation'
 if counts.get('reservation_accepted',0) or counts.get('pending_buy_not_yet_filled',0):return 'buy_cancelled_or_unfilled'
 actionable={k:v for k,v in counts.items() if k.startswith(('selection_rejected:','execution_rejected:')) or k=='waiting_not_selected'}
 if actionable:return max(actionable,key=lambda k:(actionable[k],k))
 if counts.get('sector_not_valid'):return 'sector_not_valid'
 if counts.get('stock_not_confirmed'):return 'stock_not_confirmed'
 return max(counts,key=counts.get) if counts else 'current_cap_not_selected_or_identity_unknown'

def main():
 out=HERE/'misses-v2';out.mkdir(exist_ok=False)
 details={(x['account'],x['key']):x for x in read(HERE/'funnel-v2/target-counters.json')}
 contributions=pd.read_csv(HERE/'analysis-v2/daily-stock-contributions.csv');contributions.date=pd.to_datetime(contributions.date)
 curves=pd.read_csv(HERE/'analysis-v2/curves.csv');curves.date=pd.to_datetime(curves.date);nav={(a,str(d.date())):n for a,d,n in curves[['account','date','nav']].itertuples(index=False,name=None)}
 contributions['weight']=[v/nav[(a,str(d.date()))] for a,d,v in contributions[['account','date','market_value']].itertuples(index=False,name=None)]
 bycon={key:part for key,part in contributions.groupby(['account','symbol'],sort=False)}
 fills=pd.read_csv(HERE/'analysis-v2/fills.csv');fills['date']=pd.to_datetime(fills['at'],utc=True).dt.tz_convert('Asia/Shanghai').dt.tz_localize(None).dt.normalize()
 byfill={key:part for key,part in fills.groupby(['account','security_id'],sort=False)}
 dates=pd.DatetimeIndex(pd.to_datetime([x[:10] for x in read(HERE/'inputs-v2/market-rules.json')['decision_cutoffs']]))
 annual=read(HERE/'funnel-v2/qualified-annual-top20.json');rawtop=read(HERE/'opportunities-v2/annual-top20.json')
 episodes=read(HERE/'opportunities-v2/structural-winners.json');windows={}
 for x in rawtop+annual:
  key=f'annual:{x["symbol"]}:{int(x["year"])}';windows[key]=dict(x,window_type='annual',key=key,start_date=max(str(x['origin_date']),'2015-01-01'),end_date=str(x['last_observation']),price_return=x['adjusted_price_return'],closed=None)
 for x in episodes:
  if x['current_cap_disposition']!='selected':continue
  key='episode:'+x['episode_id'];windows[key]=dict(x,window_type='episode',key=key,start_date=max(x['entry_date'],'2015-01-01'),price_return=x['signal_price_return'])
 result=[];snapshots=[]
 for (aid,key),d in details.items():
  if key not in windows:continue
  w=windows[key];sid=w['symbol'];start=pd.Timestamp(w['start_date']);end=pd.Timestamp(w['end_date']);days=int(((dates>=start)&(dates<=end)).sum())
  cs=bycon.get((aid,sid));f=byfill.get((aid,sid))
  part=cs.loc[cs.date.between(start,end)] if cs is not None else pd.DataFrame()
  trade=f.loc[f.date.between(start,end)] if f is not None else pd.DataFrame()
  buys=trade.loc[trade.side=='buy'] if not trade.empty else trade
  held=part.loc[part.shares>0] if not part.empty else part
  participates=bool(len(held) or len(trade));first=str(held.date.min().date()) if len(held) else str(buys.date.min().date()) if len(buys) else None
  delay=max(0,int(dates.searchsorted(pd.Timestamp(first))-dates.searchsorted(start))) if first else None
  row=dict(account=aid,window_type=w['window_type'],key=key,symbol=sid,name=w['name'],industry=w['industry'],
   start_date=str(start.date()),end_date=str(end.date()),closed=w['closed'],year=int(w['year']) if 'year' in w else None,
   entry_recognition_date=w.get('entry_date'),carry_in_before_account=w.get('carry_in_before_account',False),partial_listing_or_source_year=w.get('partial_listing_or_source_year',False),
   price_return=float(w['price_return']),participated=participates,holding_days=len(held),window_sessions=days,holding_day_fraction=len(held)/days if days else 0,
   first_participation=first,delay_sessions=delay,new_buy_fills=len(buys),buy_gross=float(buys.gross_cny.sum()) if len(buys) else 0,
   window_net_contribution=float(part.net_contribution.sum()) if len(part) else 0,mean_account_weight=float(part.weight.sum()/days) if days and len(part) else 0,
   primary_reason=reason(d['counts'],participates),reason_candidate_days=d['counts'],eligibility_component_days=d['component_counts'],
   rank_fallback_days=d['rank_fallback_days'],first_q_true=d['first_q_true'],current_cap_disposition=w['current_cap_disposition'],
   raw_sample_historical_A_identity='BSE listing not verified for nonqualified names' if sid.endswith('.BJ') and w['current_cap_disposition']!='selected' else 'research proxy / documented qualified BSE starts')
  result.append(row)
  if aid.endswith('_base') and d['first_q_true']:snapshots.append(dict(account=aid,key=key,symbol=sid,**d['first_q_true']))
 write(out/'windows.json',result)
 simple=[{k:v for k,v in x.items() if k not in ('reason_candidate_days','eligibility_component_days','first_q_true')} for x in result]
 pd.DataFrame(simple).to_csv(out/'windows.csv',index=False,encoding='utf-8-sig');write(out/'first-opportunity-snapshots.json',snapshots)
 summaries=[]
 for aid in sorted({x['account'] for x in result}):
  for typ in ['annual','episode']:
   xs=[x for x in result if x['account']==aid and x['window_type']==typ and x['current_cap_disposition']=='selected']
   summaries.append(dict(account=aid,type=typ,windows=len(xs),participated=sum(x['participated'] for x in xs),missed=sum(not x['participated'] for x in xs),
    missed_reasons=dict(collections.Counter(x['primary_reason'] for x in xs if not x['participated'])),mean_window_weight=float(np.mean([x['mean_account_weight'] for x in xs])) if xs else None))
 write(out/'summary.json',dict(recorded_at=now(),rows=summaries,notes=[
  'Price windows are outcome diagnostics, not executable strategy returns. Open structure windows remain open.',
  'Annual participation can be carried holdings from a prior year; holding-day coverage, weight and same-window actual contribution prevent calling one late purchase full capture.',
  'Candidate-day reasons are factual gates. Removing a gate does not grant all missed returns without capital or risk cost.',
  'Primary missed reason prioritizes logged actionable blocking days; if an order was accepted but no position traded, classify cancelled/unfilled; full counters retained.',
  'Unverified nonqualified BSE history is not ranked as an executable A opportunity. Full raw annual outcome table remains archived.']))
 print({'diagnostic_windows':len(result),'base_snapshots':len(snapshots)},flush=True)

if __name__=='__main__':main()
