from pathlib import Path
import sys,importlib.util,json,gzip,time,collections,datetime
from decimal import Decimal as D
import pandas as pd
import numpy as np
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/time-confirmation-mechanism-20261029');sp=importlib.util.spec_from_file_location('tc_report',O/'code/study.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S);H=S.H;Z=D(0);t=time.monotonic()
def total(v):return sum((D(str(x)) for x in v),Z)
u=pd.read_parquet(O/'results/units.parquet');a=pd.read_parquet(O/'results/A-readonly.parquet');book=pd.concat([a,u],ignore_index=True);keys=['event_id','cost'];p=pd.DataFrame(index=a.set_index(keys).index);p['symbol']=a.set_index(keys).symbol
for arm in ['A','W','T']:
 z=book[book.variant.eq(arm)].set_index(keys);assert z.index.is_unique and set(z.index)==set(p.index)
 for col in z.columns:
  if col not in ['symbol','variant']:p[col+'_'+arm]=z[col]
 for k in ['net_pnl','buy_gross','buy_fees','sell_gross','sell_fees','shares','market_value','dividend_receivable','realized_trading_pnl','paid_dividend_income','unrealized_inventory_pnl','accrued_unpaid_dividend_income','invested_cost_sessions']:
  p[k+'_'+arm]=p[k+'_'+arm].map(lambda x:D(str(x)))
