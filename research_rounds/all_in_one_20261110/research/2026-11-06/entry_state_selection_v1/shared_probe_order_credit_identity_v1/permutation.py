"""Two original empty-account opening books, one fixed permutation each. No fills."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;B=R/'m3_ab_shared_probe_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path[:0]=[str(M/'code'),str(B/'shared_feasibility_v1')]
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
from limits_v3 import Exposure,Snapshot,ReserveBook
S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);S[str(p)]=sha(p);return json.loads(p.read_text())
def source(p,expected):
 S[str(p)]=sha(p);assert S[str(p)]==expected;return p
def fee(q,p,fs,side,par):return sum(fs.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=par).values(),D(0))
rules=read(M/'inputs-v2/market-rules.json');proxies=read(M/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
mm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
ev=pd.read_csv(R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv').set_index('event_id')
S[str(R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv')]=sha(R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv')
spec=[('2022',B/'known_halt_contract_v1/cohort_2022_recovery_v2','2022-01-05','2022-01-06'),('2024_924',B/'indexed_execution_v1/cohort_2024_924','2024-09-02','2024-09-03')]
rows=[];summ=[]
for w,base,sd,od in spec:
 ds=[x for x in read(base/'DECISIONS.json') if x['day'].startswith(sd) and x['decision']=='SELECTED_PENDING']
 ds=sorted(ds,key=lambda x:(-x['PVR_score'],x['sid']))
 au={x['round_id']:x for x in read(base/'AUDIT.json') if x['day'].startswith(od) and x['type'] in ['RESERVED','BUDGET_REJECTED'] and x['kind']=='INIT'}
 props={}
 for d in ds:
  sid=d['sid'];a=au[d['round_id']];m=mm[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
  b=pd.read_parquet(source(sp,m['source_sha256'][sp])).loc[:od];sig=b.loc[sd];op=b.loc[od]
  assert all(sig[k]==op[k] for k in ['source_kind','source_path','segment_id','adjustment_factor'])
  for x in [sig,op]:assert x.observed_bar and x.price_eligible and not x.source_invalid and not x.synthetic_event_bar
  px=D(str(op.raw_open))*D('1.0005');fl=D(str(ev.at[d['event_id'],'i_floor']))/D(str(sig.adjustment_factor))
  ident=market_identity_on(rules,sid,od,proxies);v=version_on(rules['fee_versions'][ident['venue']],od,proxies)['schedule']
  qr=QuantityRule(**version_on(rules['quantity_versions'][sid],od,proxies)['rule']);fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components']));par=D(str(rules['security_metadata'][sid]['par_value']))
  props[sid]=(d,a,px,fl,qr,fs,par)
 target=min([d['sid'] for d in ds if au[d['round_id']]['shared_q']==0])
 for arm,order in [('ORIGINAL',[d['sid'] for d in ds]),('LEX_FIRST_REJECTED_MOVED_FIRST',[target]+[d['sid'] for d in ds if d['sid']!=target])]:
  book=ReserveBook(Snapshot(D('1200000'),D(0),D('1200000'),D('1200000'),(),(),(),'ORIGINAL_EMPTY_ACCOUNT_FIXED_OPEN'))
  selected=[]
  for rank,sid in enumerate(order,1):
   d,a,px,fl,qr,fs,par=props[sid];q=int(a['before_shared_q']);reasons=[]
   while q>0:
    bf=fee(q,px,fs,'buy',par);fr=max(D(0),D(q)*(px-fl*D('.9995'))+bf+fee(q,fl*D('.9995'),fs,'sell',par))
    reasons=[]
    if D(q)*px+bf>D('24000'):reasons.append('original_round_budget')
    if fr>D('3000'):reasons.append('original_round_fee_risk')
    ex=Exposure(sid,d['round_id'],d['sector'],'probe',q,px,fl,bf,'live');reasons+=book.reasons(ex)
    if not reasons:
     assert not book.reserve(ex);break
    q=qr.buy_floor(q-1)
   if arm=='ORIGINAL':assert q==a['shared_q'],(w,sid,q,a['shared_q'])
   if q>0:selected.append(sid)
   rows.append(dict(window=w,arm=arm,signal_day=sd,conditional_open_day=od,rank=rank,sid=sid,name=d['name'],original_PVR=d['PVR_score'],proposed_q=a['before_shared_q'],reserved_q=q,original_reserved_q=a['shared_q'],last_reasons=reasons,nominal_risk=D(q)*max(D(0),px-fl),new_fills=0))
  summ.append(dict(window=w,arm=arm,pending=len(ds),moved_sid=target,moved_name=props[target][0]['name'],selected_names=selected,reserved_names=len(selected),reserved_cash=book.reserved_cash,nominal_probe_risk=book.resources(pool='probe')[1],effective_nav=D('1200000')-book.unbooked_buy_fees,original_quantities_exact=arm=='ORIGINAL',outcome_use='NONE',not_a_proposed_alpha_rank=True))
pd.DataFrame(rows).to_csv(O/'TWO_EMPTY_START_FIXED_PERMUTATIONS.csv',index=False)
(O/'TWO_EMPTY_START_FIXED_PERMUTATION_SUMMARY.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2,default=str))
assert all(sha(p)==v for p,v in S.items())
(O/'PERMUTATION_QA.json').write_text(json.dumps(dict(source_hashes=S,source_unchanged=True,original_books_exact=2,permutations=2,target='lexicographically first originally rejected sid moved to front, fixed before labels',no_fills=True,no_accounts=True,no_PnL_labels=True),ensure_ascii=False,indent=2))
print(json.dumps(summ,ensure_ascii=False,indent=2,default=str))
