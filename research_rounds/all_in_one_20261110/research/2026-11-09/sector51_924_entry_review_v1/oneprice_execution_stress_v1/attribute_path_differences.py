"""Daily symbol-level accounting decomposition; not isolated causal counterfactuals."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,sys,hashlib
import pandas as pd
R=Path(sys.argv[1]);rd=lambda p:json.loads(Path(p).read_text());S=R/'full_20241031_once';B=Path(rd(R/'FREEZE.json')['source_facts'])/'full_20241031_once';Z=D(0)
selected={x['sid'] for x in rd(R/'BARRED_SEED_PATH_LINEAGES.json')};days=[x['day'] for x in rd(S/'DAY_LEDGER.json')]
def daily(run):
 orders=rd(run/'ORDERS.json');equity=rd(run/'EQUITY_EVENTS.json');holdings=rd(run/'HOLDINGS.json');cf=defaultdict(lambda:Z);ent=defaultdict(lambda:Z);out={}
 for dt in days:
  for x in orders:
   if x['day']==dt:cf[x['sid']]+=D(x['cash_delta'])
  for x in equity:
   if x['day']==dt and x['event']=='ACCRUE_NET80':ent[x['sid']]+=D(x['receivable_delta'])
  mv=defaultdict(lambda:Z)
  for x in holdings:
   if x['day']==dt:mv[x['sid']]+=D(x['market_value'])
  out[dt]={s:dict(cashflow=cf[s],entitlement=ent[s],market_value=mv[s],marked_pnl=cf[s]+ent[s]+mv[s]) for s in set(cf)|set(ent)|set(mv)}
 return out
ss=daily(S);bb=daily(B);rows=[];decomp=[];nav={x['day']:x for x in rd(R/'DAILY_BASELINE_DIFFERENCES.json')}
for dt in days:
 delta={s:ss[dt].get(s,{}).get('marked_pnl',Z)-bb[dt].get(s,{}).get('marked_pnl',Z) for s in set(ss[dt])|set(bb[dt])};assert sum(delta.values(),Z)==D(nav[dt]['difference_NAV'])
 for s,v in sorted(delta.items()):
  if v:rows.append(dict(day=dt,sid=s,barred_seed_symbol=s in selected,scenario=ss[dt].get(s,{}),baseline=bb[dt].get(s,{}),marked_pnl_difference=str(v)))
 decomp.append(dict(day=dt,blocked_seed_symbol_pnl_difference=str(sum((v for s,v in delta.items() if s in selected),Z)),other_symbol_pnl_difference=str(sum((v for s,v in delta.items() if s not in selected),Z)),total_NAV_difference=str(sum(delta.values(),Z)),nonzero_symbol_differences=sum(v!=0 for v in delta.values()),interpretation='Accounting decomposition by symbol, not isolated causal attribution; cash and future decisions are shared.'))
for name,x in [('DAILY_SYMBOL_PATH_DIFFERENCES',rows),('DAILY_PATH_ACCOUNTING_DECOMPOSITION',decomp)]:
 (R/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');pd.DataFrame(x).to_csv(R/(name+'.csv'),index=False)
(R/'PATH_DECOMPOSITION_SEAL.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__)]+[R/(n+'.json') for n in ['DAILY_SYMBOL_PATH_DIFFERENCES','DAILY_PATH_ACCOUNTING_DECOMPOSITION']]},indent=2)+'\n');print(json.dumps(decomp[-1],ensure_ascii=False))
