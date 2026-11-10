"""Frozen winner windows and real rotation handoff, posthoc attribution only."""
from common_abcd import *
import collections,pandas as pd
from analyze_abcd import stream,account_path

def main():
 out=HERE/'diagnostics';out.mkdir(exist_ok=False);windows=read(OLD/'funnel-v2/qualified-annual-top20.json');assert len(windows)==240
 meta=read(OLD/'inputs-v2/metadata.json');campaign=pd.read_csv(HERE/'analysis/campaigns.csv');curves=pd.read_csv(HERE/'analysis/curves.csv');contrib=pd.read_csv(HERE/'analysis/daily-stock-contributions.csv')
 z=np.load(HERE/'prepared/dual-board.npz');dates=pd.DatetimeIndex(z['dates']);ids={str(s):j for j,s in enumerate(z['symbols'])};gate=z['gate'];raw=np.load(OLD/'h1/matrix.npz');closes=raw['close'];segments=raw['segment'];buy=read(HERE/'prepared/buy-events.json')
 targets={(w['symbol'],w['year']) for w in windows};named=['688256.SH','300308.SZ','300502.SZ'];targets.update((s,y) for s in named for y in range(2023,2027));trace=collections.defaultdict(lambda:dict(events=0,eligible=0,accepted=0,reasons=collections.Counter(),rejects=collections.Counter(),stock_gate_false=0,sector_gate_false=0,rotation_ban=0));daily={r['account']:{ } for r in read(HERE/'analysis/summary.json') if r['scenario']=='base'}
 for d in stream('daily'):
  if d['account'] in daily:daily[d['account']][d['at'][:10]]=d
 rotations=[];observations=collections.Counter()
 for d in stream('decisions'):
  if not d['account'].endswith('_base'):continue
  day=d['at'][:10];year=int(day[:4]);first=dict(d['first_rejected']);execution=dict(d['rejected']);mode=d['account'].split('__')[0];i=dates.get_loc(day)
  rot=d.get('rotation')
  if rot:
   for p in rot['observations']:observations[d['account'],p['kind']]+=1
   if rot['plan']:
    assert rot['plan']['confirmations']>=3 and rot['plan']['gap']>=2 and not rot['waiting_for_own_exit']
  for e in d['event_eligibility']:
   s=e['symbol']
   if (s,year) not in targets:continue
   t=trace[d['account'],s,year];t['events']+=1;t['eligible']+=e['q'] is True;t['accepted']+=s in d['accepted'];t['reasons'].update(e['reasons'])
   if s in first:t['rejects'][first[s]]+=1
   if s in execution:t['rejects'][execution[s]]+=1
   if mode in ['B','D']:
    t['stock_gate_false']+=s in ids and gate[i,ids[s]]==0;t['sector_gate_false']+=meta[s]['sector_id'] in ids and gate[i,ids[meta[s]['sector_id']]]==0
   if rot:t['rotation_ban']+=s in rot['banned_stocks'] or meta[s]['sector_id'] in rot['banned_sectors']
 rows=[];namedrows=[]
 def window(aid,s,year,w=None):
  start=f'{year}-01-01';end=min(f'{year}-12-31','2026-10-22');cc=campaign.loc[campaign.account.eq(aid)&campaign.symbol.eq(s)];overlap=cc[(cc.entry_at.str[:10]<=end)&(cc.exit_at.fillna('9999').str[:10]>=start)];part=bool(len(overlap));t=trace[aid,s,year]
  helddays=sum(s in r['positions'] for dt,r in daily[aid].items() if start<=dt<=end)
  eventcount=sum(start<=d<=end for d in buy.get(s,[]))
  if part:reason='participated'
  elif eventcount==0:reason='no_original_IX_event'
  elif t['accepted']:reason='accepted_without_actual_fill'
  elif t['eligible']:reason=t['rejects'].most_common(1)[0][0] if t['rejects'] else 'eligible_without_allocation'
  elif t['rotation_ban']:reason='rotation_reentry_not_requalified'
  elif t['sector_gate_false']:reason='dual_sector_absolute_or_breadth_gate'
  elif t['stock_gate_false']:reason='dual_stock_channel_gate'
  else:reason=t['reasons'].most_common(1)[0][0] if t['reasons'] else 'event_not_admitted'
  dc=contrib.loc[contrib.account.eq(aid)&contrib.symbol.eq(s)] if 'symbol' in contrib else pd.DataFrame()
  if not dc.empty:
   datecol='date' if 'date' in dc else 'at';dc=dc[(dc[datecol].str[:10]>=start)&(dc[datecol].str[:10]<=end)]
  return dict(account=aid,scheme=aid.split('__')[0],symbol=s,name=meta[s]['name'],industry=meta[s]['industry'],year=year,posthoc_price_return=w['adjusted_price_return'] if w else None,participated=part,held_closes=helddays,events=eventcount,eligible_event_days=t['eligible'],accepted_days=t['accepted'],main_reason=reason,qualification_reasons=dict(t['reasons']),constraint_reasons=dict(t['rejects']),stock_gate_false_days=t['stock_gate_false'],sector_gate_false_days=t['sector_gate_false'],rotation_ban_days=t['rotation_ban'],overlapping_campaign_pnl=float(overlap.net_pnl.astype(float).sum()))
 for aid in daily:
  for w in windows:rows.append(window(aid,w['symbol'],w['year'],w))
  for s in named:
   for year in range(2023,2027):namedrows.append(window(aid,s,year))
 write(out/'annual-winner-reasons.json',rows);pd.DataFrame(rows).to_csv(out/'annual-winner-reasons.csv',index=False)
 write(out/'named-winner-reasons.json',namedrows);pd.DataFrame(namedrows).to_csv(out/'named-winner-reasons.csv',index=False)
 for aid in daily:
  obj=read(account_path(aid));events=[r for r in obj['audit_log'] if r['kind']=='portfolio_rotation_request'];fills=obj['fills']
  for e in events:
   at=e['at'];outs=e['outgoing_stocks'];future=[f for f in fills if f['side']=='sell' and f['security_id'] in outs and f['at']>at]
   # Follow only this exit order's fills, stopping before any later buy of an
   # outgoing stock. Do not attribute a later independent campaign's sale.
   sales=[]
   for sid in outs:
    nextbuy=min((f['at'] for f in fills if f['side']=='buy' and f['security_id']==sid and f['at']>at),default='9999')
    sales.extend(f for f in future if f['security_id']==sid and f['at']<nextbuy)
   last_sale=max((f['at'] for f in sales),default=None)
   laterbuys=[f for f in fills if f['side']=='buy' and last_sale and f['at']>last_sale]
   first=min(laterbuys,key=lambda f:f['at']) if laterbuys else None
   match=(first['security_id']==e['incoming'] if e['rotation_kind']=='stock' else meta[first['security_id']]['sector_id']==e['incoming']) if first else False
   for sid in outs:
    i=dates.get_loc(at[:10]);j=ids[sid];post={}
    for h in [21,63]:
     k=i+h;good=k<len(dates) and np.isfinite(closes[i,j]) and np.isfinite(closes[k,j]) and segments[i,j]==segments[k,j]
     post[f'outgoing_posthoc_{h}']=float(closes[k,j]/closes[i,j]-1) if good else None
    rotations.append(dict(account=aid,scheme=aid.split('__')[0],request_at=at,rotation_kind=e['rotation_kind'],incoming=e['incoming'],outgoing=sid,outgoing_name=meta[sid]['name'],outgoing_industry=meta[sid]['industry'],outgoing_sector=meta[sid]['sector_id'],confirmations=e['confirmations'],rank_in=e['rank_in'],rank_out=e['rank_out'],first_sale=min((f['at'] for f in sales if f['security_id']==sid),default=None),last_outgoing_sale=last_sale,first_later_buy=first['security_id'] if first else None,first_later_buy_at=first['at'] if first else None,first_later_buy_matches_original_challenger=match,**post))
 write(out/'rotation-handoffs.json',rotations);pd.DataFrame(rotations).to_csv(out/'rotation-handoffs.csv',index=False)
 # The old fixed semiconductor windows are slices of continuous all-A NAV:
 # never reset the capital or pretend they classify the whole A-share market.
 scenarios=[('偏强震荡参照','2021-01-01','2021-12-31'),('熊市参照','2022-01-01','2022-12-31'),('弱震荡参照','2023-01-01','2023-12-31'),('半导体牛市参照','2025-01-01','2026-06-30'),('2026完整周期','2026-01-01','2026-10-22')];slices=[]
 for aid,g in curves.groupby('account'):
  for label,start,end in scenarios:
   f=g[(g.date>=start)&(g.date<=end)];prev=g[g.date<start];initial=float(prev.nav.iloc[-1]) if len(prev) else 1e6;n=f.nav.to_numpy();slices.append(dict(account=aid,scheme=aid.split('__')[0],scenario=aid.split('_')[-1],window=label,start=start,end=end,initial_nav=initial,net_return=float(n[-1]/initial-1),max_drawdown=float(-(n/np.maximum.accumulate(np.r_[initial,n])[1:]-1).min())))
 write(out/'fixed-scenario-slices.json',slices);pd.DataFrame(slices).to_csv(out/'fixed-scenario-slices.csv',index=False)
 write(out/'receipt.json',dict(passed=True,annual_windows_per_base_account=240,base_accounts=4,posthoc_only=True,no_posthoc_profit_added=True,rotation_distinct_close_buffer_verified=True,recorded_at=now()))
 print(dict(winner_windows=len(rows),named_windows=len(namedrows),rotation_stock_exits=len(rotations)),flush=True)
if __name__=='__main__':main()
