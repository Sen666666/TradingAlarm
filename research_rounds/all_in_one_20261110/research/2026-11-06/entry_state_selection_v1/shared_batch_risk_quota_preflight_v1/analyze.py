"""Exact72 baseline and two capped-PVR nominal-risk quota reservation fixtures. No fills."""
from pathlib import Path
from decimal import Decimal as D,localcontext
from fractions import Fraction as F
import sys,json,hashlib,ast
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;B=R/'m3_ab_shared_probe_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025');S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(p,h=None):
 p=Path(p);S[str(p)]=sha(p)
 if h:assert S[str(p)]==h
 return p
def read(p):return json.loads(source(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def dec(x):
 with localcontext() as c:c.prec=60;return D(x.numerator)/D(x.denominator)
for p,h in read(O/'FREEZE.json')['files'].items():assert sha(p)==h
seeds=read(O/'FIXED_72_TICKETS.json');mm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
sys.path[:0]=[str(M/'code'),str(B/'shared_feasibility_v1')]
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
from limits_v3 import Exposure,Snapshot,ReserveBook
for p in [M/'code/market_rules.py',M/'code/sector_account.py',B/'shared_feasibility_v1/limits_v3.py']:source(p)
ss=source(R/'m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py').read_text()
wanted={'finite','true','false','lineage','flags','getmeta','fee','size'}
nodes=[n for n in ast.parse(ss).body if isinstance(n,ast.FunctionDef) and n.name in wanted];assert {n.name for n in nodes}==wanted
env=dict(D=D,np=np,pd=pd,RuleUnavailable=RuleUnavailable,QuantityRule=QuantityRule,FeeComponent=FeeComponent,FeeSchedule=FeeSchedule,version_on=version_on,market_identity_on=market_identity_on,
 rules=read(M/'inputs-v2/market-rules.json'),proxies=read(M/'inputs-v2/economic-protocol.json')['approved_proxy_ids'],meta={},SLIP=D('.0005'))
exec(compile(ast.Module(body=nodes,type_ignores=[]),'ORIGINAL_SIZE_ONLY','exec'),env)
def waterfill(caps,weights,budget):
 assert set(caps)==set(weights) and all(w>0 for w in weights.values()) and all(v>=0 for v in caps.values())
 budget=max(F(0),budget);target=min(budget,sum(caps.values(),F(0)))
 if target==0:return {s:F(0) for s in caps},F(0),target
 if target==sum(caps.values(),F(0)):return caps.copy(),max(caps[s]/weights[s] for s in caps),target
 active=set(caps);out={s:F(0) for s in caps};left=target
 while active:
  lam=left/sum((weights[s] for s in active),F(0))
  hit=sorted(s for s in active if caps[s]<=lam*weights[s])
  if not hit:
   for s in active:out[s]=lam*weights[s]
   break
  for s in hit:out[s]=caps[s];left-=caps[s];active.remove(s)
 assert sum(out.values(),F(0))==target
 assert all(out[s]==min(caps[s],lam*weights[s]) for s in caps)
 return out,lam,target
# Frozen arithmetic branches, no empirical parameter search.
for caps,weights,budget,expect in [({'a':F(1),'b':F(9)},{'a':F(1),'b':F(1)},F(6),{'a':F(1),'b':F(5)}),({'a':F(2)},{'a':F(3)},F(-1),{'a':F(0)}),({'a':F(0),'b':F(2)},{'a':F(1),'b':F(1)},F(3),{'a':F(0),'b':F(2)})]:
 assert waterfill(caps,weights,budget)[0]==expect
source(R/'shared_ab_entry_selection_attribution_v1/PROTOCOL.md')
source('/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py')
source('/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/RULES.txt')
source(R/'shared_probe_order_credit_identity_v1/permutation.py')
props={};snapshot_checks=[]
spec={'2022':B/'known_halt_contract_v1/cohort_2022_recovery_v2','2024_924':B/'indexed_execution_v1/cohort_2024_924'}
for win,base in spec.items():
 batch=[x for x in seeds if x['window']==win];sd=batch[0]['signal_day'];od=batch[0]['open_day']
 acts=read(base/'ACTIONS.json');audit=read(base/'AUDIT.json')
 assert not [x for x in acts if x['day'][:10]<od]
 s=next(x for x in audit if x['type']=='CLOSE_SNAPSHOT' and x['day'][:10]==sd)
 a=next(x for x in audit if x['type']=='ALL_RESERVATIONS_COMPLETE' and x['day'][:10]==od)
 assert s['certified'] and D(s['Nd'])==D('1200000') and D(a['cash_before_fills'])==D('1200000')
 assert not [x for x in audit if x['type']=='PROMOTED' and x['day'][:10]<=od]
 assert not [x for x in acts if x['day'][:10]==od and x['side']=='buy_add']
 snapshot_checks.append(dict(window=win,common_pre_INIT_NAV='1200000',cash='1200000',probe_risk='0',holdings=0,ADD_reservations=0,NAV_certified=True))
 for x in batch:
  sid=x['sid'];m=mm[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));fp=m['refs']['facts']
  raw=pd.read_parquet(source(p,m['source_sha256'][p]),columns=['source_kind','source_path','segment_id','adjustment_factor','raw_open','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']).loc[:od];fact=pd.read_parquet(source(fp,m['output_sha256'][fp])).loc[:sd];sg=raw.loc[sd];op=raw.loc[od]
  assert env['flags'](sg) and env['finite'](op.raw_open) and op.raw_open>0 and env['lineage'](sg)==env['lineage'](op) and np.isclose(sg.adjustment_factor,op.adjustment_factor,rtol=1e-11)
  floor=D(str(fact.at[pd.Timestamp(sd),'i_floor']))/D(str(sg.adjustment_factor));openp=D(str(op.raw_open));px=openp*D('1.0005')
  assert openp>floor
  formula,_,_,fs,par=env['size'](sid,pd.Timestamp(od),px,floor,D('24000'),D('3000'),int(x['prior20_capacity']))
  qr,_,_=env['getmeta'](sid,pd.Timestamp(od));before=qr.buy_floor(min(formula,int(x['close_q'])))
  assert formula==x['source_formula_q'] and before==x['before_shared_q'],(win,sid,formula,before,x)
  assert D(str(x['PVR_score'])).is_finite() and D(str(x['PVR_score']))>0
  delta=px-floor;assert before==0 or delta>0
  props[(win,sid)]=dict(x,px=px,floor=floor,qr=qr,fs=fs,par=par,d=delta,weight=F(D(str(x['PVR_score']))),rmax=F(before)*F(delta),source_formula_rmax=F(formula)*F(delta))
def reserve_batch(win,arm,quota=None):
 batch=sorted([v for (w,s),v in props.items() if w==win],key=lambda x:(-x['PVR_score'],x['sid']))
 book=ReserveBook(Snapshot(D('1200000'),D(0),D('1200000'),D('1200000'),(),(),(),'ORIGINAL_EMPTY_COMMON_PRE_INIT'))
 out=[]
 for rank,x in enumerate(batch,1):
  sid=x['sid'];q=x['before_shared_q'];qr=x['qr'];px=x['px'];fl=x['floor'];fs=x['fs'];par=x['par'];trials=[];last=[];lim=quota[sid] if quota is not None else None
  while q>0:
   fee=env['fee'](q,px,fs,'buy',par);sf=env['fee'](q,fl*D('.9995'),fs,'sell',par);fee_risk=max(D(0),D(q)*(px-fl*D('.9995'))+fee+sf)
   reasons=[]
   if D(q)*px+fee>D('24000'):reasons.append('original_round_budget')
   if fee_risk>D('3000'):reasons.append('original_round_fee_risk')
   if lim is not None and F(q)*F(x['d'])>lim:reasons.append('frozen_batch_quota')
   e=Exposure(sid,x['round_id'],x['sector'],'probe',int(q),px,fl,fee,'live');reasons+=book.reasons(e)
   trials.append(dict(q=q,reasons=reasons));last=reasons
   if not reasons:
    assert not book.reserve(e);break
   q=qr.buy_floor(q-1)
  if arm=='ORIGINAL':assert q==x['original_shared_q'],(win,sid,q,x['original_shared_q'])
  fee=env['fee'](q,px,fs,'buy',par) if q else D(0);sf=env['fee'](q,fl*D('.9995'),fs,'sell',par) if q else D(0)
  nominal=D(q)*x['d'];fr=max(D(0),D(q)*(px-fl*D('.9995'))+fee+sf) if q else D(0)
  minrisk=F(qr.buy_minimum)*F(x['d'])
  out.append({k:x[k] for k in ['window','signal_day','open_day','event_id','sid','name','sector','PVR_score','source_formula_q','before_shared_q','close_q','original_shared_q']}|
   dict(arm=arm,rank=rank,reserved_q=q,minimum_quantity=qr.buy_minimum,buy_step=qr.buy_step,buy_proxy=px,raw_I_floor=fl,nominal_per_share=x['d'],
   before_shared_rmax=dec(x['rmax']),source_formula_rmax=dec(x['source_formula_rmax']),
   quota=dec(lim) if lim is not None else None,quota_numerator=str(lim.numerator) if lim is not None else None,quota_denominator=str(lim.denominator) if lim is not None else None,
   quota_less_than_minimum=bool(lim is not None and minrisk>lim),minimum_nominal_risk=dec(minrisk),nominal_risk=nominal,fee_inclusive_risk=fr,
   gross=D(q)*px,buy_fee=fee,stop_sell_fee=sf,cash=D(q)*px+fee,buy_fee_pct=fee/(D(q)*px)*100 if q else None,
   planned_roundtrip_fee_pct=(fee+sf)/(D(q)*px)*100 if q else None,minimum_quantity_selected=q==qr.buy_minimum,last_reasons='|'.join(last) if q==0 else '',
   unused_own_quota=dec(lim-F(q)*F(x['d'])) if lim is not None else None,trial_count=len(trials)))
 selected=[x for x in out if x['reserved_q']>0];pc,pr=book.resources(pool='probe')
 totalgross=sum((x['gross'] for x in selected),D(0));fees=sum((x['buy_fee'] for x in selected),D(0));stopfees=sum((x['stop_sell_fee'] for x in selected),D(0))
 fee_ratios=[x['buy_fee_pct'] for x in selected]
 summary=dict(window=win,arm=arm,original_ticket_count=len(out),reserved_names=len(selected),reserved_sectors=len({x['sector'] for x in selected}),
  reserved_gross=totalgross,reserved_cash=book.reserved_cash,nominal_risk=pr,fee_inclusive_risk=sum((x['fee_inclusive_risk'] for x in selected),D(0)),
  buy_fees=fees,planned_stop_sell_fees=stopfees,weighted_buy_fee_pct=fees/totalgross*100 if totalgross else None,
  mean_order_buy_fee_pct=sum(fee_ratios,D(0))/len(fee_ratios) if fee_ratios else None,max_order_buy_fee_pct=max(fee_ratios,default=None),
  minimum_quantity_selected=sum(x['minimum_quantity_selected'] for x in selected),quota_below_minimum_count=sum(x['quota_less_than_minimum'] for x in out),
  unfunded_count=sum(x['reserved_q']==0 for x in out),original_fee_adjusted_headroom=(D('1200000')-fees)*D('.005')-pr,
  nominal_unspent_before_fee_adjustment=D('6000')-pr,unused_cash=D('1200000')-book.reserved_cash,unchanged_preallocation_NAV='1200000',
  selected=[dict(sid=x['sid'],name=x['name'],q=x['reserved_q'],nominal_risk=x['nominal_risk']) for x in selected],
  all_original_q_exact=arm=='ORIGINAL',fills=0)
 return out,summary
rows=[];summary=[]
# Exact all72 baseline first, before any alternative is computed.
for win in spec:
 r,s=reserve_batch(win,'ORIGINAL');rows+=r;summary.append(s)
save('BASELINE_72_QA.json',dict(exact_rows=sum(len([x for x in seeds if x['window']==w]) for w in spec),windows=2,all_source_formula_q_exact=True,all_before_shared_q_exact=True,all_final_reserved_q_exact=True,snapshots=snapshot_checks))
qrows=[];lambdas=[]
for win in spec:
 batch={sid:x for (w,sid),x in props.items() if w==win};caps={sid:x['rmax'] for sid,x in batch.items()};weights={sid:x['weight'] for sid,x in batch.items()}
 quota,lam,target=waterfill(caps,weights,F(6000))
 lambdas.append(dict(window=win,lambda_numerator=lam.numerator,lambda_denominator=lam.denominator,lambda_decimal=dec(lam),raw_nominal_headroom='6000',sum_rmax=dec(sum(caps.values(),F(0))),quota_sum_exact=dec(sum(quota.values(),F(0))),saturated_names=sum(quota[s]==caps[s] for s in caps),target=dec(target)))
 for sid,x in batch.items():qrows.append(dict(window=win,sid=sid,name=x['name'],weight=dec(weights[sid]),before_shared_q=x['before_shared_q'],source_formula_q=x['source_formula_q'],rmax=dec(caps[sid]),quota=dec(quota[sid]),quota_numerator=quota[sid].numerator,quota_denominator=quota[sid].denominator))
 r,s=reserve_batch(win,'FROZEN_PVR_NOMINAL_RISK_QUOTA',quota);rows+=r;summary.append(s)
for win in spec:
 base=next(s for s in summary if s['window']==win and s['arm']=='ORIGINAL');alt=next(s for s in summary if s['window']==win and s['arm']!='ORIGINAL')
 old={x['sid'] for x in base['selected']};new={x['sid'] for x in alt['selected']}
 alt['retained_original_names']=sorted(old&new);alt['lost_original_names']=sorted(old-new);alt['added_names']=sorted(new-old)
 # All unfilled/rounded quota is idle by contract, not refilled.
 assert alt['original_fee_adjusted_headroom']>=0
pd.DataFrame(rows).to_csv(O/'TWO_START_RESERVATIONS.csv',index=False);pd.DataFrame(qrows).to_csv(O/'FROZEN_QUOTAS.csv',index=False)
save('LAMBDA.json',lambdas);save('SUMMARY.json',summary)
save('FINAL_QA.json',dict(original_rows_exact=72,windows=2,formulas=1,synthetic_edge_checks=3,parameter_searches=0,source_files=len(S),new_fills=0,new_accounts=0,subsequent_days=0,negative_headroom_all_quotas_zero=True,source_hashes_unchanged=all(sha(p)==h for p,h in S.items())))
assert all(sha(p)==h for p,h in S.items());save('SOURCE_SHA256.json',S)
print(json.dumps(summary,ensure_ascii=False,default=str,indent=2));print(json.dumps(lambdas,ensure_ascii=False,default=str,indent=2))
