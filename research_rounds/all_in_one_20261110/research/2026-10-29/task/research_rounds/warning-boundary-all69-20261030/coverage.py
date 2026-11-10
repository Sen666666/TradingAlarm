"""All 69 identities; cached facts + warning-only RMS; no economic comparison."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import sys,json,math,hashlib,time,importlib.util
import numpy as np
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent;W=O.parent;D=W/'sell-failure-design-review-20261030';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');OLD=W/'old-side-exit-all69-20261030'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
assert not (O/'COVERAGE.csv').exists();sys.path.insert(0,str(D));from minimal_boundary import BoundaryState
src=OLD/'FROZEN_69_CYCLES.csv';cases=pd.read_csv(src);assert len(cases)==69 and cases.cycle_id.is_unique;cases.to_csv(O/'FROZEN_69_CYCLES.csv',index=False)
pfile=W/'act-loss-facts-20261030/actual-holding-close-paths.csv';efile=W/'down-event-transfer-exposure-20261030/all-holding-exposure-before-labels.csv';afile=W/'act-loss-facts-20261030/actual-cycles.csv'
paths=pd.read_csv(pfile,float_precision='round_trip',usecols=['day','shares','cycle_id','old_floor_causal','new_floor_causal','causal_close','ACT_on','I_active']);ex=pd.read_csv(efile,usecols=['date','cycle_id','event','old_signal']);actual=pd.read_csv(afile,float_precision='round_trip',usecols=['cycle_id','exit_request','initial_floor_causal']).set_index('cycle_id')
snap=Path(json.loads((R/'pvr-act-comparison-20261027/input.json').read_text())['snapshot']['path']);proof=json.loads((R/'ph1-cross-sector-20261028/event-validation.json').read_text());rec={x['symbol']:x for x in proof['records'] if x['sector']=='TECH'};assert proof['passed']
B5=R/'pv-strength-b5-20261025/code';spec=importlib.util.spec_from_file_location('all69_original_arithmetic',B5/'arithmetic.py');arith=importlib.util.module_from_spec(spec);spec.loader.exec_module(arith)
ident={str(p):sha(p) for p in [src,pfile,efile,afile,D/'minimal_boundary.py',D/'SYNTHETIC_RESULTS.json',B5/'arithmetic.py',B5/'evidence.py',O/'PROTOCOL.txt',Path(__file__)]};history={};vol={}
for s in sorted(cases.old.unique()):
 fp=snap/'facts'/f'{s}.parquet';sp=snap/'signals'/f'{s}.parquet'
 for p in [fp,sp]:assert sha(p)==rec[s]['inputs'][str(p)];ident[str(p)]=sha(p)
 history[s]=pd.read_parquet(fp,columns=['close','segment_id']);vol[s]=pd.read_parquet(sp,columns=['volume'])
save(O/'INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),before_new_economic_results=True,sha256=ident))
results=[];trace=[];sigma_checks=0
for z in cases.itertuples(index=False):
 cid=z.cycle_id;s=z.old;c=actual.loc[cid];g=paths[paths.cycle_id.eq(cid)].sort_values('day');eg=ex[ex.cycle_id.eq(cid)].set_index('date');first=None if pd.isna(z.date) else z.date;qq=eg[eg.old_signal];assert (None if qq.empty else qq.index.min())==first
 missing=list(eg.index[eg.event.isna()]);before=[d for d in missing if first and d<first];P=sigma=B=floor=None;sigma_status='no_known_warning'
 if first:
  f=history[s];day=pd.Timestamp(first)
  if day not in f.index:sigma_status='warning_price_unknown'
  else:
   P=float(f.loc[day,'close']);seg=f.loc[day,'segment_id'];b=f[f.segment_id.eq(seg)][['close']].join(vol[s],how='left');b=b[b.gt(0).all(axis=1)&np.isfinite(b).all(axis=1)];floor=float(g[g.day.eq(first)].iloc[0].old_floor_causal)
   if day not in b.index or b.index.get_loc(day)<64:sigma_status='sigma_original_warmup_unknown'
   else:
    j=b.index.get_loc(day);rr=[arith.log_ratio(float(b.close.iloc[k]),float(b.close.iloc[k-1])) for k in range(j-63,j)];sigma=max(math.sqrt(math.fsum(x*x for x in rr)/63),1e-8);B=P*math.exp(-math.sqrt(5)*sigma);sigma_status='original_RMS63_known';sigma_checks+=1
 st=BoundaryState(float(c.initial_floor_causal));trigger=handoff=None;unknown=[]
 for rr in g.itertuples(index=False):
  day=rr.day;er=eg.loc[day];native=pd.Timestamp(day) in history[s].index;price=float(rr.causal_close) if native else None
  if native:assert price==float(history[s].loc[pd.Timestamp(day),'close'])
  if st.e0_floor!=float(rr.old_floor_causal):unknown.append(day+':original_floor_state_mismatch');break
  end=(day==c.exit_request[:10]) or not bool(rr.ACT_on) or not bool(rr.I_active);known=pd.notna(er.event);event=int(er.event) if known else 0
  if event==-1 and not st.warning_seen and not bool(er.old_signal):event=0
  if event==-1 and not st.warning_seen:assert day==first
  nf=float(rr.new_floor_causal) if pd.notna(rr.new_floor_causal) else None;upd=nf if nf is not None and nf!=st.e0_floor and not end else None
  if upd is not None and (not known or event!=1):unknown.append(day+':floor_update_event_unknown');break
  x=st.step(close=price,event=event,sigma=sigma if day==first else None,updated_e0_floor=upd,original_exit=end);x.update(cycle_id=cid,day=day,event_known=known,native_close_known=native);trace.append(x)
  if st.handed_off and handoff is None:handoff=day
  if st.exit_locked:
   if st.exit_reason=='warning_boundary':trigger=day
   break
 mechanism='unknown_behavior' if unknown else 'unknown_scale' if first and sigma is None else 'delayed_boundary_request' if trigger else 'safe_floor_handoff' if handoff else 'no_known_warning' if not first else 'original_exit_without_boundary_hit'
 q=int(g[g.day.eq(first)].iloc[0].shares) if first else None
 results.append(dict(cycle_id=cid,symbol=s,name=z.name,first_known_warning=first,P=P,sigma=sigma,B=B,warning_old_floor=floor,warning_quantity=q,sigma_status=sigma_status,new_trigger=trigger,handoff=handoff,mechanism=mechanism,unknown_event_days=json.dumps(missing),unknown_before_first=json.dumps(before),behavior_unknown=json.dumps(unknown),original_entry=z.original_entry,original_exit=z.original_exit,original_exit_request=c.exit_request))
pd.DataFrame(results).to_csv(O/'COVERAGE.csv',index=False);pd.DataFrame(trace).to_csv(O/'COVERAGE_STATE_TRACE.csv',index=False)
small=pd.read_csv(D/'historical-behavior-v1/RESULTS.csv',float_precision='round_trip',usecols=['cycle_id','first_known_warning','P','sigma','B','warning_old_floor','new_trigger','handoff']).set_index('cycle_id');large=pd.DataFrame(results).set_index('cycle_id')
for cid,row in small.iterrows():
 for k in small.columns:
  a=row[k];b=large.loc[cid,k];assert (pd.isna(a) and pd.isna(b)) or a==b,(cid,k,a,b)
summary=dict(passed=True,cycles=69,stocks=len(history),known_warning=sum(x['first_known_warning'] is not None for x in results),mechanism=dict(Counter(x['mechanism'] for x in results)),warning_scale_known=sigma_checks,warning_scale_unknown=sum(x['first_known_warning'] is not None and x['sigma'] is None for x in results),unknown_event_rows=sum(len(json.loads(x['unknown_event_days'])) for x in results),cases_with_prior_unknown_event=sum(bool(json.loads(x['unknown_before_first'])) for x in results),small_13_case_behavior_exact=True,indicator_replays=0,only_warning_RMS_computed=True,new_economic_ledgers=0,seconds=time.monotonic()-T)
assert all(sha(p)==h for p,h in ident.items());save(O/'COVERAGE_SUMMARY.json',summary);save(O/'COVERAGE_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_new_economic_results=True,sha256={str(O/n):sha(O/n) for n in ['PROTOCOL.txt','FROZEN_69_CYCLES.csv','COVERAGE.csv','COVERAGE_STATE_TRACE.csv','COVERAGE_SUMMARY.json','INPUT_IDENTITY.json']}));print(json.dumps(summary,ensure_ascii=False))
