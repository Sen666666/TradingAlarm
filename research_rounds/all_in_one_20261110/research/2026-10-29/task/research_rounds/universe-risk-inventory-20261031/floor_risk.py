"""Read-only nominal floor distances of six existing ACT ledgers; no strategy replay."""
from pathlib import Path
from decimal import Decimal as D
import csv, gzip, hashlib, json, time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
TP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared')
T=time.monotonic(); identities={};entries=[];holdings=[];days=[];checks=[];summaries=[]
def note(p): identities[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,x): (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2))
def out(name,x): pd.DataFrame(x).to_csv(O/name,index=False)
def quant(s):
 s=pd.Series(s,dtype=float).dropna()
 return {str(p):float(s.quantile(p)) for p in [0,.1,.25,.5,.75,.9,.95,1]} if len(s) else {}
def decimal(x):return D(str(x))
for sector,root,prefix,prep in [
 ('TECH',RR/'pvr-local-finite-capital-20261029/baseline','I',TP),
 ('DRUG',RR/'innovative-drug-local-recovery-20261028/S0','ACT',RR/'innovative-drug-sfw3-20261028/prepared')]:
 cp=root/'analysis/contributions.csv';note(cp);contrib=pd.read_csv(cp,dtype=str)
 dp=root/'accounts-v2/daily.jsonl.gz';note(dp)
 with gzip.open(dp,'rt') as f:daily=[json.loads(l) for l in f]
 facts={}
 def row(sid,dt):
  if sid not in facts:
   p=prep/'facts'/f'{sid}.parquet';note(p);facts[sid]=pd.read_parquet(p)
  f=facts[sid];i=f.index.searchsorted(pd.Timestamp(dt[:10]),side='right')-1
  return (None,None) if i<0 else (f.iloc[i],str(f.index[i].date()))
 for stress in ['base','cost2','delay1']:
  account=f'{prefix}__S0_{stress}';p=root/'accounts-v2'/f'{account}.json';note(p);a=json.loads(p.read_text())
  contracts={x['order_id']:x for x in a['audit_log'] if x.get('kind')=='entry_contract'}
  fills=[x for x in a['audit_log'] if x.get('kind')=='fill' and x['receipt']['side']=='buy']
  ac=contrib[contrib.account==account];mapc={(x['date'],x['symbol']):x for x in ac.to_dict('records')}
  ds=[x for x in daily if x['account']==account];ee=[];hh=[];dd=[];errs=[]
  for x in fills:
   r=x['receipt'];sid=r['security_id'];c=contracts.get(x['order_id']);f,fd=row(sid,r['at'])
   status='known' if c and f is not None and pd.notna(f.factor) and f.factor>0 and c.get('floor_signal') is not None else 'unknown_contract_or_factor_or_floor'
   q=int(r['shares']);price=decimal(x['price']);nav=decimal(c['nav']) if c else None
   floor=decimal(c['floor_signal'])/decimal(f.factor) if status=='known' else None
   if floor is not None and floor<=0:status='unknown_nonpositive_floor';floor=None
   risk=q*(price-floor) if floor is not None else None
   e=dict(sector=sector,stress=stress,account=account,order_id=x['order_id'],receipt_id=r['receipt_id'],symbol=sid,at=r['at'],decision_at=c['decision_at'] if c else None,shares=q,execution_price=str(price),entry_floor_raw=str(floor) if floor is not None else None,fill_factor_date=fd,decision_NAV=str(nav),gross_cny=r['gross_cny'],buy_fees=r['fees_cny'],signed_nominal_risk_cny=str(risk) if risk is not None else None,positive_nominal_risk_cny=str(max(D(0),risk)) if risk is not None else None,risk_fraction_decision_NAV=float(risk/nav) if risk is not None else None,floor_distance_fraction_price=float((price-floor)/price) if floor is not None else None,status=status)
   ee.append(e)
   if abs(q*price-decimal(r['gross_cny']))>D('.000001'):errs.append(dict(kind='fill_gross_mismatch',receipt=r['receipt_id']))
  for d in ds:
   date=d['at'][:10];nav=decimal(d['nav']);rs=[];mv=D(0);positive=D(0);signed=D(0);unknown=0;stale=0;negative=0
   for sid,q in d['positions'].items():
    if not q:continue
    z=mapc.get((date,sid));f,fd=row(sid,date)
    if z is None:errs.append(dict(kind='position_not_linked',date=date,symbol=sid));continue
    if decimal(z['shares'])!=q:errs.append(dict(kind='position_quantity_mismatch',date=date,symbol=sid))
    m=decimal(z['market_value']);mv+=m;price=m/q;status='known';floor=None
    if f is None or pd.isna(f.i_floor) or pd.isna(f.factor) or f.factor<=0 or f.i_floor<=0:status='unknown_current_floor_or_factor'
    else:floor=decimal(f.i_floor)/decimal(f.factor)
    if price<=0:status='unknown_current_price';floor=None
    mark=d.get('mark_observed_at',{}).get(sid);is_stale=bool(mark and mark[:10]!=date);stale+=is_stale
    risk=q*(price-floor) if floor is not None else None
    if risk is None:unknown+=1
    else:signed+=risk;positive+=max(D(0),risk);negative+=risk<0
    h=dict(sector=sector,stress=stress,account=account,date=date,symbol=sid,shares=q,market_value=str(m),ledger_price=str(price),current_floor_raw=str(floor) if floor is not None else None,floor_asof_date=fd,mark_observed_at=mark,stale_mark=is_stale,status=status,signed_risk_cny=str(risk) if risk is not None else None,positive_risk_cny=str(max(D(0),risk)) if risk is not None else None,risk_fraction_NAV=float(risk/nav) if risk is not None else None,floor_distance_fraction_price=float((price-floor)/price) if floor is not None else None,pending_sell=sid in d['pending_sells'])
    hh.append(h);rs.append(h)
   if abs(mv-decimal(d['inventory']))>D('.000001'):errs.append(dict(kind='inventory_mark_sum_mismatch',date=date,difference=str(mv-decimal(d['inventory']))))
   reconstructed=sum((decimal(d[k]) for k in ['available','order_reserved','settlement_locked','sale_receivable','dividend_receivable','inventory']),D(0))-decimal(d['payable'])
   if abs(reconstructed-nav)>D('.000001'):errs.append(dict(kind='NAV_components_mismatch',date=date,difference=str(reconstructed-nav)))
   dd.append(dict(sector=sector,stress=stress,account=account,date=date,nav=str(nav),positions=len(rs),known_positions=len(rs)-unknown,unknown_positions=unknown,below_floor_positions=negative,stale_mark_positions=stale,signed_identified_risk_cny=str(signed),positive_identified_risk_cny=str(positive),positive_identified_risk_NAV=float(positive/nav),complete_risk_NAV=float(positive/nav) if unknown==0 else None,total_status='flat' if not rs else 'known' if not unknown else 'unknown_total_identified_lower_bound'))
  entries+=ee;holdings+=hh;days+=dd
  check=dict(account=account,days=len(ds),buy_fills=len(fills),contracts=len(contracts),holding_days=len(hh),errors=errs);checks.append(check)
  known=[x for x in dd if x['complete_risk_NAV'] is not None and x['positions']>0]
  s=dict(sector=sector,stress=stress,account=account,buy_fills=len(ee),unique_buy_orders=len({x['order_id'] for x in ee}),entry_unknown=sum(x['status']!='known' for x in ee),entry_nonpositive_distance=sum(x['risk_fraction_decision_NAV'] is not None and x['risk_fraction_decision_NAV']<=0 for x in ee),entry_risk_NAV_quantiles=quant([x['risk_fraction_decision_NAV'] for x in ee]),entry_floor_distance_quantiles=quant([x['floor_distance_fraction_price'] for x in ee]),entry_risk_over_1pct_NAV=sum(x['risk_fraction_decision_NAV'] is not None and x['risk_fraction_decision_NAV']>.01 for x in ee),account_days=len(dd),flat_days=sum(x['positions']==0 for x in dd),unknown_total_days=sum(x['unknown_positions']>0 for x in dd),holding_stock_days=len(hh),unknown_floor_stock_days=sum(x['status']!='known' for x in hh),below_floor_stock_days=sum(x['signed_risk_cny'] is not None and decimal(x['signed_risk_cny'])<0 for x in hh),stale_mark_stock_days=sum(x['stale_mark'] for x in hh),known_nonflat_portfolio_risk_NAV_quantiles=quant([x['complete_risk_NAV'] for x in known]),identified_lower_bound_risk_NAV_quantiles=quant([x['positive_identified_risk_NAV'] for x in dd if x['positions']>0]),max_known_day=max(known,key=lambda x:x['complete_risk_NAV']) if known else None,verification_errors=len(errs))
  summaries.append(s);print(json.dumps(s,ensure_ascii=False),flush=True)
out('ENTRY_FLOOR_RISK.csv',entries);out('HOLDING_FLOOR_RISK.csv',holdings);out('DAILY_PORTFOLIO_FLOOR_RISK.csv',days)
dump('FLOOR_RISK_SUMMARY.json',summaries);dump('FLOOR_RISK_VERIFICATION.json',dict(checks=checks,seconds=time.monotonic()-T,errors=sum(len(x['errors']) for x in checks),new_strategy_paths=0));dump('FLOOR_RISK_INPUT_IDENTITY.json',identities)
assert not any(x['errors'] for x in checks)
