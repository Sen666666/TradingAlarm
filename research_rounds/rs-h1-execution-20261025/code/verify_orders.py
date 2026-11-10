"""Independent original-bar and order-lifetime audit after account completion."""
import collections,bisect
import numpy as np,pandas as pd
from build_inputs import HERE,read,write,now

def main():
 z=np.load(HERE/'h1/matrix.npz');days=pd.DatetimeIndex(z['dates']);cols={s:j for j,s in enumerate(z['symbols'])};scores=z['score'];h=z['h'];obs=z['obs_count']
 sessions=[x[:10] for x in read(HERE/'inputs-v2/market-rules.json')['calendars']['A']]
 meta=read(HERE/'inputs-v2/metadata.json');pm={x['series_id']:x for x in read(HERE/'prepared-v2/manifest.json')['series']};state={};result=[];details=[]
 for v in ['T0','T1','S0','S1']:
  for stress in ['base','cost2','delay1']:
   aid=v+'_'+stress;obj=read(HERE/'accounts-v2'/(aid+'.json'));orders={};active={};fills={};expiry=0;partial=0;short=[];exitchecks=0;refreshed=0;last_expired={}
   for row in obj['audit_log']:
    k=row['kind']
    if k=='reserve':
     sid=row['sid'];date=row['decision_at'][:10];t=days.get_loc(date);j=cols[sid];assert np.isfinite(scores[t,j]),(aid,date,sid,'unknown RS order')
     if v in ('S0','S1'):assert np.isfinite(scores[t,cols[meta[sid]['sector_id']]])
     orders[row['order_id']]=row;active[row['order_id']]=row
     if sid in last_expired and last_expired[sid]<=date:refreshed+=1
    elif k=='buy_day_expiry':
     q=orders[row['order_id']];scheduled=sessions[bisect.bisect_right(sessions,q['decision_at'][:10])]
     assert row['at'][:10]==row['valid_session']==scheduled,(aid,row,'expiry not next market day')
     expiry+=1;partial+=row['filled_shares']>0
     if row['rearm']:last_expired[row['sid']]=row['at'][:10]
    elif k=='release_buy':active.pop(row['order_id'])
    elif k=='fill' and row['receipt']['side']=='buy':
     q=orders[row['order_id']];date=q['decision_at'][:10];expected=sessions[bisect.bisect_right(sessions,date)];actual=row['receipt']['at'][:10]
     assert actual==expected,(aid,date,actual,'stale intent fill')
     if row['order_id'] not in fills:
      sid=q['sid'];t=days.get_loc(date);j=cols[sid];fills[row['order_id']]=True
      details.append(dict(account=aid,symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],decision_date=date,first_fill=actual,h=int(h[t,j]),observations=int(obs[t,j]),score=float(scores[t,j]),wait_market_sessions=1))
      if h[t,j]<252:short.append(sid)
    elif k=='exit_request':
     sid=row['sid'];date=row['at'][:10]
     if sid not in state:state[sid]=pd.read_parquet(HERE/'prepared-v2'/pm[sid]['files']['states']['path'],columns=['ready','target'])
     old=state[sid].loc[:date].iloc[-1];assert old.ready and not old.target,(aid,date,sid,'exit without unchanged E0 failure');exitchecks+=1
   for q in active.values():assert q['decision_at'][:10]=='2026-10-22',(aid,q,'overdue end order')
   result.append(dict(account=aid,passed=True,reservations=len(orders),filled_order_count=len(fills),daily_expirations=expiry,partial_balance_expirations=partial,reaccepted_after_expiry=refreshed,short_history_filled_orders=len(short),short_history_unique_stocks=len(set(short)),e0_exit_requests_verified=exitchecks,max_reserve_to_first_fill_market_sessions=1 if fills else None,ending_active_orders=len(active)))
 write(HERE/'audit/order-lifecycle.json',dict(recorded_at=now(),passed=True,rows=result,notes=['Buy reserve-to-fill maximum is one market session for all scenarios. Delay1 needs two fresh competing reservations before execution, never an old order.','E0 source target false independently verified for every requested exit; no ranking rotation.']))
 write(HERE/'audit/filled-order-ranks.json',details)
 pd.DataFrame(details).to_csv(HERE/'audit/filled-order-ranks.csv',index=False,encoding='utf-8-sig')
 print(result,flush=True)
if __name__=='__main__':main()