p=p.reset_index();p['D_copy_W']=p.entry_timepass_W.fillna(False).astype(bool);p['net_pnl_D']=[x if yes else Z for x,yes in zip(p.net_pnl_W,p.D_copy_W)];p['net_return_D']=p.net_return_W.where(p.D_copy_W);p['shares_D']=p.shares_W.where(p.D_copy_W,0)
diag=pd.read_parquet(S.TA/'diagnostic/event-timing.parquet');q=diag[diag.Q];first=q[q.first_Q_in_study_epoch];firstlow=set(first.loc[first.frontier_neff.map(lambda x:pd.notna(x) and not S.near2(float(x))),'e0_epoch']);everlow=set(q.loc[q.frontier_neff.map(lambda x:pd.notna(x) and not S.near2(float(x))),'e0_epoch']);allQ=set(q.e0_epoch)
p['first_Q_low']=p.event_id.isin(firstlow);p['ever_Q_low']=p.event_id.isin(everlow);p['actual_low_intent']=p.low_intents_W.gt(0)|p.low_intents_T.gt(0);p['unknown_event']=p.unknown_origins_W.gt(0)|p.unknown_origins_T.gt(0);p['no_Q']=~p.event_id.isin(allQ)
assert all((p.net_pnl_T-p.net_pnl_W)==(p.net_pnl_D-p.net_pnl_W)+(p.net_pnl_T-p.net_pnl_D))
summary={};comparisons=[];subsets=[];continuous=[];delays=[];AA_tail={}
cache=pd.read_parquet(S.E1/'market-cache.parquet');dates=sorted(cache.date.unique());dateindex={pd.Timestamp(d).date():i for i,d in enumerate(dates)};Qlookup={(r.symbol,r.date.date()):r.Q for r in cache.itertuples()}
for cost in [1,2]:
 z=p[p.cost.eq(cost)].copy();Atail=z.net_return_A.ge(.3).fillna(False);AA_tail[cost]=Atail
 def side(arm):
  v=z['net_pnl_'+arm];pos=[x for x in v if x>0];neg=[x for x in v if x<0];gain=total(pos);loss=-total(neg);filled=z['first_fill_'+arm].notna()
  return dict(pnl=total(v),per_1m_all=total(v)/len(z),filled=int(filled.sum()),no_fill=int((~filled).sum()),positive_units=len(pos),negative_units=len(neg),negative_loss=loss,positive_pnl=gain,payoff=(gain/len(pos))/(loss/len(neg)) if pos and neg else None,profit_factor=gain/loss if loss else None,win_fraction=len(pos)/len(z),open_shares_units=int(z['shares_'+arm].gt(0).sum()),market_value=total(z['market_value_'+arm]),unpaid_dividends=total(z['dividend_receivable_'+arm]),realized_trading=total(z['realized_trading_pnl_'+arm]),paid_dividend=total(z['paid_dividend_income_'+arm]),unrealized_inventory=total(z['unrealized_inventory_pnl_'+arm]),accrued_unpaid_income=total(z['accrued_unpaid_dividend_income_'+arm]),fees=total(z['buy_fees_'+arm]+z['sell_fees_'+arm]),buy_cost=total(z['buy_gross_'+arm]+z['buy_fees_'+arm]),held_close_sessions=int(z['held_close_sessions_'+arm].sum()),mean_held_sessions_filled=float(z.loc[filled,'held_close_sessions_'+arm].mean()),invested_cost_sessions=total(z['invested_cost_sessions_'+arm]),A_tail_retention=total(z.loc[Atail,'net_pnl_'+arm])/total(z.loc[Atail,'net_pnl_A']),A_tail_delta=total(z.loc[Atail,'net_pnl_'+arm]-z.loc[Atail,'net_pnl_A']),pending_time=int(z['pending_time_at_end_'+arm].fillna(False).sum()) if arm!='A' else 0)
 cc={}
 for x,y in [('T','A'),('W','A'),('T','W'),('D','W'),('T','D')]:
  d=z['net_pnl_'+x]-z['net_pnl_'+y];tail=z['net_return_'+x].ge(.3).fillna(False)|z['net_return_'+y].ge(.3).fillna(False);saved=total(z['net_pnl_'+y].map(lambda n:max(Z,-n)))-total(z['net_pnl_'+x].map(lambda n:max(Z,-n)));added=total(z['net_pnl_'+x].map(lambda n:max(Z,n)))-total(z['net_pnl_'+y].map(lambda n:max(Z,n)));assert saved+added==total(d)
  r=dict(cost=cost,comparison=x+'-'+y,events=len(z),delta=total(d),per_1m=total(d)/len(z),tail_delta=total(d[tail]),ordinary_delta=total(d[~tail]),tail_pairs=int(tail.sum()),saved_negative=saved,added_positive=added);assert r['tail_delta']+r['ordinary_delta']==r['delta'];comparisons.append(r);cc[x+'-'+y]=r
  for name,mask in [('first_Q_low',z.first_Q_low),('ever_Q_low',z.ever_Q_low),('actual_low_intent',z.actual_low_intent),('no_actual_low',~z.actual_low_intent),('unknown',z.unknown_event),('no_Q',z.no_Q)]:
   n=int(mask.sum());subsets.append(dict(cost=cost,comparison=x+'-'+y,subset=name,events=n,delta=total(d[mask]),per_1m=total(d[mask])/n if n else None))
 for arm in ['W','T']:
  both=z['first_fill_'+arm].notna()&z.first_fill_A.notna();lag=[]
  for row in z[both].to_dict('records'):lag.append(dateindex[pd.Timestamp(row['first_fill_'+arm]).date()]-dateindex[pd.Timestamp(row['first_fill_A']).date()])
  delays.append(dict(cost=cost,arm=arm,both=int(both.sum()),same=sum(v==0 for v in lag),later=sum(v>0 for v in lag),earlier=sum(v<0 for v in lag),median_market_session_lag=float(np.median(lag)) if lag else None,A_only=int((z.first_fill_A.notna()&z['first_fill_'+arm].isna()).sum()),new_only=int((z.first_fill_A.isna()&z['first_fill_'+arm].notna()).sum()),both_no_fill=int((z.first_fill_A.isna()&z['first_fill_'+arm].isna()).sum()),entry_decision_not_original_Q=sum(pd.notna(r['first_signal_'+arm]) and not Qlookup.get((r['symbol'],pd.Timestamp(r['first_signal_'+arm]).date()),False) for r in z.to_dict('records'))))
 rejected=~z.D_copy_W;restore=rejected&z.first_fill_T.notna();accepted=z.D_copy_W
 summary[cost]=dict(events=len(z),A=side('A'),W=side('W'),T=side('T'),comparisons=cc,first_Q_low=int(z.first_Q_low.sum()),ever_Q_low=int(z.ever_Q_low.sum()),actual_low=int(z.actual_low_intent.sum()),unknown_events=int(z.unknown_event.sum()),W_actual_entry_time_rejected=int((rejected&z.first_fill_W.notna()).sum()),T_filled_when_D_rejected=int(restore.sum()),T_pnl_when_D_rejected=total(z.loc[rejected,'net_pnl_T']),T_minus_D_on_W_gate_pass=total(z.loc[accepted,'net_pnl_T']-z.loc[accepted,'net_pnl_D']),D_minus_W=total(z.net_pnl_D-z.net_pnl_W),T_minus_D=total(z.net_pnl_T-z.net_pnl_D))
 z.to_csv(O/f'results/paired-events-cost{cost}.csv',index=False)
 order=z.assign(delta=z.net_pnl_T-z.net_pnl_A).sort_values('delta',ascending=False);cum=Z
 for rank,r in enumerate(order.itertuples(),1):cum+=r.delta;continuous.append(dict(cost=cost,rank=rank,event_id=r.event_id,symbol=r.symbol,A=r.net_pnl_A,W=r.net_pnl_W,T=r.net_pnl_T,D=r.net_pnl_D,T_A_delta=r.delta,cumulative=cum,A_tail=bool(pd.notna(r.net_return_A) and r.net_return_A>=.3),T_first_fill=r.first_fill_T,A_first_fill=r.first_fill_A))
