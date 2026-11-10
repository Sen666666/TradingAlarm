from pathlib import Path
import json,gzip,hashlib,collections
import pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/act_pause_scope_diagnostic_v1')
R=O.parent;P=R/'account_comparison_continuous_v1/run_1200000/pair';U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
assert not(O/'FIXED_CASE_NEXT_OPEN.csv').exists()
f=pd.read_csv(O/'FIXED_CASE_DAILY.csv');risk=pd.read_csv(O/'RISK_DAILY.csv')
days=sorted(risk['at'].str[:10].unique());nxt=dict(zip(days,days[1:]));spec=json.load(open(O/'PROTOCOL.json'))['case_windows']
sids={x[0]for x in spec};sm={r['symbol']:r for r in json.load(open(U/'STOCK_MANIFEST.json'))};raw={}
src={}
def bind(p):
 p=Path(p);src[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
for s in sids:raw[s]=pd.read_parquet(bind(next(p for p in sm[s]['source_sha256']if p.endswith('/signal.parquet'))))
fund=collections.defaultdict(list)
for l in gzip.open(bind(P/'funding.jsonl.gz'),'rt'):
 x=json.loads(l)
 if x['sid']in sids:fund[(x['account'],x['sid'],x['at'][:10])].append(x)
books={}
for a in ['PVR','E31']:
 books[a]=json.load(gzip.open(bind(P/(a+'.json.gz')),'rt'))
out=[]
for x in f.to_dict('records'):
 d=x['day'];s=x['sid'];a=x['account'];nd=nxt.get(d);ts=pd.Timestamp(nd)if nd else None;r=raw[s].loc[ts]if ts in raw[s].index else None
 t=[z for z in books[a]['trades']if z['security_id']==s and z['at'][:10]==nd]
 out.append(dict(account=a,sid=s,signal_close_day=d,next_common_open_day=nd,signal_roles=x['roles'],signal_barriers=x['barriers'],industry_active=x['industry_active'],ACT_on=x['ACT_on'],actual_pending=x['actual_stock_pending'],
  next_raw_open=r.raw_open if r is not None else None,next_full_day_flat_warning=bool(r.raw_high<=r.raw_low)if r is not None else None,
  raw_open_is_next_day_reference_not_signal_information=True,
  funding=json.dumps(fund.get((a,s,nd),[])),actual_trades=json.dumps(t),
  hypothetical_fill='NOT_COMPUTED'))
pd.DataFrame(out).to_csv(O/'FIXED_CASE_NEXT_OPEN.csv',index=False)
pd.DataFrame([z for k,ls in fund.items()for z in ls]).to_csv(O/'FIXED_CASE_ALL_FUNDING.csv',index=False)
# Same first-ever one-buy/full-quantity ACT-sale examples, pure cash net; no total-return or causal loss assertion.
simple=[]
from decimal import Decimal as D
for a,j in books.items():
 hist=collections.defaultdict(list)
 for t in j['trades']:
  s=t['security_id'];h=hist[s]
  if t['side']=='sell'and t['reason']=='ACT_pause'and len(h)==1 and h[0]['side']=='buy'and h[0]['shares']==t['shares']:
   b=h[0];net=D(t['gross_cny'])-D(t['fees_cny'])-D(b['gross_cny'])-D(b['fees_cny'])
   simple.append(dict(account=a,sid=s,buy_at=b['at'],sell_at=t['at'],shares=t['shares'],buy_price=b['price'],sell_price=t['price'],cash_net_excluding_dividends=str(net),buy_kind=b['kind'],reason=t['reason'],not_future_hold_return=True))
  h.append(t)
pd.DataFrame(simple).to_csv(O/'SIMPLE_FIRST_ROUND_ACT_CASH_EXAMPLES.csv',index=False)
bind(__file__);(O/'SUPPLEMENT_SOURCE_HASHES.json').write_text(json.dumps(src,indent=2))
(O/'STARTUP_AND_DISPLAY_FAILURES.json').write_text(json.dumps(dict(script_creation_first_attempt='Python syntax error from shell quoting before execution; no directory/file/account mutation. Corrected creation succeeded.',main_computation_runs=1,main_computation_status='COMPLETE',later_stdout_only_inspection='pandas attribute .at shadows column at; changed inspection to brackets; saved diagnostic unaffected',economic_replays=0),indent=2))
print('supplement',len(out),'case open observations',len(simple),'simple ACT cash pairs')
