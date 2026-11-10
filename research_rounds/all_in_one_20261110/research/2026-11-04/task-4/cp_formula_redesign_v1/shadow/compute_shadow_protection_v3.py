"""Pure CP V3 downside-protection math over existing saved inputs; never imports any account/runner/model.
V2 fixed before this script: independent amount gate, peak line and local repair.
"""
from pathlib import Path
from decimal import Decimal as D
import math,json,csv,hashlib,time
import pandas as pd
O=Path(__file__).resolve().parent/'protection_v3';O.mkdir(exist_ok=True);ROOT=O.parents[2]
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
A0=math.sqrt(5);K0=math.sqrt(21);SMIN=math.log1p(.001);EPS=4*2**-53/(1-4*2**-53);SOURCES={}
CASES=[('000620.SZ','盈新','2022-01-04','2022-02-08',['2022-01-21','2022-01-27']),('002583.SZ','海能达','2024-09-23','2024-11-27',['2024-09-24','2024-10-18']),('300085.SZ','银之杰','2024-09-23','2024-11-27',['2024-09-24','2024-10-10'])]
def bind(p):
 p=Path(p);SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def ge(a,b):return a>=b or abs(a-b)<=EPS*max(abs(a),abs(b),1e-300)
def gt(a,b):return a>b and not abs(a-b)<=EPS*max(abs(a),abs(b),1e-300)
def finite(x):return x is not None and math.isfinite(float(x))
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,list):return [clean(v)for v in x]
 if isinstance(x,tuple):return [clean(v)for v in x]
 if isinstance(x,float)and not math.isfinite(x):return None
 return x

def prepare(inp,old,facts,cut):
 f=inp.loc[:cut].copy();q=old.loc[f.index].copy();v=facts.loc[f.index,['factor','raw_close']]
 assert f.index.equals(q.index)and f.index.equals(v.index)
 z21=pd.Series(index=f.index,dtype=float);downside21=pd.Series(index=f.index,dtype=float)
 for _,g in q.groupby(f.segment_id,sort=False):
  z21.loc[g.index]=g.r.abs().shift(1).rolling(21,min_periods=21).median().mul(1.4826).clip(lower=SMIN)
  downside21.loc[g.index]=g.r.clip(upper=0).pow(2).shift(1).rolling(21,min_periods=21).mean().pow(.5)
 records=[]
 for date in f.index:
  r=f.loc[date];a=q.loc[date];factor=float(v.loc[date,'factor']);raw=float(v.loc[date,'raw_close'])
  assert float(r.close)==float(facts.loc[date,'close'])and float(r.amount)>0
  records.append(dict(date=str(date.date()),close=float(r.close),raw_close=raw,factor=factor,segment=int(r.segment_id),valid=bool(r.e0_valid),down=bool(r.e0_down),amount=float(r.amount),r=float(a.r),z63=float(a.z),z21=float(z21.loc[date]),downside21=float(downside21.loc[date]),B=float(a.B),old_receipt=bool(a.receipt),old_candidate=float(a.candidate),old_scale=float(a.scale),old_credit=float(a.credit),old_displacement=float(a.displacement),old_m=float(a.m)))
 return records

