"""Post-freeze independent account reconstruction and actual contribution export."""
import sys,gzip,collections
from decimal import Decimal as D
import pandas as pd
import numpy as np
from util_ix import *
sys.path.append(str(OLD/'code'))
import analyze_accounts as audit
from market_runner import encoded

class IndependentPrices(audit.Prices):
 """Raw close marks with the declared validity mask, independent of the runner."""
 def mark(self,sid,day):
  if sid not in self.cache:
   r=self.records[sid];f=pd.read_parquet(r['raw']['path']);dates=pd.DatetimeIndex(pd.to_datetime(f.trade_date if 'trade_date' in f else f.index));o=f[['open','high','low','close']].apply(pd.to_numeric)
   valid=np.isfinite(o).all(axis=1)&o.gt(0).all(axis=1)&o.high.ge(o.low)&o.high.ge(o[['open','close']].max(axis=1))&o.low.le(o[['open','close']].min(axis=1))
   def flag(name,default):return f[name].astype(str).str.lower().isin(['true','1','1.0']) if name in f else pd.Series(default,index=f.index)
   observed=flag('is_observed_bar',True) if 'is_observed_bar' in f else flag('observed_bar',True)
   valid&=observed&~flag('synthetic_event_bar',False)&~flag('source_invalid',False)
   if 'source_anomaly' in f:valid&=f.source_anomaly.fillna('').astype(str).str.strip().eq('')
   actions=read(r['adjustment']['actions']['path'])['events'];self.cache[sid]=(dates[valid.to_numpy()],f.close.to_numpy()[valid.to_numpy()],actions)
  d,c,actions=self.cache[sid];i=d.searchsorted(pd.Timestamp(day),side='right')-1;assert i>=0
  price=D(str(c[i]));old=d[i].date().isoformat()
  for e in actions:
   if old<e['effective_date']<=day:price=(price-D(str(e.get('signal_cash_per_old_share',e['cash_per_old_share']))))/D(str(e.get('signal_split_ratio',e['split_ratio'])))
  return price

