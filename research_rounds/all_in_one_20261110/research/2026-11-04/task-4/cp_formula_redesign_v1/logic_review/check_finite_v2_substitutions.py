"""Finite saved-row arithmetic review only; no state-machine/account/model execution."""
from pathlib import Path
from statistics import median
import json,math,hashlib
import pandas as pd
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'cp_formula_redesign_v1/shadow'
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CASES={'000620.SZ':['2022-01-21','2022-01-24'],'002583.SZ':['2024-09-24','2024-09-25','2024-10-18'],'300085.SZ':['2024-10-10','2024-10-14']}
checks=[];bound={};facts_bound=[]
def bind(p):
 p=Path(p);bound[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def record(sid,day,field,got,want):
 if got is None or want is None:passed=got is want;err=None
 else:err=abs(float(got)-float(want));passed=err<=1e-10*max(1.,abs(float(want)))
 checks.append(dict(sid=sid,day=day,field=field,saved=got,independent=want,absolute_error=err,passed=passed))
 assert passed,(sid,day,field,got,want)
m={x['symbol']:x for x in json.loads(bind(MANIFEST).read_text())}
for sid,dates in CASES.items():
 f=pd.read_parquet(bind(m[sid]['refs']['CP1_input']));q=pd.read_parquet(bind(m[sid]['refs']['CP1']));facts=pd.read_parquet(bind(m[sid]['refs']['facts']))
 rows=json.loads(bind(S/(sid+'_combined.json')).read_text());bydate={x['date']:x for x in rows}
 for day in dates:
  x=bydate[day];i=f.index.get_loc(pd.Timestamp(day));seg=f.iloc[i].segment_id;g=f.iloc[:i+1];g=g[g.segment_id.eq(seg)];c=[float(v)for v in g.close];rr=[math.log(c[k])-math.log(c[k-1])for k in range(1,len(c))]
  z63=max(math.log1p(.001),1e-8,1.4826*median(abs(v)for v in rr[-64:-1]));z21=max(math.log1p(.001),1.4826*median(abs(v)for v in rr[-22:-1]));B=median(float(v)for v in g.amount.iloc[-22:-1]);r=rr[-1]
  record(sid,day,'source_close',x['close'],float(f.iloc[i].close));record(sid,day,'cached_r',float(q.loc[day,'r']),r);record(sid,day,'z63',x['z63'],z63);record(sid,day,'z21',x['z21'],z21);record(sid,day,'B',x['B'],B);record(sid,day,'amount',x['amount'],float(f.iloc[i].amount));record(sid,day,'factor',x['factor'],float(facts.loc[day,'factor']));record(sid,day,'raw_close',x['raw_close'],float(facts.loc[day,'raw_close']))
  prev=rows[rows.index(x)-1];H=x['market_line_before'];fail=H is not None and x['close']<=H
  record(sid,day,'failure_oldline',x['market_line_failed'],fail)
  if x['delta_frontier']>0:
   ta=prev['next_amount_sum']+x['amount'];tb=prev['next_baseline_sum']+x['B'];V=ta/tb;D=math.log(x['close'])-x['proof_anchor_before'];T=math.sqrt(5)*x['proof_scale_before']
   record(sid,day,'V_from_prior_sums',x['amount_ratio_at_decision'],V);record(sid,day,'D_from_anchor',x['displacement_at_decision'],D);record(sid,day,'threshold',x['threshold_at_decision'],T);record(sid,day,'receipt_two_gates',x['receipt'],D>=T and V>=1)
   if x['receipt']:
    record(sid,day,'oldscale_candidate',x['receipt_oldscale_candidate'],x['close']*math.exp(-math.sqrt(21)*x['proof_scale_before']));record(sid,day,'reset_amount_sum',x['next_amount_sum'],0);record(sid,day,'reset_baseline_sum',x['next_baseline_sum'],0)
  zh=max(z63,z21)
  if fail:expected=None;record(sid,day,'failure_no_receipt',x['receipt'],False);record(sid,day,'failure_repair_anchor',x['proof_anchor_after'],math.log(x['close']))
  elif x['new_trend_initialized']:expected=x['close']*math.exp(-math.sqrt(21)*zh)
  elif H is not None and x['close']>x['trend_peak_before']:expected=max(H,x['close']*math.exp(-math.sqrt(21)*zh))
  else:expected=H
  record(sid,day,'market_line_after',x['market_line_after'],expected)
  if expected is not None:record(sid,day,'market_line_raw',x['market_line_after_raw'],expected/x['factor'])
summary=dict(scope='Seven preselected finite CP V2 rows, direct raw saved input/window arithmetic, no state-machine replay',observations=sum(map(len,CASES.values())),checks=len(checks),passed=all(x['passed']for x in checks),maximum_absolute_error=max(x['absolute_error']or 0 for x in checks),new_accounts=0,new_backtests=0,full_formula_or_indicator_runs=0,source_sha256=bound,checks_detail=checks)
(O/'FINITE_V2_SUBSTITUTIONS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print({k:summary[k]for k in ['observations','checks','passed','maximum_absolute_error']})
