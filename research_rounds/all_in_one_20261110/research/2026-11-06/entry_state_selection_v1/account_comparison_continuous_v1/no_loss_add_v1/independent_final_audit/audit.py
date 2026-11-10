"""Read saved final checkpoint; no account construction or execution."""
import sys,pickle,hashlib,json
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
OUT=Path(__file__).resolve().parent
P=OUT.parent
sys.path.insert(0,str(P))
import profit_gate as PG # pickle class registration only
C=PG.C
run=P/'run_1200000';cp=run/'latest_checkpoint/checkpoint.pkl'
raw=cp.read_bytes();h=hashlib.sha256(raw).hexdigest();meta=json.loads(cp.with_suffix('.json').read_text());assert h==meta['sha256']
x=pickle.loads(raw);done=json.loads((run/'DONE.json').read_text());assert done['completed'] and str(x['last_completed_event'])==done['last_event']
a=x['accounts']['PVR'];r=x['runner'];assert list(x['accounts'])==['PVR'] and r['rank_mode']=='PVR_SLOT1' and a['initial_cash']==D(1200000)
fm=C.J.M.E.FastMarket.__new__(C.J.M.E.FastMarket);fm.cache_at=None
rulespath=C.J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json';protocolpath=C.J.M.BP.C.OLD/'inputs-v2/economic-protocol.json'
fm.rules=json.loads(rulespath.read_text());fm.protocol=json.loads(protocolpath.read_text())
s={};counts=Counter();js=defaultdict(list);gs=defaultdict(list)
tr={(t['at'],t['security_id'],t['side']):t for t in a['trades']};assert len(tr)==len(a['trades'])
for j in a['journal']:js[j['at']].append(j)
for g in r['profit_gate_events']:gs[g['at']].append(g)
for at in sorted(set(js)|set(gs)):
 rows=js[at]
 # Original OPEN sells settle before admission; buys occur after all routes.
 for j in rows:
  sid=j['sid'];q,k,rr=s.get(sid,(0,D(0),0))
  if j['kind']=='actual_split':
   nq=int(D(q)*j['ratio']);counts['splits']+=1;counts['fractional_splits']+=D(q)*j['ratio']!=nq
   s[sid]=(nq,k if nq else D(0),rr)
  elif j['kind']=='real_sell_fill':
   n=j['shares'];assert 0<n<=q;counts['partial_sells']+=n<q;counts['sell_fills']+=1
   s[sid]=(q-n,k*D(q-n)/D(q) if q>n else D(0),rr)
 verdicts={}
 for g in gs[at]:
  sid=g['sid'];q,k,rr=s.get(sid,(0,D(0),0))
  assert g['qty']==q and g['cost']==k,(at,sid,'cost mismatch')
  assert g['signal_at']<at and (at.hour,at.minute)==(9,30)
  assert g['round']==rr and g['dividend_cost_convention']=='EXCLUDED'
  counts['gate_decisions']+=1
  if q:
   par=fm.rules.get('security_metadata',{}).get(sid,{}).get('par_value')
   fee=C.J.LR.fees(q,g['known_open']*D('.9995'),fm.fees(sid,at),'sell',D(str(par)) if par is not None else None)
   assert fee==g['estimated_sell_fee'];counts['dated_fee_exact']+=1
   v=D(q)*g['known_open']*D('.9995')-fee
   assert v==g['net_liquidation'] and g['net_profit']==v-k and g['allowed']==(v>k)
   assert g['buy_proxy']==g['known_open']*D('1.0005')
  else:assert g['allowed'];counts['flat_gate_allowed']+=1
  counts['gate_rejections']+=not g['allowed'];verdicts[(sid,g['role'])]=g
 for j in rows:
  if j['kind']!='real_buy_fill':continue
  sid=j['sid'];q,k,rr=s.get(sid,(0,D(0),0));g=verdicts[(sid,j['role'])]
  assert g['allowed'] and g['qty']==q and g['cost']==k
  if q:assert g['net_liquidation']>k;counts['held_buy_pass']+=1
  else:counts['flat_buy_pass']+=1;counts['flat_reentry_buy_pass']+=rr>0
  t=tr[(at,sid,'buy')]
  assert t['shares']==j['shares'] and t['fees_cny']==j['fees'] and D(j['shares'])*j['price']==t['gross_cny']
  assert t['raw_open']*D('1.0005')==t['price'] and g['buy_proxy']==t['price']
  s[sid]=(q+j['shares'],k+t['gross_cny']+t['fees_cny'],rr+(q==0));counts['buy_fills']+=1
b=r['cost_books']['PVR'];assert b.journal_cursor==len(a['journal'])
for sid in set(s)|set(b.states)|set(a['positions']):
 q,k,rr=s.get(sid,(0,D(0),0));saved=b.states.get(sid,{'qty':0,'cost':D(0),'round':0})
 assert (q,k,rr)==(saved['qty'],saved['cost'],saved['round'])
 assert q==(a['positions'][sid].shares if sid in a['positions'] else 0)
assert counts['buy_fills']==sum(t['side']=='buy'for t in a['trades'])
assert counts['sell_fills']==sum(t['side']=='sell'for t in a['trades'])
assert counts['gate_decisions']==done['profit_gate_decisions'] and counts['gate_rejections']==done['profit_gate_rejections']
assert len(r['daily'])==len(r['open_checks'])==done['daily_rows']==1054
assert all(v['cash_gap']==0 for v in r['open_checks'])
assert str(a['current_nav'])==done['final_nav']['PVR']
bad=[p for p,h0 in x['source_freeze'].items()if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h0];assert not bad
report=dict(passed=True,checkpoint_sha256=h,last_completed_event=str(x['last_completed_event']),counts=dict(counts),journal_cursor=b.journal_cursor,journal_rows=len(a['journal']),stock_states=len(s),cash_bridge_rows=len(r['open_checks']),maximum_cash_bridge_residual='0',source_files_verified=len(x['source_freeze']),final_NAV=str(a['current_nav']),initial_cash=str(a['initial_cash']),no_new_account_constructed=True,no_account_execution=True,method='Independent Q/K reconstruction from native journal order and actual buy gross+fees; pro-rata stock-wide cost retirement; dividends do not reduce K; splits change only Q except zero Q resets K; dated original schedule and par metadata independently recompute every held-position fee. Actual buys linked to same-clock same-role gate. Cash bridge checked from saved original event checks.',limitations=['Fixed future 1709 universe and causal OPEN fill proxy remain assumptions; no tradability or PIT proof.','Original immutable fee helper used, but no market data loading or C.inputs call.','No claim that this gate improves returns or that rejected orders would necessarily have filled.'],audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),fee_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [rulespath,protocolpath]})
(OUT/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