def shadow(records,combined,sid):
 segment=None;proof=None;anchor=frontier=sigma=None;ta=tb=0.;H=M=None;protection_sigma0=None;trend='OFF';episode=None;advance=0;last_failed=None;out=[]
 for r in records:
  p=math.log(r['close']);C=r['close'];previous_H=H;previous_M=M;episode_before=episode;phase_before=proof;anchor_before=anchor;scale_before=sigma
  delta=0.;disp=V=threshold=proof_candidate=None;receipt=False;failure=False;initialized=False;reason=None;newhigh=False
  source_changed=r['segment']!=segment
  if source_changed:
   segment=r['segment'];proof=None;anchor=frontier=sigma=None;ta=tb=0.;H=M=None;protection_sigma0=None;trend='OFF';episode=None;advance=0;last_failed=None
   previous_H=previous_M=None;episode_before=None;reason='source_reset'
  ready=finite(r['z63'])and finite(r['B'])and r['B']>0 and (not combined or finite(r['z21']))
  zH=max(protection_sigma0,r['downside21'])if combined and ready and protection_sigma0 is not None else None
  if not ready or not r['valid']:
   proof=None;anchor=frontier=sigma=None;ta=tb=0.;H=M=None;protection_sigma0=None;trend='OFF';episode=None;advance=0;reason='unprepared'if not ready else 'I_domain_off'
  elif combined and H is not None and ge(H,C):
   failure=True;last_failed=episode;H=M=None;protection_sigma0=None;episode=None;advance=0;trend='REPAIR';proof='SEEK';anchor=frontier=p;sigma=r['z63'];ta=tb=0.;reason='old_market_line_broken'
  elif proof is None or r['down']:
   proof='SEEK';anchor=frontier=p;sigma=r['z63'];ta=tb=0.;reason='down_resets_proof_only'if r['down']else 'start'
   if H is None and trend!='REPAIR':trend='SEEK'
  elif proof=='SEEK'and gt(anchor,p):
   anchor=frontier=p;sigma=r['z63'];ta=tb=0.;reason='lower_anchor'
  else:
   delta=p-frontier if gt(p,frontier)else 0.
   if delta:
    frontier=p;ta=math.fsum((ta,r['amount']));tb=math.fsum((tb,r['B']))
   disp=frontier-anchor;V=ta/tb if tb>0 else None;threshold=A0*sigma
   receipt=bool(delta and ge(disp,threshold)and V is not None and ge(V,1.))
   if receipt:
    proof_candidate=C*math.exp(-K0*sigma)
    if combined:
     if H is None:
      protection_sigma0=sigma;zH=max(protection_sigma0,r['downside21']);H=C*math.exp(-K0*zH);M=C;trend='TREND';episode=sid+'|'+str(segment)+'|'+r['date'];advance=1;initialized=True
     else:advance+=1
    proof='UP';anchor=frontier=p;sigma=r['z63'];ta=tb=0.;reason='receipt'
  # Independent protection update must still run after a down-only proof reset.
  if combined and ready and r['valid']and not failure and H is not None and gt(C,M):
   newhigh=True;M=C;H=max(H,M*math.exp(-K0*zH))
  if receipt:
   assert delta>0 and disp is not None and threshold is not None and ge(disp,threshold)and V is not None and ge(V,1)
   assert not failure
  if combined and previous_H is not None and H is not None and episode==episode_before:
   assert ge(H,previous_H)
  if failure:assert not receipt and H is None and trend=='REPAIR'
  result=dict(r,mode='combined'if combined else 'amount_only',ready=ready,source_changed=source_changed,proof_phase_before=phase_before,proof_phase_after=proof,proof_anchor_before=anchor_before,proof_scale_before=scale_before,receipt=receipt,reason=reason,delta_frontier=delta,displacement_at_decision=disp,amount_ratio_at_decision=V,threshold_at_decision=threshold,receipt_oldscale_candidate=proof_candidate,receipt_oldscale_candidate_raw=proof_candidate/r['factor']if proof_candidate is not None else None,proof_anchor_after=anchor,proof_frontier_after=frontier,proof_scale_after=sigma,next_amount_sum=ta,next_baseline_sum=tb,trend_state=trend,trend_episode_before=episode_before,parent_trend_episode=episode,advance_index=advance,previous_failed_trend_episode=last_failed,market_line_before=previous_H,market_line_before_raw=previous_H/r['factor']if previous_H is not None else None,market_line_after=H,market_line_after_raw=H/r['factor']if H is not None else None,trend_peak_before=previous_M,trend_peak_after=M,protection_scale=zH,protection_initial_frozen_scale=protection_sigma0,market_line_failed=failure,new_trend_initialized=initialized,protection_new_close_high=newhigh)
  out.append(clean(result))
 return out

def write_csv(name,rows):
 if not rows:return
 cols=list(dict.fromkeys(k for r in rows for k in r))
 with (O/name).open('w',newline='')as f:w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)

def main():
 begun=time.monotonic();bind(__file__);bind(O.parents[1]/'FROZEN_PROTECTION_V3.txt');bind(O.parents[1]/'FROZEN_FORMULA_V2.txt');m={r['symbol']:r for r in read(MANIFEST)};summary=[];prefix=[];all_case_rows=[]
 for sid,name,start,end,cuts in CASES:
  rec=m[sid];inp=pd.read_parquet(bind(rec['refs']['CP1_input']));old=pd.read_parquet(bind(rec['refs']['CP1']));facts=pd.read_parquet(bind(rec['refs']['facts']))
  for mode in ['combined']:
   records=prepare(inp,old,facts,end);full=shadow(records,mode=='combined',sid);window=[r for r in full if start<=r['date']<=end]
   write_csv(sid+'_'+mode+'.csv',window);save(sid+'_'+mode+'.json',window);all_case_rows.extend(window)
   for cut in cuts:
    small=shadow(prepare(inp,old,facts,cut),mode=='combined',sid);expected=[r for r in full if r['date']<=cut];assert small==expected,(sid,mode,cut,'prefix mismatch')
    prefix.append(dict(sid=sid,mode=mode,cut=cut,compared_observations=len(small),all_fields_exact=True))
   original_dates=[r['date']for r in window if r['old_receipt']];new_dates=[r['date']for r in window if r['receipt']]
   summary.append(dict(sid=sid,name=name,mode=mode,start=start,end=end,source_warm_first=str(inp.index[0].date()),warm_observations_through_window_end=len(full),display_observations=len(window),original_receipts=len(original_dates),new_receipts=len(new_dates),original_receipt_dates=original_dates,new_receipt_dates=new_dates,original_dates_without_new_receipt=sorted(set(original_dates)-set(new_dates)),new_dates_without_original_receipt=sorted(set(new_dates)-set(original_dates)),market_failure_dates=[r['date']for r in window if r['market_line_failed']],domain_off_dates=[r['date']for r in window if r['reason']=='I_domain_off']))
 write_csv('ALL_THREE_STOCKS_FORMULA_STATES.csv',all_case_rows);save('SHADOW_SUMMARY.json',summary);save('PREFIX_CHECKS.json',prefix);save('SOURCE_SHA256.json',SOURCES)
 save('SCOPE.json',dict(formula='FROZEN_PROTECTION_V3',full_case_windows=len(CASES),modes=['combined'],original_baseline='saved CP cache only, not original model rerun',new_CP_formula_shadow_only=True,new_accounts=0,new_orders=0,new_strategy_backtests=0,new_return_estimates=0,known_native_models_imported=False,prefix_checks=len(prefix),future_source_vintage_certified=False,runtime_seconds=time.monotonic()-begun))
 print(json.dumps(summary,ensure_ascii=False));print('PREFIX',len(prefix),'exact; seconds',time.monotonic()-begun)
if __name__=='__main__':main()
