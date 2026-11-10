"""Independent persisted-ledger audit; never imports or runs strategy engine."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
import json,hashlib,collections
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;E=O.parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
dt=lambda v:pd.Timestamp(v)
close=lambda a,b:abs(D(str(a))-D(str(b)))<D('0.0000001')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
rules=read(B/'inputs-v2/market-rules.json')
def version(rows,day):
 rows=[x for x in rows if x['from']<=day and (not x.get('to') or day<x['to'])]
 assert len(rows)==1;return rows[0]
def fee(sid,day,q,p,side):
 day=str(dt(day).date());venue=version(rules['venue_versions'][sid],day)['venue'];schedule=version(rules['fee_versions'][venue],day)['schedule'];total=D(0)
 for c in schedule['components']:
  if c.get('side','both') not in ['both',side]:continue
  basis=c.get('amount_basis','notional');amount=D(q)*D(str(p)) if basis=='notional' else D(q) if basis=='shares' else D(q)*D(str(rules['security_metadata'][sid]['par_value']))
  x=max(D(str(c.get('minimum_local',0))),amount*D(str(c['rate'])))
  if c.get('maximum_local') is not None:x=min(x,D(str(c['maximum_local'])))
  if c.get('rounding_unit') is not None:
   u=D(str(c['rounding_unit']));x=(x/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
  total+=x
 return total

csv=lambda p:pd.read_csv(p,float_precision='round_trip',low_memory=False)
old=csv(E/'lifecycle_v1/ALL_2026H1_SEMI_ROUNDS.csv');old=old[old.arm.eq('A_UNION_B')].set_index('round_id',drop=False)
z=csv(O/'ALL_FIXED46_ROUNDS.csv').set_index('round_id',drop=False);recov=csv(O/'economic/ROUNDS.csv').set_index('round_id',drop=False)
a=csv(O/'ALL_FIXED46_ACTIONS.csv');oa=csv(E/'lifecycle_v1/ACTIONS.csv');oa=oa[oa.round_id.isin(old.index)]
claims=read(O/'economic/CLAIMS.json');events={e['economic_event_id']:e for e in read(O/'ECONOMIC_EVENTS.json')}
led=csv(O/'economic/CLAIM_LEDGER.csv');regs=csv(O/'economic/REGISTRATIONS.csv');bridges=read(O/'economic/BRIDGES.json')
rep=csv(O/'report/CORE_AND_FULL_ROUNDS.csv').set_index('round_id',drop=False);cov=csv(O/'report/FINANCIAL_COVERAGE.csv').set_index('round_id',drop=False)
closed='COMPLETE_CONDITIONAL_STOCK_ROUND';checks=collections.Counter()
assert len(z)==46 and z.index.is_unique and set(z.index)==set(old.index)
assert set(recov.index)==set(old[old.status.str.contains('UNKNOWN')].index) and len(recov)==20
def eq(x,y):
 if pd.isna(x) and pd.isna(y):return True
 if isinstance(x,(bool,np.bool_)) or isinstance(y,(bool,np.bool_)):return x==y
 if isinstance(x,(int,float,np.number)) and isinstance(y,(int,float,np.number)):return close(x,y)
 if isinstance(x,str) and isinstance(y,str) and len(x)>=10 and x[:4].isdigit() and x[4]=='-':
  try:return dt(x)==dt(y)
  except:pass
 return x==y
def compare_rows(x,y):
 assert len(x)==len(y)
 for i in range(len(x)):
  for c in x.columns:assert eq(x.iloc[i][c],y.iloc[i][c]),(i,c,x.iloc[i][c],y.iloc[i][c])
retained=old[~old.status.str.contains('UNKNOWN')]
for rid,r in retained.iterrows():
 for c,v in r.items():assert eq(v,z.loc[rid,c]),(rid,c,'retained changed')
compare_rows(oa[oa.round_id.isin(retained.index)].reset_index(drop=True),a[a.round_id.isin(retained.index)].reset_index(drop=True))
checks['unchanged_retained_permits']=26
manifest={r['symbol']:r for r in read(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))}
frames={}
for sid in z.sid.unique():
 path=next(p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet'));assert sha(path)==manifest[sid]['source_sha256'][path];frames[sid]=pd.read_parquet(path)
groups={rid:g.to_dict('records') for rid,g in a.groupby('round_id',sort=False)};cb=collections.defaultdict(list)
for c in claims:cb[c['owner_round_id']].append(c)
assert len({(c['owner_round_id'],c['economic_event_id']) for c in claims})==len(claims)==7
def inventory(trades):
 core=add=0;cash=fees=spent=D(0)
 for x in trades:
  n=int(x['q']);p=D(str(x['price']));f=D(str(x['fee']));side=x['side']
  if side=='buy_core':core+=n
  elif side=='buy_add':add+=n
  elif side=='sell_add':assert n==add;add=0
  elif side=='sell_all':assert n==core+add;core=add=0
  else:raise AssertionError(side)
  if side.startswith('buy'):cash-=n*p+f;spent+=n*p+f
  else:cash+=n*p-f
  fees+=f;assert core>=0 and add>=0
 return core,add,cash,fees,spent
for rid,r in z.iterrows():
 trades=groups.get(rid,[]);q=0;bought={}
 for x in trades:
  n=int(x['q']);p=D(str(x['price']));f=D(str(x['fee']));day=dt(x['day']);buy=x['side'].startswith('buy')
  op=D(str(frames[r.sid].loc[day,'raw_open']));assert close(p,op*(D('1.0005') if buy else D('.9995'))),(rid,'open')
  assert close(f,fee(r.sid,day,n,p,'buy' if buy else 'sell')),(rid,'fee')
  if buy:q+=n;bought[day]=bought.get(day,0)+n
  else:assert n<=q-bought.get(day,0),(rid,'T+1');q-=n
  assert q>=0;checks['action_open_fees_T1']+=1
 core,add,cash,fees,spent=inventory(trades)
 paid=sum((D(c['amount']) for c in cb[rid] if c['settled']),D(0));recv=sum((D(c['amount']) for c in cb[rid] if c['recognized'] and not c['settled']),D(0))
 if trades:
  assert core==r.core_qty and add==r.add_qty and close(fees,r.all_fees) and close(spent,r.total_buy_cash)
  if rid in recov.index:assert close(cash+paid,r.cash_after_payouts) and close(recv,r.receivable_after_payouts)
  else:assert close(cash,r.cashflow_to_date)
 if r.status==closed:assert core+add==0 and close(cash+paid+recv,r.net_pnl) and close((cash+paid+recv)/spent,r.net_return_on_buy_cash)
 if 'UNKNOWN' in r.status:assert all(dt(x['day'])<dt(r.status_day) for x in trades)
 checks['round_inventory_cash_fee_reconciliation']+=1
for c in claims:
 e=events[c['economic_event_id']];r=z.loc[c['owner_round_id']];assert r.sid==e['sid']==c['sid']
 trs=[x for x in groups[r.round_id] if dt(x['day'])<=dt(e['record_date'])];core,add,*_=inventory(trs)
 assert c['record_q']==core+add and c['core_record_q']==core
 assert D(c['amount'])==D(core+add)*D(e['d_cash'])*D('.8') and D(c['core_amount'])==D(core)*D(e['d_cash'])*D('.8')
 assert c['recognized'] and c['settled']
 l=led[led.round_id.eq(r.round_id)&led.economic_event_id.eq(c['economic_event_id'])]
 assert len(l)==2 and set(l.event)=={'ACCRUE_NET80','PAY_CLOSE_TRANSFER'}
 for x in l.itertuples():
  if x.event=='ACCRUE_NET80':assert dt(x.day)==dt(e['ex_date']) and close(x.cash_delta,0) and close(x.receivable_delta,c['amount'])
  else:assert dt(x.day)==dt(e['pay_date']) and close(x.cash_delta,c['amount']) and close(x.receivable_delta,-D(c['amount'])) and dt(x.available_from)>dt(x.day)
 checks['claim_ownership_cash_clock']+=1
assert sum((D(c['amount']) for c in claims),D(0))==D('419.732')
for x in regs.itertuples():
 e=events[x.economic_event_id];assert dt(x.inventory_snapshot_day)==dt(e['record_date'])
 if x.state=='HELD':
  core,add,*_=inventory([t for t in groups[x.owner_round_id] if dt(t['day'])<=dt(e['record_date'])]);assert core+add==x.record_q and core==x.core_record_q
 else:assert x.state=='FLAT' and x.record_q==0
 checks['registration_rows']+=1
# Independently rebuild every persisted profitability observation from trades and accrued claims.
marks=csv(O/'economic/PROFIT_GATES.csv')
for x in marks.itertuples():
 r=z.loc[x.round_id];day=dt(x.day);trades=[t for t in groups[r.round_id] if dt(t['day'])<day or (dt(t['day'])==day and (x.phase=='CLOSE' or t['side']=='sell_add'))]
 core,add,cash,_,_=inventory(trades);q=core+add
 div=sum((D(c['amount']) for c in cb[r.round_id] if dt(c['ex_date'])<=day),D(0))
 receiv=sum((D(c['amount']) for c in cb[r.round_id] if dt(c['ex_date'])<=day<=dt(c['pay_date'])),D(0))
 px=D(str(frames[r.sid].loc[day,'raw_close' if x.phase=='CLOSE' else 'raw_open']))*D('.9995')
 val=cash+div+D(q)*px-fee(r.sid,day,q,px,'sell')
 assert close(val,x.net_equity) and bool(val>0)==x.strictly_positive and close(receiv,x.receivable),(r.round_id,str(day),x.phase,'mark')
 checks['profit_gate_reconstruction']+=1
for x in a[a.side.eq('buy_add')].itertuples():
 assert x.prior_round_net>0
 checks['strictly_profitable_adds']+=1
# Existing action prefixes and terminal pre-interruption marks are unchanged.
for rid,r in old[old.status.str.contains('UNKNOWN')].iterrows():
 cutoff=dt(r.status_day)
 aa=oa[oa.round_id.eq(rid)&pd.to_datetime(oa.day).lt(cutoff)].reset_index(drop=True)
 bb=a[a.round_id.eq(rid)&pd.to_datetime(a.day).lt(cutoff)].reset_index(drop=True);compare_rows(aa,bb)
 mm=marks[marks.round_id.eq(rid)&marks.phase.eq('CLOSE')&pd.to_datetime(marks.day).eq(dt(r.last_known_mark_day))]
 assert len(mm)==1 and close(mm.iloc[0].net_equity,r.last_mark_net),(rid,'preinterrupt mark')
 checks['original_preinterruption_prefix']+=1
source=[x for x in bridges if x['kind']=='EXACT_SOURCE_TRANSITION'];cashbridges=[x for x in bridges if x['kind']=='HELD_COORDINATE']
assert len(source)==16 and len(cashbridges)==7
whitelist={r['sid']:r for r in read(E/'source_bridge_2026_feasibility_v1/SOURCE_BRIDGE_CANDIDATES.json')}
for x in source:
 w=whitelist[x['sid']];assert dt(x['day'])==dt(w['transition_day']) and list(x['from_lineage'])==list(map(str,w['from_lineage'])) and list(x['to_lineage'])==list(map(str,w['to_lineage']))
unknown=z[z.status.str.contains('UNKNOWN')]
assert set(unknown.sid)=={'300456.SZ','300661.SZ','300373.SZ'} and set(unknown.status)=={'SOURCE_CHANGE_PATH_UNKNOWN'} and all(dt(x)==dt('2026-05-18') for x in unknown.status_day)
assert not set(unknown.sid)&set(whitelist)
for rid,r in rep[rep.status.eq(closed)].iterrows():
 q=int(r.entry_q);bf=fee(r.sid,r.entry_day,q,r.entry_price,'buy');sf=fee(r.sid,r.exit_day,q,r.exit_price,'sell');div=sum((D(c['core_amount']) for c in cb[rid] if c['recognized']),D(0))
 cost=q*D(str(r.entry_price))+bf;net=q*D(str(r.exit_price))-sf-cost+div
 assert all(close(v,r[k]) for k,v in [('core_buy_fee',bf),('core_sell_fee',sf),('core_dividend_net80',div),('core_buy_cash',cost),('core_net',net),('core_return',net/cost)])
 checks['core_independent_fee_at_full_times']+=1
# Coverage audit against original local action sources, not report labels alone.
admitted={(e['sid'],dt(e['ex_date'])) for e in events.values()}
for rid,r in cov.iterrows():
 rr=z.loc[rid];ac=read(AS/'inputs-v1/actions'/f'{r.sid}.json')
 assert ac['series_id']==r.sid and ac['currency']=='CNY'
 empty=ac.get('raw_response_empty') or not ac.get('coverage_evidence')
 for ev in ac.get('coverage_evidence',[]):
  assert sha(ev['path'])==ev['sha256'];rights=read(ev['path']);empty=empty or not rights.get('records')
 # All dated/undated unresolved records require scrutiny; these frozen 46 have none.
 unresolved=list(ac.get('unresolved',[]))
 for ev in ac.get('coverage_evidence',[]):unresolved+=read(ev['path']).get('unparsed',[])
 if pd.isna(rr.entry_day):assert r.financial_coverage_status=='NO_CONFIRMED_HOLDING'
 else:
  end=dt(rr.exit_day if rr.status==closed else rr.status_day);inclusive=rr.status==closed or 'CENSORED' in rr.status
  held=[e for e in ac['events'] if dt(rr.entry_day)<dt(e['effective_date']) and (dt(e['effective_date'])<=end if inclusive else dt(e['effective_date'])<end)]
  for ev in held:
   ed=dt(ev['effective_date']);assert (r.sid,ed) in admitted,(rid,'unadmitted held event')
   ee=next(e for e in events.values() if e['sid']==r.sid and dt(e['ex_date'])==ed)
   assert any(c['economic_event_id']==ee['economic_event_id'] and c['recognized'] for c in cb[rid])
  for un in unresolved:
   row=un.get('row',un);ud=row.get('1') or row.get('effective_date') or row.get('date')
   if ud is None:empty=True;continue
   ud=pd.to_datetime(str(ud),format='%Y%m%d') if '-' not in str(ud) else dt(ud)
   if dt(rr.entry_day)<ud and (ud<=end if inclusive else ud<end):empty=True
  want='COVERAGE_UNKNOWN' if empty else 'VERIFIED_ACTIONS_SCENARIO' if held else 'LOCAL_NO_ACTION_EVIDENCE'
  assert r.financial_coverage_status==want,(rid,want,r.financial_coverage_status)
 assert r.evidence_usable_closed==(rr.status==closed and r.financial_coverage_status in ['VERIFIED_ACTIONS_SCENARIO','LOCAL_NO_ACTION_EVIDENCE'])
 checks['financial_coverage_rows']+=1
bad=cov[cov.execution_status.eq(closed)&~cov.evidence_usable_closed]
assert set(bad.sid)=={'688220.SH','688234.SH','688141.SH','688107.SH'}
perf=csv(O/'report/PERFORMANCE.csv')
for x in perf.itertuples():
 g=rep if x.scope=='ALL_FIXED46' else rep.loc[recov.index];c=g[g.evidence_usable_closed];p='core_net' if x.layer=='CORE' else 'net_pnl';ret='core_return' if x.layer=='CORE' else 'net_return_on_buy_cash'
 w=c[c[p]>0];l=c[c[p]<=0]
 assert x.fixed_permits==len(g) and x.closed==sum(g.status.eq(closed)) and x.covered_closed==len(c) and x.wins==len(w) and x.losses==len(l)
 assert close(x.covered_closed_win_rate,len(w)/len(c)) and close(x.covered_closed_mean_return,c[ret].mean())
 assert x.tail_ge20==sum(c[ret]>=.2) and x.tail_ge50==sum(c[ret]>=.5)
 checks['metric_denominators']+=1
held=set(z[z.status.eq('OPEN_CENSORED_AT_2026_06_30')].index);oldheld=set(old[old.status.eq('OPEN_CENSORED_AT_2026_06_30')].index);newheld=set(recov[recov.status.eq('OPEN_CENSORED_AT_2026_06_30')].index)
assert len(oldheld)==9 and len(newheld)==6 and not oldheld&newheld and held==oldheld|newheld
overlaps=[]
for sid,g in z[z.entry_day.notna()].groupby('sid'):
 rows=list(g.sort_values('entry_day').itertuples())
 for prior,nxt in zip(rows,rows[1:]):
  end=dt(prior.exit_day) if prior.status==closed else dt('2026-06-30')
  if dt(nxt.entry_day)<=end:overlaps.append([prior.round_id,nxt.round_id])
# Frozen execution, original inputs, all persisted economics and report hashes.
pre=read(O/'PRE_ECONOMIC_AUDIT.json');once=read(O/'ECONOMIC_RUN_ONCE.json')
assert once['review_sha256']==sha(O/'PRE_ECONOMIC_AUDIT.json')
for name,h in pre['code_sha256'].items():assert sha(O/name)==h
for p,h in pre['input_sha256'].items():assert sha(p)==h
for root in [O/'economic',O/'report']:
 for p,h in read(root/'OUTPUT_HASHES.json').items():assert sha(root/p)==h
for p,h in read(O/'economic/SOURCE_HASHES.json').items():assert sha(p)==h
out=dict(result='PASS_INDEPENDENT_FIXED20_PERSISTED_POST_AUDIT',checks=dict(checks),scope='Fixed20 recovery plus preserved26 diagnostic only',status_counts=z.status.value_counts().to_dict(),recovery_status_counts=recov.status.value_counts().to_dict(),original_held=9,new_held=6,total_held=15,pending=int(z.status.eq('BUY_PENDING_CENSORED_AT_DATA_END').sum()),source_bridges=16,cash_bridges=7,claims=7,paid_net80='419.732',closed=25,covered_closed=21,unknown_coverage_closed=4,unknown_coverage=[dict(sid=r.sid,reason=r.coverage_reasons,original_or_recovered='recovered' if rid in recov.index else 'original') for rid,r in bad.iterrows()],fixed_permit_overlaps=overlaps,metrics=perf.to_dict('records'),economic_reruns_by_auditor=0,engine_sha256=sha(O/'engine.py'),pre_audit_sha256=sha(O/'PRE_ECONOMIC_AUDIT.json'),once_sha256=sha(O/'ECONOMIC_RUN_ONCE.json'),economic_seal_sha256=sha(O/'economic/OUTPUT_HASHES.json'),report_seal_sha256=sha(O/'report/OUTPUT_HASHES.json'),limits=['Non-PIT archives, conditional OPEN proxies and NET80 tax scenario, not actual account returns.','No complete strategy/reselection/occupancy reconstruction.','Old14 execution-closed and new21 evidence-usable are different denominators; do not call their win-rate difference improvement.','CORE is initial-layer attribution at FULL entry/exit with independent fees, not core-only strategy.','Held/UNKNOWN/pending/nofill do not enter closed win counts.','No economic rerun performed. Original preinterruption persisted prefixes and marks verified; physical-prefix causality separately established by pre-audit bridge-off and synthetic integrated tests.'])
(O/'POST_ECONOMIC_AUDIT.json').open('x').write(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
