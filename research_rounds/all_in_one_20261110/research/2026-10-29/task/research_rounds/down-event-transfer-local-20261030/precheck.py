"""Next-open prefix checks only, using the exact existing reservation/fill methods."""
from pathlib import Path
import importlib.util,sys,csv,json,bisect,time
from datetime import time as dt,timedelta
from decimal import Decimal as D
from dataclasses import replace
import pandas as pd
O=Path(__file__).resolve().parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');P=O.parent/'down-event-transfer-exposure-20261030';T=time.monotonic()
sp=importlib.util.spec_from_file_location('prefix_existing_helpers',R/'s-entry-mechanism-audit-20261029/code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
es=list(csv.DictReader((P/'selected-events-before-labels.csv').open()));_,m,_,_=H.context({e[k] for e in es for k in ['old','new']},False);f=pd.read_parquet(R/'s-entry-mechanism-audit-20261029/market-cache.parquet');cc={(x.symbol,str(x.date.date())):x for x in f.itertuples(index=False)};out=[]
for e in es:
 t=H.at(e['date'],dt(15,10));op=m.sessions['A'][bisect.bisect_right(m.sessions['A'],t)]
 for cost in [1,2]:
  old,new=e['old'],e['new'];q=int(e['old_quantity']);w=m.window(old,op,'sell',cost);ok=bool(w and w.sell_allowed and w.capacity_shares>=q and w.quantity.sell_floor(q,q)==q);r=dict(cycle_id=e['cycle_id'],cost=cost,at=op,old_full_market_check=ok,new_status=None)
  if ok:
   gross=D(q)*w.execution_price;fee=sum(w.fees.incremental('sell',gross,{}, {},cost,shares=q,par_value=w.par_value).values(),D(0));net=gross-fee;a=H.L.SectorAccount(initial_cash=net,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);nw=m.window(new,op,'buy',cost);quote=m.quote(new,op);floor=D(str(cc[new,e['date']].i_floor))/D(str(cc[new,str(op.date())].factor));cap=int(e['new_projected_shares'])
   for x in m.actions.get(new,[]):
    if e['date']<x['effective_date']<=str(op.date()):cap=int(D(cap)*D(x['split_ratio']))
   if nw is None or not nw.buy_allowed:r['new_status']='buy_market_proxy_unavailable'
   elif nw.raw_open<=floor:r['new_status']='open_not_above_frozen_support'
   elif quote is None:r['new_status']='quote_unknown'
   else:
    when=op+timedelta(seconds=1);accept,why=a.reserve_budget(quote=quote,clock=H.A.Clock(op,when,op.date()),gross_budget_cny=min(D(e['new_gross_cap']),net),target_shares_cap=cap,candidate_id='execution_prefix_only');bf=a.fill_buy(new,replace(nw,event_id=nw.event_id+':prefix',at=when,cash_due_at=max(when,nw.cash_due_at))) if accept else None;r['new_status']='new_filled' if bf else 'reservation_or_fill_failed:'+str(why);r['predicted_new_qty']=bf.shares if bf else 0
   r.update(predicted_old_net=net,new_raw_open=nw.raw_open if nw else None,frozen_raw_support=floor)
  out.append(r)
(O/'NEXT_OPEN_PRECHECK.json').write_text(json.dumps(H.encoded(dict(rows=out,seconds=time.monotonic()-T,not_a_return_path=True)),ensure_ascii=False,indent=2));print(json.dumps(H.encoded(dict(seconds=time.monotonic()-T,failed=[r for r in out if not r['old_full_market_check'] or r['new_status']!='new_filled'])),ensure_ascii=False),flush=True)
