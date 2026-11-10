"""Post-run paired comparisons; never supplies a trading decision."""
from pathlib import Path
import json,collections
import pandas as pd,numpy as np
from build_inputs import HERE,read,write,now
OLD=HERE.parent/'a-share-selection-e0-20261024'
def csv(name,rows):pd.DataFrame(rows).to_csv(HERE/'comparison'/(name+'.csv'),index=False,encoding='utf-8-sig')
def main():
 out=HERE/'comparison';out.mkdir(exist_ok=False)
 old={x['account']:x for x in read(OLD/'analysis-v2/summary.json')};new=read(HERE/'analysis-v2/summary.json');paired=[]
 for x in new:
  o=old[x['account']];paired.append(dict(account=x['account'],old=o,new=x,return_change_pp=100*(x['net_return']-o['net_return']),drawdown_change_pp=100*(x['max_drawdown']-o['max_drawdown']),pnl_change=x['final_nav']-o['final_nav']))
 write(out/'paired-metrics.json',paired);csv('paired-metrics',[dict(account=x['account'],**{f'{v}_{k}':d for v in ['old','new'] for k,d in x[v].items() if k!='account'},return_change_pp=x['return_change_pp'],drawdown_change_pp=x['drawdown_change_pp'],pnl_change=x['pnl_change']) for x in paired])
 for label,keys in [('actual-stocks',['account','symbol','name','industry','sector_id']),('actual-industries',['account','industry'])]:
  a=pd.DataFrame(read(OLD/'analysis-v2'/(label+'.json')));b=pd.DataFrame(read(HERE/'analysis-v2'/(label+'.json')))
  a=a.loc[~a.account.str.startswith('B0')];both=a.merge(b,on=keys,how='outer',suffixes=('_old','_new'))
  for col in ['net_contribution','buy_gross']:
   both[col+'_old']=both[col+'_old'].fillna(0);both[col+'_new']=both[col+'_new'].fillna(0);both[col+'_change']=both[col+'_new']-both[col+'_old']
  both['participation_change']=np.select([(both.buy_gross_old==0)&(both.buy_gross_new>0),(both.buy_gross_old>0)&(both.buy_gross_new==0)],['newly_bought','no_longer_bought'],default='both_bought')
  both.to_csv(out/(label+'-comparison.csv'),index=False,encoding='utf-8-sig');write(out/(label+'-comparison.json'),json.loads(both.to_json(orient='records',force_ascii=False)))
 # Actual purchases by calendar year, not a fixed stock list after the run.
 for root,label in [(OLD,'old'),(HERE,'new')]:
  fills=pd.read_csv(root/'analysis-v2/fills.csv');b=fills.loc[fills.side.eq('buy')&~fills.account.str.startswith('B0')].copy();b['year']=b['at'].str[:4].astype(int)
  grouped=b.groupby(['account','year','security_id','name','industry'],sort=True).agg(buy_gross_cny=('gross_cny','sum'),buy_fees_cny=('fees_cny','sum'),buy_fills=('at','size'),first_buy=('at','min'),last_buy=('at','max')).reset_index()
  grouped.to_csv(out/('annual-actual-buys-'+label+'.csv'),index=False,encoding='utf-8-sig')
 oldw={(x['account'],x['key']):x for x in read(OLD/'misses-v2/windows.json')};neww=read(HERE/'misses-v2/windows.json');joined=[]
 for x in neww:
  o=oldw.get((x['account'],x['key']))
  if not o:continue
  joined.append(dict(account=x['account'],key=x['key'],window_type=x['window_type'],symbol=x['symbol'],name=x['name'],industry=x['industry'],year=x['year'],start_date=x['start_date'],end_date=x['end_date'],price_return=x['price_return'],old_participated=o['participated'],new_participated=x['participated'],old_reason=o['primary_reason'],new_reason=x['primary_reason'],old_contribution=o['window_net_contribution'],new_contribution=x['window_net_contribution'],old_coverage=o['holding_day_fraction'],new_coverage=x['holding_day_fraction'],old_weight=o['mean_account_weight'],new_weight=x['mean_account_weight'],new_first=x['first_participation'],current_cap_disposition=x['current_cap_disposition'],new_components=x['eligibility_component_days']))
 write(out/'winner-comparison.json',joined);csv('winner-comparison',[{k:v for k,v in x.items() if k!='new_components'} for x in joined])
 annual=[]
 for aid in ['T0_base','T1_base','S0_base','S1_base']:
  xs=[x for x in joined if x['account']==aid and x['window_type']=='annual' and x['current_cap_disposition']=='selected'];assert len(xs)==240
  annual.append(dict(account=aid,windows=240,old_participated=sum(x['old_participated'] for x in xs),new_participated=sum(x['new_participated'] for x in xs),newly_participated=sum(x['new_participated'] and not x['old_participated'] for x in xs),lost_participation=sum(x['old_participated'] and not x['new_participated'] for x in xs),new_missed_reasons=dict(collections.Counter(x['new_reason'] for x in xs if not x['new_participated'])),old_mean_weight=float(np.mean([x['old_weight'] for x in xs])),new_mean_weight=float(np.mean([x['new_weight'] for x in xs])),old_mean_coverage=float(np.mean([x['old_coverage'] for x in xs])),new_mean_coverage=float(np.mean([x['new_coverage'] for x in xs]))))
 write(out/'annual-winners-summary.json',annual)
 # Fixed ex-post leading examples; IPO/source year is not a year of tradable gains.
 top=read(HERE/'funnel-v2/qualified-annual-top20.json');top=sorted(top,key=lambda x:x['adjusted_price_return'],reverse=True)[:16]
 pm={x['series_id']:x for x in read(HERE/'prepared-v2/manifest.json')['series']};readiness=[]
 for x in top:
  st=pd.read_parquet(HERE/'prepared-v2'/pm[x['symbol']]['files']['states']['path'],columns=['ready','target']);f=pd.read_parquet(HERE/'prepared-v2'/pm[x['symbol']]['files']['signal']['path'],columns=['close'])
  yr=st.loc[str(x['year'])];rr=yr.loc[yr.ready.astype(bool)];first=rr.index[0] if len(rr) else None
  readiness.append(dict(symbol=x['symbol'],name=x['name'],year=int(x['year']),price_return=x['adjusted_price_return'],first_e0_ready=str(first.date()) if first is not None else None,full_year_e0_unready=first is None,price_move_before_first_e0_ready=float(f.loc[first,'close']/f.loc[:first].loc[str(x['year'])].close.iloc[0]-1) if first is not None else None))
 write(out/'leading-winners-readiness.json',readiness)
 write(out/'summary.json',dict(recorded_at=now(),paired_accounts=len(paired),annual_winner_windows=240,old_results_read_only=True,formula_revisions_after_results=0,component_attribution='Joint repair only; no RS-only or TTL-only causal effect estimate',delay_comparison='Delay1 requires daily fresh reranking; old persistent-order wait clock differs',source=read(HERE/'freeze.json')['recorded_at']))
 print({'paired_accounts':len(paired),'winner_rows':len(joined)},flush=True)
if __name__=='__main__':main()
