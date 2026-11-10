"""Names and original outcome context; no projection or proportional PnL."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent;T=O.parent.parent/'task';F=O/'funding_agent';src={}
def read(p):
 p=Path(p);src[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
meta=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
rows=read(F/'ALL16_RECEIPTS_WITH_REAL_RESOURCES.json');pre=read(F/'PREOPEN_EXACT_STATE.json')
es=read(T/'loss_correction/entry_risk_commitment_review/strong_ENTRIES.json');by=defaultdict(list)
for e in es:by[e['sid'],e['signal_day'],e['role']].append(e)
out=[]
for clock,z in pre.items():
 state=z['state'];opening=clock[:10];targets=[r for r in rows if r['next_open']==opening and r['exact_open_responsibility']]
 assert targets
 last=max(targets,key=lambda r:r['exact_open_responsibility']['original_rank'])['exact_open_responsibility']
 competitors=[]
 for r in last['prior_actual_reserved_competitors']:
  sid=r['sid'];old=by[sid,last['signal_day'],r['role']]
  competitors.append(dict(sid=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],role=r['role'],pool=r['pool'],
    actual_reserved_quantity=r['shares'],actual_reserved_gross=r['gross_reserved'],actual_reserved_fees=r['fee_reserved'],
    original_fill_layers=[e['layer'] for e in old],original_fill_actions=[e['action'] for e in old],
    original_lifecycle_net_toJun30=sum((D(e['net']) for e in old),D(0)),
    outcome_is_original_only_not_scalable_or_counterfactual=True))
 holdings=defaultdict(lambda:dict(quantity=0,capital=0,risk=0,gross_mark_minus_lot_cost=0,layers=[]))
 for lot in state['lots']:
  if not lot['qty']:continue
  s=lot['stock'];mark=state['prices'][s];h=holdings[s]
  h['quantity']+=lot['qty'];h['capital']+=lot['qty']*mark;h['risk']+=lot['qty']*max(0,mark-lot['floor']);h['gross_mark_minus_lot_cost']+=lot['qty']*(mark-lot['cost']);h['layers'].append(lot['batch'])
 hold=[dict(sid=s,name=meta[s]['name'],industry=meta[s]['industry'],pending_original_sell=s in state['pending_sells'],**h) for s,h in holdings.items()]
 hold.sort(key=lambda h:-h['capital'])
 out.append(dict(OPEN=clock,decision_day=last['signal_day'],original_S0_available=state['available_exact'],
   original_S0_decision_NAV=state['decision_nav'],original_S0_cash_above10pct=D(state['available_exact'])-D(state['decision_nav'])*D('.1'),
   original_protection_sells_before_S0=[dict(sid=t['security_id'],name=meta[t['security_id']]['name'],shares=t['shares'],gross=t['gross_cny'],fee=t['fees_cny']) for t in z['same_open_protection_sells']],
   prior_new_reservations_before_last_focus_candidate=competitors,original_holdings_count=len(hold),top10_original_holdings=hold[:10],
   no_new_sales_or_reallocations_assumed=True))
(O/'COMPETITION_CONTEXT_13OPEN.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
(O/'COMPETITION_CONTEXT_SOURCE_SHA256.json').write_text(json.dumps(dict(src,reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),ensure_ascii=False,indent=2)+'\n')
for x in out[:2]:print(x['OPEN'],'S0 above reserve',x['original_S0_cash_above10pct'],'competitors',[(z['name'],z['actual_reserved_gross'],z['original_lifecycle_net_toJun30']) for z in x['prior_new_reservations_before_last_focus_candidate']])
