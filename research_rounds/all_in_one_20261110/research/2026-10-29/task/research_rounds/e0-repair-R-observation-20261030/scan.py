"""Frozen 407 cached E0 periods; market observations only, never computes indicators."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
from collections import Counter
import csv,json,hashlib,time,math
import numpy as np,pandas as pd
T=time.monotonic();O=Path(__file__).resolve().parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');PH=R/'ph1-cross-sector-20261028';PRIOR=O.parent/'down-warning-six-mechanisms-20261030';END=pd.Timestamp('2026-10-27')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def export(n,rr):pd.DataFrame(rr).to_csv(O/n,index=False)
def ratio(C,L,H):
 C,L,H=map(lambda z:D(str(z)),[C,L,H]);assert H>L and C>L,(H,L,C);v=(C-L)/(H-L);x=math.log1p(float((C-L)/L));d=math.log1p(float((H-L)/L));other=math.expm1(x)/math.expm1(d);assert math.isclose(float(v),other,rel_tol=1e-10,abs_tol=1e-12);return C,L,H,v,D(1)-L/H,x
pool=list(csv.DictReader((R/'tech-compound-design-20261026/proposed-pool.csv').open()));assert len(pool)==len({x['symbol'] for x in pool})==407
snap=Path(read(R/'pvr-act-comparison-20261027/input.json')['snapshot']['path']);proof=read(PH/'event-validation.json');assert proof['passed'];records={x['symbol']:x for x in proof['records'] if x['sector']=='TECH'};assert set(records)=={x['symbol'] for x in pool}
sourcefiles=[O/'PROTOCOL.txt',Path(__file__),R/'tech-compound-design-20261026/proposed-pool.csv',R/'pvr-act-comparison-20261027/input.json',PH/'event-validation.json',PRIOR/'T0-fixed-facts.json',PRIOR/'T1-fixed-facts.json',PRIOR/'observation-endings-not-T0-features.json'];identity={str(p):sha(p) for p in sourcefiles};frames={};loaded=[]
for meta in pool:
 s=meta['symbol'];fp=snap/'facts'/f'{s}.parquet';ep=PH/'events/TECH'/f'{s}.parquet';rec=records[s];assert sha(fp)==rec['inputs'][str(fp)] and sha(ep)==rec['output_sha256'],s;identity[str(fp)]=sha(fp);identity[str(ep)]=sha(ep);f=pd.read_parquet(fp);ev=pd.read_parquet(ep);assert f.index.equals(ev.index);np.testing.assert_array_equal(f.close.to_numpy(float),ev.close.to_numpy(float));np.testing.assert_array_equal(f.segment_id.to_numpy(),ev.segment_id.to_numpy());frames[s]=(meta,f.loc[:END].copy(),ev.loc[:END].copy())
 loaded.append(dict(symbol=s,rows=len(f),first=str(f.index[0].date()),last=str(min(f.index[-1],END).date()),sigma_a_available=False))
save('INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),pool=407,history='complete cached per-stock source history through 2026-10-27',before_features_and_forward_labels=True,sha256=identity))
# Fixed old ACT cases only verify H/L/C/event semantics; never force later warnings into first-per-E0 mother.
v0=read(PRIOR/'T0-fixed-facts.json');v1={x['cycle_id']:x for x in read(PRIOR/'T1-fixed-facts.json')};ends={x['cycle_id']:x for x in read(PRIOR/'observation-endings-not-T0-features.json')};fixture=[]
for old in v0:
 s=old['symbol'];_,f,ev=frames[s];t0=pd.Timestamp(old['T0']);assert int(ev.loc[t0,'event'])==-1 and D(str(ev.loc[t0,'pivot']))==D(old['T0_peak_causal']);past=v1[old['cycle_id']];cand=ev[(ev.index>t0)&(ev.index<=pd.Timestamp(ends[old['cycle_id']]['T2']))&(ev.event==1)];observed=str(cand.index[0].date()) if len(cand) else None;assert observed==past['T1'];rr=None
 if observed:
  t1=pd.Timestamp(observed);C,L,H,v,dep,x=ratio(f.loc[t1,'close'],ev.loc[t1,'pivot'],ev.loc[t0,'pivot']);assert L==D(past['T1_confirmed_low']) and C==D(past['T1_close']) and v==D(past['T1_repaired_fraction_of_peak_low_decline']);rr=str(v)
 fixture.append(dict(cycle_id=old['cycle_id'],T0=old['T0'],T1=observed,HLC_exact=True,R_exact=True if observed else None,R=rr,numeric_k_check='stopped_sigma_a_not_in_cached_events',symbolic_bound='event implies x>=k, hence R>=expm1(k)/expm1(d)>0'))
save('SIX_CASE_VERIFICATION.json',dict(passed=True,actual_cycles=7,T1_R_exact=4,fixtures=fixture,sigma_a_missing_not_recomputed=True));print(json.dumps(dict(stage='six_cases_verified',seconds=time.monotonic()-T)),flush=True)
features=[];epochs=[];locators={};left_unknown=0
def finish(meta,f,ev,lo,hi,t0,t1,end_i,end_kind,left):
 global left_unknown
 s=meta['symbol'];sid=str(f.iloc[lo].segment_id);start=str(f.index[lo].date());key=f'{s}|{sid}|{start}';known_start=not left;left_unknown+=int(left);ep=dict(epoch_id=key,symbol=s,source_segment=sid,start=start,last_active=str(f.index[hi].date()),observed_end=str(f.index[end_i].date()),end_kind=end_kind,start_observed_0_to_1=known_start,T0_present=t0 is not None);epochs.append(ep)
 if t0 is None:return
 row=ep|dict(name=meta['name'],T0=str(f.index[t0].date()),H_pivot_date=str(ev.iloc[t0].pivot_date)[:10],H_known_at=str(f.index[t0].date()),H=str(ev.iloc[t0].pivot),T1=str(f.index[t1].date()) if t1 is not None else None,L_pivot_date=None,L_known_at=None,C_known_at=None,L=None,C=None,R=None,depth=None,wait_valid_price_observations=None,up_log_amplitude_x=None,sigma_L=None,activity_a=None,positive_event_confirmation_magnitude=None)
 if t1 is not None:
  C,L,H,v,dep,x=ratio(f.iloc[t1].close,ev.iloc[t1].pivot,ev.iloc[t0].pivot);row.update(L_pivot_date=str(ev.iloc[t1].pivot_date)[:10],L_known_at=str(f.index[t1].date()),C_known_at=str(f.index[t1].date()),H=str(H),L=str(L),C=str(C),R=str(v),depth=str(dep),wait_valid_price_observations=t1-t0,up_log_amplitude_x=x,natural_group='T1_C_below_H' if C<H else 'T1_C_at_or_above_H')
 else:row['natural_group']='no_repair_before_E0_end' if end_kind=='E0_off' else 'no_repair_right_censored'
 if left:row['natural_group']='unknown_true_E0_start'
 features.append(row);locators[key]=(s,t1,end_i,end_kind)
for j,(s,(meta,f,ev)) in enumerate(frames.items()):
 start=None;t0=t1=None;segment=None;known_before=False;last_i=None
 for i in range(len(f)):
  seg=f.iloc[i].segment_id
  if segment is not None and seg!=segment:
   if start is not None:finish(meta,f,ev,start,last_i,t0,t1,last_i,'source_boundary_censored',left)
   start=None;t0=t1=None;known_before=False
  segment=seg;active=bool(pd.notna(f.iloc[i].e0_target) and f.iloc[i].e0_target)
  if start is not None and not active:finish(meta,f,ev,start,i-1,t0,t1,i,'E0_off',left);start=None;t0=t1=None
  if active and start is None:start=i;t0=t1=None;left=not known_before
  if not active:known_before=True
  if active:
   event=int(ev.iloc[i].event)
   if t0 is None and event==-1:t0=i
   elif t0 is not None and t1 is None and i>t0 and event==1:t1=i
  last_i=i
 if start is not None:finish(meta,f,ev,start,last_i,t0,t1,last_i,'last_cached_price_censored',left)
 if (j+1)%80==0:print(json.dumps(dict(stage='cached_period_scan',stocks=j+1,T0_mother=len(features),seconds=time.monotonic()-T)),flush=True)
 if time.monotonic()-T>300:raise TimeoutError('300s scan budget; no extra indicator work allowed')
export('features-before-forward-labels.csv',features);export('all-E0-period-identities.csv',epochs)
freeze={str(O/n):sha(O/n) for n in ['PROTOCOL.txt','features-before-forward-labels.csv','all-E0-period-identities.csv','SIX_CASE_VERIFICATION.json']};save('FEATURE_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_forward_labels_computed=True,fields_fixed_before_outcomes=True,sha256=freeze));print(json.dumps(dict(stage='features_frozen',T0_mother=len(features),epochs=len(epochs),seconds=time.monotonic()-T)),flush=True)
# Attach only strictly post-T1 close observations after the feature file has been frozen.
labels=[]
for row in features:
 s,t1,end_i,kind=locators[row['epoch_id']];f=frames[s][1];label=dict(epoch_id=row['epoch_id'],label_status='no_T1_label_undefined' if t1 is None else 'ended_E0' if kind=='E0_off' else 'right_censored',post_observations=None,post_end_price_change=None,post_MFE=None,post_MAE=None,label_end_causal_close=None)
 if t1 is not None:
  seq=f.close.iloc[t1+1:end_i+1];label['post_observations']=len(seq)
  if len(seq):
   C=D(row['C']);y=D(str(seq.iloc[-1]))/C-1;high=D(str(seq.max()))/C-1;low=D(str(seq.min()))/C-1;label.update(post_end_price_change=str(y),post_MFE=str(max(D(0),high)),post_MAE=str(min(D(0),low)),label_end_causal_close=str(seq.iloc[-1]))
  else:label['label_status']='right_censored_no_post_observation'
 labels.append(label)
export('forward-market-labels.csv',labels);joined=[a|b for a,b in zip(features,labels)];assert all(a['epoch_id']==b['epoch_id'] for a,b in zip(features,labels));export('observation-ledger.csv',joined)
expected={x['T0']+'|'+x['symbol'] for x in features};fx=[]
for x in fixture:fx.append(x|dict(in_first_per_E0_mother=(x['T0']+'|'+x['cycle_id'].split('|')[0]) in expected))
save('SIX_CASE_MEMBERSHIP.json',fx)
assert len(features)==len(set(x['epoch_id'] for x in features));assert all(sha(p)==h for p,h in identity.items());assert all(sha(p)==h for p,h in freeze.items());summary=dict(stocks=407,source_rows=sum(x['rows'] for x in loaded),date_first=min(x['first'] for x in loaded),date_last=max(x['last'] for x in loaded),E0_periods=len(epochs),without_T0=sum(not x['T0_present'] for x in epochs),T0_mother=len(features),left_start_unknown=left_unknown,natural_groups=dict(Counter(x['natural_group'] for x in features)),end_kinds=dict(Counter(x['end_kind'] for x in features)),label_status=dict(Counter(x['label_status'] for x in labels)),sigma_a_available=0,field_identity_unchanged=True,source_hashes_unchanged=True,indicators_recomputed=0,trade_paths=0,seconds=time.monotonic()-T);save('SCAN_VERIFICATION.json',summary);print(json.dumps(dict(stage='complete',summary=summary),ensure_ascii=False),flush=True)
