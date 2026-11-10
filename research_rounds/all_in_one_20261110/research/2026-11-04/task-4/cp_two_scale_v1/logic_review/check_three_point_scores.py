"""Three fixed two-scale point values from raw saved source;no new permissionFSM."""
from pathlib import Path
from statistics import median
import math,json,hashlib
import pandas as pd
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;P=R/'cp_two_scale_v1/POINTWISE_TWO_SCALE_SCORES.json'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');CASES=[('000620.SZ','2022-01-20'),('000620.SZ','2022-01-24'),('002583.SZ','2024-09-30')];h={};checks=[]
def bind(p):
 p=Path(p);h[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def ck(s,d,k,a,b):
 if a is None or b is None:err=None;ok=a is b
 else:err=abs(float(a)-float(b));ok=err<=1e-12*max(1.,abs(float(b)))
 checks.append(dict(sid=s,date=d,field=k,saved=a,independent=b,absolute_error=err,passed=ok));assert ok,(s,d,k,a,b)
rows=json.loads(bind(P).read_text());m={r['symbol']:r for r in json.loads(bind(M).read_text())};loaded={}
for sid,date in CASES:
 if sid not in loaded:
  z=m[sid];f=pd.read_parquet(bind(z['refs']['CP1_input']));cp=pd.read_parquet(bind(z['refs']['CP1']));ep=next(p for p in z['source_sha256']if p.endswith('/events.parquet'));ev=pd.read_parquet(bind(ep));loaded[sid]=(f,cp,ev)
 f,cp,ev=loaded[sid];x=next(q for q in rows if q['sid']==sid and q['date']==date);seg=f.loc[date,'segment_id'];known=ev.loc[:date];known=known[known.segment_id.eq(seg)]
 for axis,sign,label in [('s',1,'short'),('l',-1,'long')]:
  events=known[known.event.eq(sign)];e=events.iloc[-1];cd=str(events.index[-1].date());bd=str(pd.Timestamp(e.confirmed_pivot_date).date());assert bd<=cd<=date
  assert bd==x[label+'_pivot_day']and cd==x[label+'_confirm_day'];part=f.loc[bd:date];assert part.segment_id.eq(seg).all();prices=[math.log(float(c))for c in part.close];a=prices[-1]-prices[0];L=math.fsum(abs(prices[i]-prices[i-1])for i in range(1,len(prices)));er=a/L if L>0 else None;dd=max(prices)-prices[-1];sigma=float(cp.loc[cd,'z']);G=a*abs(er)if er is not None else None;k=math.sqrt(5)*sigma;Q=G/k if G is not None else None
  ck(sid,date,label+'_pivot_source_price',float(part.iloc[0].close),float(e.confirmed_pivot_price));ck(sid,date,'A_'+axis,x['A_'+axis],a);ck(sid,date,'L_'+axis,x['L_'+axis],L);ck(sid,date,'ER_'+axis,x['ER_'+axis],er);ck(sid,date,'DD_'+axis,x['DD_'+axis],dd);ck(sid,date,'sigma_'+axis+'_is_z_on_confirm',x['sigma_'+axis],sigma);ck(sid,date,'G_'+axis,x['G_'+axis],G);ck(sid,date,'threshold_'+axis,x['threshold_'+axis],k);ck(sid,date,'Q_'+axis,x['Q_'+axis],Q)
  prefix=f.loc[:cd];prefix=prefix[prefix.segment_id.eq(seg)];c=[math.log(float(y))for y in prefix.close];rr=[c[i]-c[i-1]for i in range(1,len(c))];lag=rr[-64:-1];assert len(lag)==63;ind_sigma=max(math.log1p(.001),1e-8,1.4826*median(abs(y)for y in lag));ck(sid,date,'sigma_'+axis+'_lag63_math',sigma,ind_sigma)
out=dict(scope='Three fixed score points,two axes each,direct original confirmed-event and price path substitutions;no active-barrier,permissions or consumptionFSM',point_dates=CASES,checks=len(checks),passed=all(x['passed']for x in checks),max_absolute_error=max(x['absolute_error']or 0 for x in checks),source_sha256=h,new_permission_states=0,new_accounts=0,new_backtests=0,checks_detail=checks)
(O/'FINITE_THREE_POINT_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print({k:out[k]for k in ['checks','passed','max_absolute_error']})