def main():
 out=HERE/'analysis';out.mkdir(exist_ok=False);source=HERE/'accounts';assert read(source/'summary.json')['historical_account_runs']==48
 daily=collections.defaultdict(list)
 with gzip.open(source/'daily.jsonl.gz','rt') as f:
  for line in f:r=readline(line);daily[r['account']].append(r)
 meta=read(OLD/'inputs-v2/metadata.json');prices=IndependentPrices();calendar=[audit.t(x) for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']]
 results=[];campaign_rows=[];curves=[];years=[];audits=[];profiles=[];contrib=[];fills=[];signal_cache={}
 for full,rows in daily.items():
  mode,aid=full.split('__',1);obj=read(source/f'{full}.json');details=[]
  camps,receipt=audit.audit_account(aid,obj,rows,prices,meta,calendar,details);receipt['account']=full;audits.append(receipt)
  for c in camps:c['account']=full;c['entry_scheme']=mode
  campaign_rows+=camps
  for c in details:c['account']=full;c['entry_scheme']=mode
  contrib+=details
  f=pd.DataFrame(rows);f['date']=pd.to_datetime(f['at'],utc=True).dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
  for col in ['nav','inventory','available','order_reserved','dividend_receivable','fees_cny']:f[col]=f[col].astype(float)
  nav=f.nav.to_numpy();peak=np.maximum.accumulate(np.r_[1e6,nav])[1:];dd=nav/peak-1;exposure=f.inventory/f.nav;closed=[x for x in camps if x['closed']];tail=sum((x['net_pnl'] for x in closed if x['tail_closed']),D(0));ordinary=sum((x['net_pnl'] for x in closed if not x['tail_closed']),D(0));openpnl=sum((x['net_pnl'] for x in camps if not x['closed']),D(0))
  results.append(dict(account=full,entry_scheme=mode,allocation=aid.split('_')[0],scenario=aid.split('_')[1],net_return=nav[-1]/1e6-1,cagr=(nav[-1]/1e6)**(1/((f.date.iloc[-1]-pd.Timestamp('2015-01-01')).days/365.25))-1,max_drawdown=float(-dd.min()),final_nav=float(nav[-1]),mean_exposure=float(exposure.mean()),mean_cash=float((f.available/f.nav).mean()),fees_cny=float(f.fees_cny.iloc[-1]),closed_campaigns=len(closed),open_campaigns=len(camps)-len(closed),win_rate=sum(x['net_pnl']>0 for x in closed)/len(closed) if closed else None,tail_closed_profit=float(tail),ordinary_closed_pnl=float(ordinary),open_campaign_pnl=float(openpnl),unique_stocks=len(set(x['symbol'] for x in camps)),buy_fills=sum(x['side']=='buy' for x in obj['fills']),sell_fills=sum(x['side']=='sell' for x in obj['fills']),max_stock_weight=receipt['max_stock_weight'],max_sector_weight=receipt['max_sector_weight']))
  for i,r in f.iterrows():curves.append(dict(account=full,entry_scheme=mode,allocation=aid.split('_')[0],scenario=aid.split('_')[1],date=str(r.date.date()),nav=float(r.nav),drawdown=float(dd[i]),exposure=float(exposure.iloc[i]),cash=float(r.available)))
  previous=1e6
  for year,group in f.groupby(f.date.dt.year):
   a=group.nav.to_numpy();years.append(dict(account=full,entry_scheme=mode,allocation=aid.split('_')[0],scenario=aid.split('_')[1],year=int(year),net_return=float(a[-1]/previous-1),max_drawdown=float(-(a/np.maximum.accumulate(np.r_[previous,a])[1:]-1).min())));previous=float(a[-1])
  reservations={x['order_id']:x['decision_at'] for x in obj['audit_log'] if x['kind']=='reserve'}
  # All actual buys must be backed by this scheme's event on the decision day.
  for row in obj['audit_log']:
   if row['kind']!='fill':continue
   receipt=row['receipt'];z=dict(account=full,entry_scheme=mode,allocation=aid.split('_')[0],scenario=aid.split('_')[1],**receipt);fills.append(z)
   if receipt['side']!='buy':continue
   sid=receipt['security_id'];decision=reservations[row['order_id']][:10]
   if sid not in signal_cache:signal_cache[sid]=pd.read_parquet(HERE/'signals'/f'{sid}.parquet')
   sf=signal_cache[sid];q=sf.loc[decision];assert bool(q[mode]),(full,sid,decision,'non-event buy')
   assert audit.t(receipt['at']).date()>audit.t(decision).date()
  first={}
  for row in obj['audit_log']:
   if row['kind']=='fill' and row['receipt']['side']=='buy':first.setdefault((row['receipt']['security_id'],row['receipt']['at']),row)
  for c in camps:
   row=first[c['symbol'],c['entry_at']];decision=reservations[row['order_id']][:10];sf=signal_cache[c['symbol']];q=sf.loc[decision]
   loc=sf.index.get_loc(pd.Timestamp(decision));history=sf.iloc[:loc+1];oldenter=np.flatnonzero(history.e0_entered.to_numpy(float)==1);ixexit=np.flatnonzero(history.ix_exited.to_numpy(float)==1)
   if bool(q.ix_entered):kind='recovery' if len(ixexit) and len(oldenter) and ixexit[-1]>oldenter[-1] else 'first_or_delayed_start'
   else:kind='continuation'
   profiles.append(dict(account=full,entry_scheme=mode,allocation=aid.split('_')[0],scenario=aid.split('_')[1],symbol=c['symbol'],name=c['name'],industry=c['industry'],decision_date=decision,entry_at=c['entry_at'],entry_grade=float(q.grade),previous_grade=float(q.previous_grade) if pd.notna(q.previous_grade) else None,e0_age=float(q.e0_age_observations) if pd.notna(q.e0_age_observations) else None,support_distance=float((q.close-q.e0_floor)/q.close),signal_type=kind,closed=c['closed'],net_pnl=float(c['net_pnl']),net_return=c['net_return']))
  print(dict(audited=full,rows=len(rows),closed=len(closed)),flush=True)
 pd.DataFrame(results).to_csv(out/'summary.csv',index=False);write(out/'summary.json',results)
 for name,rs in [('campaigns',campaign_rows),('curves',curves),('annual',years),('entry-profiles',profiles),('daily-stock-contributions',contrib),('fills',fills)]:
  pd.DataFrame(rs).to_csv(out/f'{name}.csv',index=False);write(out/f'{name}.json',encoded(rs))
 write(out/'accounting-audit.json',dict(recorded_at=now(),passed=True,accounts=len(audits),daily_rows=sum(x['checks']['daily_independent_nav_and_shares'] for x in audits),all_actual_buys_have_current_scheme_events=True,details=audits))
 # Same explicit PnL labels as old research; never net fees twice.
 for label,key in [('stocks','symbol'),('industries','industry')]:
  a=pd.DataFrame(campaign_rows);a['net_pnl']=a.net_pnl.astype(float);q=a.groupby(['account','entry_scheme',key],dropna=False).agg(net_pnl=('net_pnl','sum'),campaigns=('net_pnl','size')).reset_index();q.to_csv(out/f'actual-{label}.csv',index=False)
 old=read(OLD/'analysis-v2/summary.json');write(out/'old-E0-reference.json',old)
 print(pd.DataFrame(results).query("scenario=='base'")[['entry_scheme','allocation','net_return','max_drawdown','mean_exposure','closed_campaigns']].to_string(index=False),flush=True)

def readline(s):import json;return json.loads(s)
if __name__=='__main__':main()
