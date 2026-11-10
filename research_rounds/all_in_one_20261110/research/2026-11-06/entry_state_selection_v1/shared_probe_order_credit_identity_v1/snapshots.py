"""Reconstruct fixed original pre-buy snapshots from immutable exact journals only."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;B=R/'m3_ab_shared_probe_v1'
S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):S[str(p)]=sha(p);return json.loads(Path(p).read_text())
u=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
mm={x['symbol']:x for x in read(u/'STOCK_MANIFEST.json')}
ds=pd.read_csv(O/'FIXED_DAILY_FUNNEL.csv',dtype={'window':str})
base={'2022':B/'known_halt_contract_v1/cohort_2022_recovery_v2','2024_924':B/'indexed_execution_v1/cohort_2024_924'}
cache={}
def data(sid):
 if sid not in cache:
  m=mm[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));f=m['refs']['facts']
  for x,h in [(p,m['source_sha256'][p]),(f,m['output_sha256'][f])]:S[str(x)]=sha(x);assert S[str(x)]==h
  cache[sid]=(pd.read_parquet(p),pd.read_parquet(f))
 return cache[sid]
summ=[];details=[]
for w,g in ds.groupby('window'):
 bb=base[w];j=read(bb/'EXACT_TRADE_JOURNAL.json');au=read(bb/'AUDIT.json');arc=read(bb/'ARCHIVES.json');ledger={x['day'][:10]:x for x in read(bb/'DAY_LEDGER.json')}
 for d in g.to_dict('records'):
  day=d['open_day'];prev=d['signal_day'];q=defaultdict(lambda:dict(core=0,add=0))
  for a in j:
   ad=a['day'][:10]
   if ad>day or (ad==day and a['side'].startswith('buy')):continue
   z=q[a['round_id']]
   if a['side']=='buy_core':z['core']+=int(a['q'])
   elif a['side']=='buy_add':z['add']+=int(a['q'])
   elif a['side']=='sell_add':z['add']-=int(a['q'])
   else:assert sum(z.values())==int(a['q']);q[a['round_id']]=dict(core=0,add=0)
  promoted={a['round_id'] for a in au if a['type']=='PROMOTED' and a['day'][:10]<=day}
  gross=D(0);risk=D(0);nprobe=0
  for rid,parts in q.items():
   qty=sum(parts.values())
   if not qty:continue
   st=arc[rid];sid=st['sid'];raw,f=data(sid);rr=raw.loc[day];op=D(str(rr.raw_open));floor=D(str(f.loc[prev,'i_floor']))/D(str(rr.adjustment_factor))
   gross+=D(qty)*op
   if rid not in promoted:
    assert parts['add']==0
    r=D(qty)*max(D(0),op-floor);risk+=r;nprobe+=1
    details.append(dict(window=w,open_day=day,sid=sid,name=st['name'],round_id=rid,q=qty,open=op,original_I_floor=floor,nominal_risk=r))
  batch=next(a for a in au if a['type']=='ALL_RESERVATIONS_COMPLETE' and a['day'][:10]==day)
  cash=D(batch['cash_before_fills']);recv=D(ledger[day]['OPEN']['receivable']);nav=cash+recv+gross
  newcash=D(0);newmark=D(0)
  for a in j:
   if a['day'][:10]!=day or not a['side'].startswith('buy'):continue
   sid=arc[a['round_id']]['sid'];raw,_=data(sid);qty=D(a['q']);newcash+=qty*D(a['exact_price'])+D(a['exact_whole_order_fee']);newmark+=qty*D(str(raw.loc[day,'raw_open']))
  residual=nav-newcash+newmark-D(ledger[day]['OPEN']['NAV']);assert residual==0,(w,day,residual)
  summ.append(dict(d,prebuy_NAV=nav,prebuy_cash=cash,probe_names_after_original_promotions=nprobe,probe_nominal_risk=risk,probe_cap_before_new_fees=nav*D('.005'),probe_headroom_before_new_fees=nav*D('.005')-risk,original_NAV_reconciliation_residual=residual))
pd.DataFrame(summ).to_csv(O/'FIXED_PREBUY_RESOURCE_SNAPSHOTS.csv',index=False)
pd.DataFrame(details).to_csv(O/'FIXED_PREBUY_PROBE_HOLDINGS.csv',index=False)
assert all(sha(p)==h for p,h in S.items())
(O/'SNAPSHOT_QA.json').write_text(json.dumps(dict(exact_NAV_reconciliations=len(summ),source_sha256=S,source_unchanged=True,no_new_economics=True),ensure_ascii=False,indent=2))
print(pd.DataFrame(summ)[['window','signal_day','open_day','pending','original_fills','probe_names_after_original_promotions','probe_nominal_risk','probe_headroom_before_new_fees']].to_string(index=False))
