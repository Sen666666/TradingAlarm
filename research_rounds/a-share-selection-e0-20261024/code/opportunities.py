"""Outcome-only diagnostics fixed in scope; never fed to the frozen accounts."""
from pathlib import Path
from decimal import Decimal as D,localcontext,ROUND_HALF_EVEN
import json,csv,collections
import numpy as np,pandas as pd
from normalize_actions import normalize
from build_inputs import HERE,read,write,now

def adjusted_close(raw,events):
 d=pd.DatetimeIndex(pd.to_datetime(raw.trade_date));c=raw.close.to_numpy();factor=np.ones(len(c));previous=[]
 with localcontext() as ctx:
  ctx.prec=40;ctx.rounding=ROUND_HALF_EVEN;scale=D(1)
  for e in events:
   day=pd.Timestamp(e['effective_date']);i=d.searchsorted(day,side='left')-1
   if i<0 or day>d[-1]:continue
   price=D(str(c[i]));old=d[i]
   for pe in previous:
    if old<pd.Timestamp(pe['effective_date'])<day:
     price=(price-D(pe.get('signal_cash_per_old_share',pe['cash_per_old_share'])))/D(pe.get('signal_split_ratio',pe['split_ratio']))
   cash=D(e.get('signal_cash_per_old_share',e['cash_per_old_share']));split=D(e.get('signal_split_ratio',e['split_ratio']))
   assert price>cash
   scale*=price/((price-cash)/split);factor[d.searchsorted(day,side='left'):]=float(scale);previous.append(e)
 return pd.Series(c*factor,index=d)

def main():
 out=HERE/'opportunities-v1';out.mkdir(exist_ok=False)
 cov=list(csv.DictReader((HERE/'data-adjudicated-v2/coverage.csv').open()));dispositions={x['symbol']:x for x in read(HERE/'inputs-v1/roster-dispositions.json')}
 annual=[];unsupported=[]
 prepared=read(HERE/'prepared-v1/manifest.json');pmap={x['series_id']:x for x in prepared['series']}
 for i,c in enumerate(cov):
  sid=c['symbol'];raw=pd.read_parquet(c['bars_path']);rights=read(c['rights_path']);ev,ignored,u=normalize(rights['records'],rights['source_sha256'],c['first'],'2026-10-22')
  if u:
   unsupported.append(dict(symbol=sid,unresolved=u));continue
  price=adjusted_close(raw,ev)
  # Where production exists, the plotted/traded frozen signal coordinate is
  # authoritative, including official BSE origins and all binary64 encodings.
  if sid in pmap:
   f=pd.read_parquet(HERE/'prepared-v1'/pmap[sid]['files']['signal']['path']);price=f.loc[f.observed_bar,'close']
  for year in range(2015,2027):
   part=price.loc[str(year)] if (price.index.year==year).any() else pd.Series(dtype=float)
   if part.empty:continue
   before=price.loc[price.index<pd.Timestamp(f'{year}-01-01')]
   origin=before.iloc[-1] if len(before) else part.iloc[0];origin_day=before.index[-1] if len(before) else part.index[0]
   disp=dispositions[sid]
   annual.append(dict(symbol=sid,name=disp['name'],industry=disp['industry'],year=year,adjusted_price_return=float(part.iloc[-1]/origin-1),
    first_observation=str(part.index[0].date()),last_observation=str(part.index[-1].date()),origin_date=str(origin_day.date()),
    observations=len(part),partial_listing_or_source_year=not len(before),current_cap_disposition=disp['disposition'],current_cap_cny=disp['cap_cny']))
  if (i+1)%1000==0:print({'annual_price_assets':i+1},flush=True)
 frame=pd.DataFrame(annual);frame['rank_all_current_A']=frame.groupby('year').adjusted_price_return.rank(method='first',ascending=False).astype(int)
 frame.to_csv(out/'annual-all-current-A.csv',index=False,encoding='utf-8-sig')
 tops=frame.loc[frame.rank_all_current_A<=20].sort_values(['year','rank_all_current_A']).to_dict('records');write(out/'annual-top20.json',tops)
 episodes=[]
 for sid,p in pmap.items():
  if not sid.endswith(('.SH','.SZ','.BJ')):continue
  state=pd.read_parquet(HERE/'prepared-v1'/p['files']['states']['path']);sig=pd.read_parquet(HERE/'prepared-v1'/p['files']['signal']['path'])
  origin=None
  for day,row in state.iterrows():
   if row.entered==1:origin=day
   if origin is not None and (row.exited==1 or day==state.index[-1]):
    part=sig.loc[origin:day,'close'];gain=float(part.iloc[-1]/part.iloc[0]-1);end=str(day.date());entry=str(origin.date());disp=dispositions[sid]
    if gain>=.30 and end>='2015-01-01':
     episodes.append(dict(episode_id=sid+':'+entry,symbol=sid,name=disp['name'],industry=disp['industry'],entry_date=entry,
      end_date=end,closed=bool(row.exited==1),signal_price_return=gain,peak_signal_price_return=float(part.max()/part.iloc[0]-1),
      observations=len(part),entry_kind=str(state.loc[origin,'entry_kind']),carry_in_before_account=entry<'2015-01-01',
      current_cap_disposition=disp['disposition']))
    origin=None
 write(out/'structural-winners.json',episodes);pd.DataFrame(episodes).to_csv(out/'structural-winners.csv',index=False,encoding='utf-8-sig')
 write(out/'coverage.json',dict(recorded_at=now(),raw_roster=len(cov),annual_rows=len(annual),unsupported_price_action_assets=unsupported,
  structural_stock_pool=len(pmap)-90,structural_winners=len(episodes),account_decisions_affected=0,algorithm_changes=0,
  annual_definition='prior-year last adjusted close to current-year last observed close; no prior observation uses first same-year close and marks partial. All current5576, unsupported action terms retained separately.',
  structure_definition='Frozen E0 recognition close to exit/last observed signal close >=30%; not executable PnL, open and pre-account carry-in disclosed.'))
 print({'annual_rows':len(annual),'unsupported':len(unsupported),'structural_winners':len(episodes)},flush=True)

if __name__=='__main__':main()
