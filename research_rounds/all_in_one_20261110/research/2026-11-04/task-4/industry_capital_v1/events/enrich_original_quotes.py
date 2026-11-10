"""Target raw OPEN plus original LR preview only; no full mark preparation.
Amounts are frozen maxima/minimum units, never a submitted reject quantity.
"""
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
from collections import Counter,defaultdict
import dataclasses,gzip,hashlib,inspect,json,sys,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parents[1]
sys.path.insert(0,str(W/'new_price_trend_v1/funding'))
import entry_adapter as E
LR=E.J.LR
SOURCES={}
def bind(p):p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def stream(p):
 with gzip.open(bind(p),'rt')as f:
  for line in f:yield json.loads(line)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def writer(n,rows):
 with gzip.open(O/n,'wt')as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False,default=str)+'\n')
def eff(xs,day):return next(x for x in reversed(xs)if x['from']<=day and(x.get('to')is None or day<x['to']))
def main():
 start=time.monotonic();bind(__file__);bind(inspect.getsourcefile(LR.preview));rows=list(stream(O/'CORE_SECTOR_REJECT_BOUND.jsonl.gz'))
 sm={r['symbol']:r for r in read(E.L.U/'STOCK_MANIFEST.json')};mr={r['series_id']:r for r in read(E.J.M.P/'manifest.json')['series']}
 rules=read(E.J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json');cache={};out=[];counts=Counter()
 # Reuse scalar S0 capital already computed by the closed prior census. This is
 # optional coverage and a conservative lower bound, not new mark construction.
 prior={}
 for p in stream(W/'core_supplement_v1/funding/P_ORIGINAL_RESOURCE_CONTEXT.jsonl.gz'):
  s=p.get('original_S0')
  if not s:continue
  key=p['window'],p['next_OPEN'],p['sector'];v=(s['actual_sector_inventory_capital'],s['optimistic_NAV_upper'])
  if key in prior:assert prior[key]==v
  prior[key]=v
 exact={k[:10]:v['state']for k,v in read(W/'reentry_v1/funding_agent/PREOPEN_EXACT_STATE.json').items()}
 assert LR.SLIP==D('.0005')
 for n,r in enumerate(rows):
  if n%100==0 and time.monotonic()-start>88:
   writer('CORE_SECTOR_REJECT_QUOTES.partial.jsonl.gz',out);save('QUOTE_STATUS.json',dict(complete=False,processed=len(out),events=len(rows),seconds=time.monotonic()-start,limit_seconds=100));save('QUOTE_UNPROCESSED_KEYS.json',[x['key']for x in rows[n:]]);return
  sid,day=r['sid'],r['OPEN']
  if sid not in cache:
   fp=bind(sm[sid]['refs']['facts']);assert SOURCES[str(fp.resolve())]==sm[sid]['output_sha256'][str(fp)]
   rp=bind(mr[sid]['raw']['path']);assert SOURCES[str(rp.resolve())]==mr[sid]['raw']['sha256']
   f=pd.read_parquet(fp,columns=['factor']);raw=pd.read_parquet(rp,columns=['trade_date','open']);raw.index=pd.to_datetime(raw.trade_date)
   cache[sid]=f,raw
  f,raw=cache[sid];assert pd.Timestamp(day)in raw.index
  op=D(str(raw.loc[day,'open']));assert op.is_finite()and op>0
  factor=D(str(f.factor.iloc[f.index.searchsorted(pd.Timestamp(day),side='right')-1]))
  qr=eff(rules['quantity_versions'][sid],day)['rule'];rule=LR.L.QuantityRule(**qr)
  venue=eff(rules['venue_versions'][sid],day)['venue'];fs=eff(rules['fee_versions'][venue],day)['schedule'];fee=LR.L.FeeSchedule(fs['schedule_id'],tuple(LR.L.FeeComponent(**x)for x in fs['components']))
  original=r['original_intent'];i=dict(original)
  for k in ['budget','floor','risk_budget']:i[k]=D(str(i[k]))
  i['quote']=NS(par_value=D(rules['security_metadata'][sid]['par_value']))
  preview,why=LR.preview(i,op,factor,rule,fee);assert preview is not None and why is None,(r['key'],why)
  p=preview['price'];floor=preview['floor'];qm=preview['minq'];qx=preview['maxq'];gross=D(qm)*p;nomrisk=D(qm)*max(D(0),p-floor)
  q=dict(raw_OPEN=str(op),raw_OPEN_source=mr[sid]['raw'],known_at=day+'T09:30:00+08:00',execution_price_with_original_5bps=str(p),factor=str(factor),protection_raw=str(floor),
   dated_quantity_rule=dataclasses.asdict(rule),fee_schedule_id=fs['schedule_id'],
   frozen_CLOSE_max_shares=original['cap'],frozen_CLOSE_max_gross_budget=original['budget'],frozen_CLOSE_risk_budget=original['risk_budget'],
   OPEN_preview_max_shares=qx,OPEN_preview_max_gross=str(D(qx)*p),OPEN_preview_max_buy_fee=str(preview['cost'](qx)-D(qx)*p),
   dated_minimum_shares=qm,dated_minimum_gross=str(gross),dated_minimum_buy_fee=str(preview['cost'](qm)-gross),dated_minimum_cash=str(preview['cost'](qm)),
   dated_minimum_nominal_sector_risk=str(nomrisk),dated_minimum_CORE_protection_risk_with_fees=str(LR.protection_risk(qm,p,floor,fee,i['quote'].par_value)),
   actual_rejected_order_quantity=None,source_inferred_diagnostic_quantity=qm,
   diagnostic_quantity_scope='Unchanged route allowed(rule.buy_minimum,detail=True); source maximum_quantity rejects illegal min before upper search. No real reservation/request amount logged.',
   candidate_execution_HLV_or_future_window_consulted=False)
  r['original_OPEN_contract_preview']=q
  capacity=dict(exact_pre_candidate_sc_sr_nav='UNKNOWN',exact_sector_capital_or_risk_release='UNKNOWN',
   scope='Quoted frozen max and legal min are order bounds, not capital freed. Releasing/migrating pools does not itself reduce total industry SC. Repeated stock-days/share budgets cannot be summed as funding shortfall.')
  key=r['window'],day,r['industry']
  if key in prior:
   sc,nv=map(D,prior[key]);upper=nv+D('.000001');gap=max(D(0),sc+gross-D('.02')*upper-D('.000001'))
   capacity.update(original_S0_sc_scalar=str(sc),original_S0_NAV_optimistic_upper=str(upper),minimum_capital_relief_optimistic_lower_bound=str(gap),capacity_source='Prior closed original S0 scalar census; before this OPEN new order prefix, not actual pre-candidate headroom')
   counts['has_prior_S0_scalar_lower_bound']+=1
  if r['window']=='strong'and day in exact:
   z=exact[day];lots=[x for x in z['lots']if x['sector']==r['industry']];orders=[x for x in z['orders'].values()if x['sector']==r['industry']and x['status']in ['open','cancel_pending']]
   sc=sum(float(x['qty'])*float(z['prices'].get(x['stock'],x['cost']))for x in lots)+sum(float(x['qty'])*float(x['limit'])for x in orders)
   sr=sum(float(x['qty'])*max(0,float(z['prices'].get(x['stock'],x['cost']))-float(x['floor']))for x in lots)+sum(float(x['qty'])*max(0,float(x['limit'])-float(x['floor']))for x in orders)
   capacity['exact_existing_13date_S0']=dict(nav=z['nav'],sc=sc,sr=sr,raw_state_ref='reentry_v1/funding_agent/PREOPEN_EXACT_STATE.json#'+day,scope='Earliest S0 only, not full actual pre-candidate reserved prefix')
   counts['has_13date_exact_S0']+=1
  r['industry_capacity_amounts']=capacity;out.append(r)
  if n%5000==0:save('QUOTE_PROGRESS.json',dict(processed=len(out),events=len(rows),seconds=time.monotonic()-start))
 writer('CORE_SECTOR_REJECT_EVENTS.jsonl.gz',out);save('QUOTE_SOURCE_SHA256.json',SOURCES)
 save('QUOTE_SUMMARY.json',dict(complete=True,events=len(out),stocks=len(cache),coverage=dict(counts),seconds=time.monotonic()-start,limit_seconds=100,new_accounts=0,new_RiskBooks=0,new_full_market_marks=0,new_orders=0))
 print('QUOTES_COMPLETE',len(out),len(cache),time.monotonic()-start,flush=True)
if __name__=='__main__':main()
