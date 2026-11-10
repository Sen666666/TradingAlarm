
"""Fixed-case causal audit of CP expansion/repair credit. No account/model replay."""
from pathlib import Path
import json,hashlib,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
P=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
CASES=[('600056.SH','2022-03-03'),('600056.SH','2022-03-30'),('002385.SZ','2022-03-04'),('300182.SZ','2022-01-04'),('688582.SH','2024-07-29'),('600606.SH','2022-03-22'),('601607.SH','2022-03-24'),('000506.SZ','2024-10-15')]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
freeze=dict(name='CP expansion loss and outside-band credit',formula='M=rolling21 mean(C); U=M+2*rolling21 std(C,ddof=0); use U.shift(1) within source segment. Original fresh delta credit=m*delta; outside credit increment=m*max(0,log(C)-max(log(C)-delta,log(U_prev))). q=outside_credit/original_credit on receipt before market receipt consumption.',structural_states='BASE,EXPAND,REPAIR; source segment resets BASE. In EXPAND first check C<S_prev -> REPAIR. Current original fresh receipt & C>U_prev immediately is new EXPAND and retains original PVR; new S=F if rearmed, else max(S,F). EXPAND current fresh inside-band updates max(S,F). No I/CP/midline reset of structural state.',ranking='Only original legal empty MOBILE. REPAIR current receipt that does not newly expand: PVR/(2-q); otherwise original PVR. At most half penalty, no eligibility gate or waiting. Unknown original PVR or q retains original slot. Current new expansion gets no penalty, not delayed to another receipt.',credit_reset='Outside credit follows exact original credit reset/receipt-consumed clock; structural REPAIR does not. No original signal/CP recomputation. Outside band is auxiliary calculated from original same-segment close.',case_set=CASES,scope='8 fixed known-outcome mechanism cases, 7 stocks; NOT full candidate test, NOT return/strategy validation; no parameter sweep.',clock='Every computed state is after current close/amount. Original legal candidate execution remains next independent common observation. Full available prefix warm-start. No synthetic suspension dates. No future outcomes in state or score.')
dump('FORMULA_FREEZE.json',freeze)
manifest={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
first=pd.read_csv(P.parent/'ALL_FIRST_ENTRIES.csv');first=first[first.account=='PVR']
mother=pd.read_parquet(P.parent/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet')
cm=mother[['sid','day','CP1_id']].drop_duplicates()
assert not cm.duplicated(['sid','day']).any()
cpids={(r.sid,r.day):r.CP1_id for r in cm.itertuples()}
source={str(U/'STOCK_MANIFEST.json'):sha(U/'STOCK_MANIFEST.json')}
def calculate(f,cp):
 band=pd.Series(np.nan,index=f.index);mean=band.copy()
 for _,g in f.groupby('segment_id',sort=False):
  mean.loc[g.index]=g.close.rolling(21,min_periods=21).mean()
  band.loc[g.index]=mean.loc[g.index]+2*g.close.rolling(21,min_periods=21).std(ddof=0)
 upper=band.groupby(f.segment_id,sort=False).shift(1)
 state='BASE';S=math.nan;Sday=None;seg=None;outside=0.;known=True;rows=[];last_expand=None;last_breach=None
 for day in f.index:
  fr=f.loc[day];cr=cp.loc[day];event=[];p=math.log(float(fr.close));fresh=float(cr.delta_frontier);m=float(cr.m);c=float(cr.credit);receipt=bool(cr.receipt);F=float(cr.candidate);up=float(upper.at[day])
  reason='' if pd.isna(cr.reset_reason) else str(cr.reset_reason)
  if seg is None or fr.segment_id!=seg:
   state='BASE';S=math.nan;Sday=None;seg=fr.segment_id;outside=0.;known=True;last_expand=None;last_breach=None;event.append('source_reset')
  if reason in ['unprepared','E0_invalid','start','E0_down_reset','lower_anchor','source_reset']:
   outside=0.;known=True
  state_before=state;Sbefore=S;Sday_before=Sday
  if state=='EXPAND' and math.isfinite(S) and float(fr.close)<S:
   state='REPAIR';last_breach=str(day.date());event.append('old_expansion_floor_broken')
  assessment_state=state
  prev_frontier=p-fresh if fresh>0 else math.nan
  out_inc=0.
  if fresh>0:
   if math.isfinite(up)and up>0 and math.isfinite(m):
    out_inc=m*max(0.,p-max(prev_frontier,math.log(up)));outside=math.fsum((outside,out_inc))
   else:known=False
  if known and math.isfinite(c):
   assert outside>=-1e-12 and outside<=c+1e-10,(day,outside,c,reason)
  q=outside/c if receipt and known and math.isfinite(c)and c>0 else math.nan
  if math.isfinite(q):
   assert -1e-10<=q<=1+1e-10
   q=min(1.,max(0.,q))
  expanding_now=bool(receipt and math.isfinite(up)and fr.close>up)
  multiplier=1.
  if receipt and assessment_state=='REPAIR' and not expanding_now:
   multiplier=1/(2-q) if math.isfinite(q) else math.nan
  if expanding_now:
   if state=='EXPAND'and math.isfinite(S):
    if F>S:S=F;Sday=str(day.date())
   else:S=F;Sday=str(day.date())
   state='EXPAND';last_expand=str(day.date());event.append('fresh_CP_outside_prior_band')
  elif receipt and state=='EXPAND':
   if not math.isfinite(S)or F>S:S=F;Sday=str(day.date())
  rows.append(dict(day=day,close=float(fr.close),raw_close=float(fr.raw_close),factor=float(fr.factor),segment_id=fr.segment_id,i_target=bool(fr.i_target),i_buy=bool(fr.i_buy),g_grade=fr.g_grade,cp_phase=cr.phase,cp_reset_reason=reason,cp_receipt=receipt,cp_candidate=F,cp_credit=c,cp_delta_frontier=fresh,cp_m=m,cp_r=float(cr.r),cp_frontier_before=prev_frontier,ma21=float(mean.at[day]),upper_current=float(band.at[day]),upper_prior=up,upper_prior_raw=up/float(fr.factor),outside_increment=out_inc,outside_credit=outside,outside_credit_known=known,inside_credit=c-outside if known and math.isfinite(c)else math.nan,q=q,state_before=state_before,state_after_floor_check=assessment_state,state_after=state,S_before=Sbefore,S_before_raw=Sbefore/float(fr.factor),S_source_before=Sday_before,S_after=S,S_after_raw=S/float(fr.factor),S_source_after=Sday,new_expansion_now=expanding_now,multiplier=multiplier,last_expansion_day=last_expand,last_breach_day=last_breach,event='|'.join(event)))
  if receipt:outside=0.;known=True
 z=pd.DataFrame(rows).set_index('day')
 return z
all_daily=[];all_events=[];summ=[];checks=[]
for sid in sorted(set(s for s,d in CASES)):
 refs=manifest[sid]['refs'];f=pd.read_parquet(refs['facts']);cp=pd.read_parquet(refs['CP1']);assert f.index.equals(cp.index)
 for path in [refs['facts'],refs['CP1']]:source[path]=sha(path)
 z=calculate(f,cp)
 assert z.loc[z.cp_receipt,'q'].dropna().between(0,1).all()
 ev=z[z.event.ne('')|z.cp_receipt].copy();ev['sid']=sid;all_events.append(ev.reset_index())
 # Independent reconstruction of each outside numerator within the exact original credit cycle.
 running=0.
 for row in z.itertuples():
  if row.cp_reset_reason in ['unprepared','E0_invalid','start','E0_down_reset','lower_anchor','source_reset']:running=0.
  running=math.fsum((running,row.outside_increment))
  assert abs(running-row.outside_credit)<1e-12
  if row.cp_receipt:running=0.
 for ss,signal in CASES:
  if ss!=sid:continue
  t=f.index.get_loc(pd.Timestamp(signal));row=z.iloc[t]
  assert row.cp_receipt
  for stop in [t,t+1]:
   small=calculate(f.iloc[:stop],cp.iloc[:stop])
   pd.testing.assert_frame_equal(small,z.iloc[:stop],check_exact=True)
   checks.append(dict(sid=sid,signal_day=signal,cutoff=str(f.index[stop-1].date()),prefix_rows=stop,passed=True))
  case=first[first.sid.eq(sid)&first.signal_day.eq(signal)]
  assert len(case)==1,(sid,signal,len(case))
  ca=case.iloc[0];pvr=float(ca.PVR_decision)
  y=row.to_dict();y.update(sid=sid,signal_day=signal,entry_day=ca.entry_day,first_kind=ca.first_kind,original_pvr=pvr,adjusted_pvr=pvr*row.multiplier,original_round_pnl=ca.round_pnl,original_cp_id=cpids.get((sid,signal)),in_original_PVR_empty_mobile_mother=bool(((mother.account=='PVR')&(mother.sid==sid)&(mother.day==signal)).any()),formula_hypothetical_even_if_CORE=ca.first_kind=='core',next_score_effect_is_not_fill_or_return=True)
  summ.append(y)
  sample=z.iloc[max(0,t-20):min(len(z),t+11)].copy();sample['sid']=sid;sample['signal_day']=signal;sample['relative_observation']=np.arange(max(0,t-20),min(len(z),t+11))-t;sample['original_cp_id']=[cpids.get((sid,str(d.date())))for d in sample.index];all_daily.append(sample.reset_index())
pd.concat(all_daily,ignore_index=True).to_csv(O/'FIXED_CASES_DAILY.csv',index=False)
pd.concat(all_events,ignore_index=True).to_csv(O/'FULL_PREFIX_STRUCTURAL_EVENTS.csv',index=False)
summary=pd.DataFrame(summ).sort_values(['signal_day','sid']);summary.to_csv(O/'SIGNAL_SUMMARY.csv',index=False)
pd.DataFrame(checks).to_csv(O/'PREFIX_CHECKS.csv',index=False)
for path,h in source.items():assert sha(path)==h
dump('SOURCE_HASHES.json',source)
dump('CHECKS.json',dict(fixed_cases=len(CASES),stocks=len(set(s for s,d in CASES)),case_daily_rows=sum(len(x)for x in all_daily),prefix_checks=len(checks),outside_credit_bounds=True,credit_cycle_reconstruction=True,source_files_unchanged=True,original_models_recomputed=False,accounts_replayed=False,candidate_universe_test=False,parameter_search=False))
cols=['sid','signal_day','first_kind','raw_close','original_pvr','state_before','state_after_floor_check','state_after','upper_prior_raw','S_before_raw','last_breach_day','q','multiplier','adjusted_pvr','new_expansion_now','in_original_PVR_empty_mobile_mother']
print(summary[cols].round(8).to_string(index=False));print('DONE',len(checks),'prefix tests.')
