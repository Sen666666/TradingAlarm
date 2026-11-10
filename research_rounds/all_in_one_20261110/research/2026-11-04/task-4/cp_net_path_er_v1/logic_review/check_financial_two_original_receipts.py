"""Two original receipt diagnostic points, four anchor paths; no new G state/account."""
from pathlib import Path
import json,math,hashlib
import pandas as pd
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'cp_net_path_er_v1/financial_924'
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CASES=[('601336.SH','2024-09-23'),('603093.SH','2024-11-07')];h={};checks=[];points=[]
def bind(p):
 p=Path(p);h[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def check(sid,date,mode,k,a,b):
 err=abs(float(a)-float(b))if a is not None and b is not None else None;ok=(a is b)if err is None else err<=1e-12*max(1.,abs(float(b)))
 checks.append(dict(sid=sid,date=date,anchor_mode=mode,field=k,saved=a,independent=b,absolute_error=err,passed=ok));assert ok,(sid,date,mode,k,a,b)
m={x['symbol']:x for x in json.loads(bind(MANIFEST).read_text())}
for sid,date in CASES:
 f=pd.read_parquet(bind(m[sid]['refs']['CP1_input']));cp=pd.read_parquet(bind(m[sid]['refs']['CP1']));facts=pd.read_parquet(bind(m[sid]['refs']['facts']))
 for mode,suffix in [('local_original','ORIGINAL_ANCHOR_ER_DAILY'),('last_original_receipt','LAST_ORIGINAL_RECEIPT_ANCHOR_ER_DAILY')]:
  rows=json.loads(bind(S/(sid+'_'+suffix+'.json')).read_text());x=next(z for z in rows if z['date']==date);ad=x['original_anchor_day']if mode=='local_original'else x['last_original_receipt_anchor_day'];part=f.loc[ad:date];assert part.segment_id.nunique()==1 and part.e0_valid.all();p=[math.log(float(c))for c in part.close];r=[p[k]-p[k-1]for k in range(1,len(p))];A=p[-1]-p[0];L=math.fsum(abs(z)for z in r);ER=A/L if L>0 else None;DD=max(p)-p[-1]
  check(sid,date,mode,'A',x['A_net_log_progress'],A);check(sid,date,mode,'L',x['L_all_abs_log_returns'],L);check(sid,date,mode,'ER',x['ER'],ER);check(sid,date,mode,'DD',x['DD_log_known_high_to_current'],DD);check(sid,date,mode,'observations',x['observations_since_anchor'],len(r));check(sid,date,mode,'anchor_close',x['anchor_CLOSE'],float(part.iloc[0].close));check(sid,date,mode,'current_close',x['continuous_close'],float(f.loc[date,'close']));check(sid,date,mode,'raw_close',x['raw_close'],float(facts.loc[date,'raw_close']));check(sid,date,mode,'original_receipt',x['old_CP_receipt'],bool(cp.loc[date,'receipt']));check(sid,date,mode,'original_credit',x['original_CP_credit'],float(cp.loc[date,'credit']));check(sid,date,mode,'original_sigma',x['original_CP_frozen_scale'],float(cp.loc[date,'scale']));check(sid,date,mode,'G_scalar_only',x['G_arithmetic_diagnostic_not_new_signal'],A*abs(ER)if ER is not None else None)
  if mode=='last_original_receipt':check(sid,date,mode,'next_sigma_of_old_anchor',x['last_original_receipt_next_frozen_scale'],float(cp.loc[ad,'next_scale']))
  points.append(dict(sid=sid,date=date,mode=mode,anchor_day=ad,A=A,L=L,ER=ER,DD=DD,observations=len(r)))
# Ranking is a saved-output diagnostic selection, not a new signal or universe.
positive=[]
for q in S.glob('*_LAST_ORIGINAL_RECEIPT_ANCHOR_ER_DAILY.json'):
 for x in json.loads(q.read_text()):
  if x['old_CP_receipt']and x['ER']is not None and x['ER']>0:positive.append((x['ER'],x['sid'],x['date']))
assert [(s,d)for er,s,d in sorted(positive)[:2]]==CASES
out=dict(scope='Two lowest-positive-ER original receipt rows under LAST_ORIGINAL_RECEIPT diagnostic,also checked corresponding local-original anchors;not new G acceptance',checks=len(checks),passed=all(x['passed']for x in checks),max_absolute_error=max(x['absolute_error']or 0 for x in checks),points=points,source_sha256=h,new_G_states=0,new_accounts=0,new_backtests=0,checks_detail=checks)
(O/'FINITE_FINANCIAL_TWO_RECEIPTS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print({k:out[k]for k in ['checks','passed','max_absolute_error']});print(points)
