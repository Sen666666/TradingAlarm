"""Saved next-session audit and behavior; no financial event."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,sys,datetime
import c_horizon as C
sys.path.insert(0,str(C.OLD));from verify_saved import check_json
HERE=C.HERE;E=C.E;Z=D(0)
def read(p):return C.read(p)
def summary(x):
 a=x['account'];b=a['balance'];industry=defaultdict(lambda:Z);roles=defaultdict(lambda:Z);use=defaultdict(lambda:Z)
 for z in a['layers']:
  m=a['capital_meta'][str(z['id'])];v=D(z['qty'])*D(a['market_marks'][z['sid']]);industry[m['sector']]+=v;roles[m['role']]+=v;use[m['purpose']]+=v
 last=x['results'][-1]['projection'];book=json.loads(x['budget'])['body'];orders=a['supports']
 rawreasons=Counter()
 for r in a['rejections']:
  def flat(y):return [t for z in y for t in flat(z)] if isinstance(y,list) else [str(y)]
  for why in set(flat(r['route']['why'])):rawreasons[why]+=1
 return dict(balance=b,exposure=D(b['inventory'])/D(b['nav']),industries=[dict(sector=s,value=v,weight=v/D(b['nav'])) for s,v in sorted(industry.items(),key=lambda z:(-z[1],z[0]))],roles=dict(roles),uses=dict(use),
  stocks=len(b['quantities']),fill_count=len(a['fills']),pending_intents=len(x['pending']),native_buys=a['buys'],exit_duties=a['exit_duties'],native_exits=a['exits'],locks=a['policy']['locks'],goal_coverage=x['goal_coverage'],batch=book['batch'],last_Q={s:q for s,q in last['Q'].items() if q},last_D=last['D'],last_projection_trace=last['trace'],raw_route_reason_presence=dict(rawreasons))
def main():
 assert read(HERE/'COMPLETED.json')['no_further_date_authorized'];rows=[];checks=[];cp=[]
 for window in ('2025_26','2022'):
  day=C.DATES[window]
  for mode in ('C10','C_BATCH20'):
   root=HERE/'runs'/(window+'-'+mode);assert read(root/'COMPARISON.json')['passed']
   for branch in ('full','physical'):
    out=root/branch
    for phase in (['ACTION'] if window=='2025_26' else [])+['OPEN','CLOSE']:
     p=out/(day+'-'+phase+'.json');diff=check_json(p);checks.append(dict(window=window,mode=mode,branch=branch,event=phase,financial_differences=diff))
   out=root/'full';start=read(out/'state/IMPORT.json')['import_evidence'];original=Path(start['checkpoint']).with_suffix('.json');before=read(original);after=read(out/(day+'-CLOSE.json'));a=after['account'];oldids={f['receipt_id'] for f in before['account']['fills']};fills=[f for f in a['fills'] if f['receipt_id'] not in oldids];newlayers={z['id']:z for z in a['layers']};detail=[]
   for f in fills:
    layerid=a['inventory_map'].get(f['receipt_id'],{}).get('layer') if f['side']=='buy' else None
    meta=a['capital_meta'].get(str(layerid)) if layerid else None
    detail.append(dict(**f,layer=layerid,role=meta['role'] if meta else None,purpose=meta['purpose'] if meta else None,pool=meta['pool'] if meta else None))
   timings=[]
   for phase in (['ACTION'] if window=='2025_26' else [])+['OPEN','CLOSE']:
    t=read(out/(phase+'-TIMING.json'));pre=out/('BEFORE_'+phase+'.json');end=datetime.datetime.fromisoformat(t['completed_at']).timestamp();begin=datetime.datetime.fromisoformat(t['started_at']).timestamp();pivot=pre.stat().st_mtime
    timings.append(dict(phase=phase,total_driver_seconds=t['seconds'],restore_guard_and_before_save_seconds=pivot-begin,event_and_after_save_seconds=end-pivot,not_pure_function_profile=True))
   result=dict(window=window,mode=mode,day=day,before=summary(before),after=summary(after),new_fills=detail,new_buy_gross=sum((D(f['gross_cny']) for f in fills if f['side']=='buy'),Z),new_sell_gross=sum((D(f['gross_cny']) for f in fills if f['side']=='sell'),Z),new_fee=sum((D(f['fees_cny']) for f in fills),Z),new_buy_count=sum(f['side']=='buy' for f in fills),new_sell_count=sum(f['side']=='sell' for f in fills),timings=timings)
   rows.append(result);p=out/(day+'-CLOSE.pkl');cp.append(dict(window=window,mode=mode,path=str(p),sha256=C.P.sha(p),cursor=after['last_completed'],source_binding_verified=True,formal_branch='full',future_finance_not_authorized=True))
 E.IO.write_json(HERE/'FINANCIAL_CHECKS.json',dict(passed=True,event_states=len(checks),checks_per_state=7,rows=checks,financial_events=0),encoder=E.encode)
 E.IO.write_json(HERE/'RESULTS.json',dict(scope='four next-session formal paths plus isolated physical verification, no further date',rows=rows),encoder=E.encode)
 E.IO.write_json(HERE/'CONTINUATION_CHECKPOINTS.json',cp,encoder=E.encode)
 print(json.dumps([dict(window=r['window'],mode=r['mode'],buy=r['new_buy_gross'],sell=r['new_sell_gross'],fees=r['new_fee'],exposure=r['after']['exposure'],D=r['after']['last_D'],budget_new=r['after']['batch']['new'],budget_carry=r['after']['batch']['carry']) for r in rows],default=str,indent=2))
if __name__=='__main__':main()