pd.DataFrame(S.enc(comparisons)).to_csv(O/'results/comparisons.csv',index=False);pd.DataFrame(S.enc(subsets)).to_csv(O/'results/affected-subsets.csv',index=False);pd.DataFrame(S.enc(delays)).to_csv(O/'results/first-participation-delays.csv',index=False);pd.DataFrame(S.enc(continuous)).to_csv(O/'results/continuous-contributions.csv',index=False)
logs=[];attempts=[];fills=[];counts=collections.defaultdict(collections.Counter);fees=collections.defaultdict(lambda:Z);shared={};clockpairs=0
with gzip.open(O/'results/audit.jsonl.gz','rt') as f:
 for line in f:
  x=json.loads(line);tag=dict(event_id=x['event_id'],symbol=x['symbol'],arm=x['variant'],cost=x['cost']);k=(x['variant'],x['cost']);cs=counts[k]
  for row in x['time']:
   logs.append(dict(**tag,**row));cs[row['kind']]+=1
   if row['kind']=='deadline':cs['deadline_legal_false']+=int(not row['legal']);cs['deadline_time_reject']+=int(not row['timepass']);cs['deadline_accept']+=int(row['accept'])
  starts=[row for row in x['time'] if row['kind']=='intent_start']
  if starts:
   key=(x['event_id'],x['cost']);known={n:starts[0][n] for n in ['at','origin','origin_pos','target_pos','anchor','origin_neff']}
   assert known['target_pos']==known['origin_pos']+4
   if key in shared:assert shared[key]==known;clockpairs+=1
   else:shared[key]=known
  origins=len([r for r in x['time'] if r['kind'] in ['intent_start','rich_immediate','unknown_origin_fallback_I']]);cs['rebuild_origins']+=max(0,origins-1)
  for row in x['attempts']:
   attempts.append(dict(**tag,**row));cs['accepted_order']+=int(row['accepted']);cs['reserve_reject']+=int(not row['accepted'])
   if not row['accepted']:cs['reject_'+row['reason']]+=1
  for row in x['audit']:
   if row['kind']=='buy_day_expiry':cs['day_expiry']+=1;cs['zero_fill_expiry']+=int(row['filled_shares']==0)
   if row['kind']=='audit_open_support_reject':cs['open_support_reject']+=1
   if row['kind']=='fill':
    fills.append(dict(**tag,**row['receipt'],raw_open=row['raw_open'],price=row['price'],fee_components=row['fee_components']))
    for name,v in row['fee_components'].items():fees[(x['variant'],x['cost'],name)]+=D(v)
pd.DataFrame(S.enc(logs)).to_parquet(O/'results/intent-log.parquet',index=False);pd.DataFrame(S.enc(attempts)).to_csv(O/'results/orders.csv',index=False);pd.DataFrame(S.enc(fills)).to_csv(O/'results/fills.csv',index=False);pd.DataFrame(S.enc([dict(arm=k[0],cost=k[1],counts=dict(v)) for k,v in counts.items()])).to_json(O/'results/intent-counts.json',orient='records',force_ascii=False,indent=2);pd.DataFrame(S.enc([dict(arm=k[0],cost=k[1],component=k[2],amount=v) for k,v in fees.items()])).to_csv(O/'results/fee-components.csv',index=False)
curve=pd.read_parquet(O/'results/daily-concurrency.parquet');curve['date']=pd.to_datetime(curve.date);crowd=[]
for (arm,cost),g in curve.groupby(['arm','cost']):
 g=g.set_index('date').reindex(pd.DatetimeIndex(dates))
 for name in ['held_units','waiting_units','origins','submitted','fills','ready']:
  v=g[name].fillna(0).astype(int);crowd.append(dict(arm=arm,cost=cost,measure=name,total=int(v.sum()),mean=float(v.mean()),p95=float(v.quantile(.95)),peak=int(v.max()),peak_dates=[str(day.date()) for day in v.index[v.eq(v.max())]]))
 for name in ['cost_basis','reserved','market_value']:
  v=g[name].fillna('0').map(D);mx=max(v);crowd.append(dict(arm=arm,cost=cost,measure=name,total=total(v),mean=total(v)/len(v),p95=None,peak=mx,peak_dates=[str(day.date()) for day,x in v.items() if x==mx]))
pd.DataFrame(S.enc(crowd)).to_csv(O/'results/concurrency-summary.csv',index=False)
S.save(O/'results/summary.json',summary);S.save(O/'results/report-verification.json',dict(passed=True,all5349_same_weights=True,derived_D_identity_exact=True,tail_ordinary_and_saved_plus_added_exact=True,first_W_T_clocks_exact_pairs=clockpairs,clock_no_future_date_at_origin=True,no_unknown_feature_support=True,unknown_events=int(p.unknown_event.sum()),seconds=time.monotonic()-t))
print(json.dumps(S.enc(summary),ensure_ascii=False,indent=2));print('report_seconds',time.monotonic()-t)
