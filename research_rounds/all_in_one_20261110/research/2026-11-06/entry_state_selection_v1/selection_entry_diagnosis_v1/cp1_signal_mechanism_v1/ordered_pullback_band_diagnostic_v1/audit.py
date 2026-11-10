from pathlib import Path
import json,hashlib,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
F=json.loads((O/'FORMULA_FREEZE.json').read_text())
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
manifest={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
first=pd.read_csv(O.parent.parent/'ALL_FIRST_ENTRIES.csv')
first=first[first.account=='PVR']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources={str(U/'STOCK_MANIFEST.json'):sha(U/'STOCK_MANIFEST.json'),str(O/'FORMULA_FREEZE.json'):sha(O/'FORMULA_FREEZE.json')}
def calc(f,cp):
 p=np.log(f.close)
 ema=p.groupby(f.segment_id,sort=False).transform(lambda x:x.ewm(span=21,adjust=False,min_periods=21).mean())
 sig=p.groupby(f.segment_id,sort=False).transform(lambda x:x.rolling(21,min_periods=21).std(ddof=0))
 ema_prev=ema.groupby(f.segment_id,sort=False).shift()
 sig_prev=sig.groupby(f.segment_id,sort=False).shift()
 qb=f.amount.groupby(f.segment_id,sort=False).transform(lambda x:x.shift().rolling(21,min_periods=21).median())
 q=f.amount/qb
 out=[];seg=None;direction=0;leg=[];upmean=downmean=H=L=S_peak=math.nan;Hday=Lday=None;prevp=math.nan;prevday=None;prevsig=math.nan
 for i,(day,row) in enumerate(f.iterrows()):
  pp=float(p.at[day]);qq=float(q.at[day]);ss=float(sig.at[day]);mm=float(ema_prev.at[day]);ps=float(sig_prev.at[day]);event=''
  if row.segment_id!=seg:
   seg=row.segment_id;direction=0;leg=[];upmean=downmean=H=L=S_peak=math.nan;Hday=Lday=None;prevp=math.nan;prevday=None;prevsig=math.nan;event='source_reset'
  rr=pp-prevp if math.isfinite(prevp) else math.nan
  if math.isfinite(rr):
   d=1 if rr>0 else -1 if rr<0 else direction
   if d!=direction and d!=0:
    if d==-1:
     H=prevp;Hday=prevday;S_peak=max(prevsig,math.log1p(.001)) if math.isfinite(prevsig) else math.nan
     upmean=float(np.mean(leg)) if leg and np.isfinite(leg).all() else math.nan
     L=math.nan;Lday=None;downmean=math.nan;event='peak_confirmed_start_fall'
    elif d==1 and direction==-1:
     L=prevp;Lday=prevday;downmean=float(np.mean(leg)) if leg and np.isfinite(leg).all() else math.nan;event='trough_confirmed_new_recovery'
    direction=d;leg=[qq]
   elif d!=0:leg.append(qq)
  G=D=R=V=B=J=math.nan
  if direction==-1:state='FALL';J=0.
  elif direction==1 and all(math.isfinite(x)for x in [H,L,upmean,downmean,S_peak,ss,mm,ps]):
   G=max(pp-L,0.);D=H-L;R=G/(G+D) if G+D>0 else 0.;V=upmean/(upmean+downmean);B=S_peak/(S_peak+max(ss,math.log1p(.001)));J=100*R*V*B
   state='RECOVERY' if pp<=mm else 'BUILD' if pp<=mm+ps else 'EXPAND'
  else:state='UNKNOWN'
  out.append(dict(day=day,close=float(row.close),raw_close=float(row.raw_close),amount=float(row.amount),amount_ratio=qq,raw_ema_prior=math.exp(mm)/float(row.factor) if math.isfinite(mm) else math.nan,raw_upper_prior=math.exp(mm+2*ps)/float(row.factor) if math.isfinite(mm+ps) else math.nan,raw_lower_prior=math.exp(mm-2*ps)/float(row.factor) if math.isfinite(mm+ps) else math.nan,log_sigma_current=ss,log_sigma_prior=ps,bandwidth_log_4sigma=4*ss,bandwidth_change=ss/prevsig-1 if math.isfinite(prevsig) and prevsig>0 else math.nan,cp_receipt=bool(cp.at[day,'receipt']),cp_phase=cp.at[day,'phase'],cp_credit=float(cp.at[day,'credit']),cp_displacement=float(cp.at[day,'displacement']),cp_scale=float(cp.at[day,'scale']),cp_reset_reason=cp.at[day,'reset_reason'],i_target=bool(row.i_target),i_buy=bool(row.i_buy),event=event,state=state,peak_day=Hday,trough_day=Lday,raw_peak=math.exp(H)/float(row.factor) if math.isfinite(H) else math.nan,raw_trough=math.exp(L)/float(row.factor) if math.isfinite(L) else math.nan,up_leg_mean_q=upmean,down_leg_mean_q=downmean,recovery_G=G,pullback_D=D,price_recovery_fraction=R,turnover_contraction_fraction=V,band_contraction_fraction=B,diagnostic_score=J))
  prevp=pp;prevday=str(day.date());prevsig=ss
 return pd.DataFrame(out).set_index('day')
allrows=[];summ=[];checks=[]
for sid,date,label in F['cases']:
 refs=manifest[sid]['refs'];f=pd.read_parquet(refs['facts']);inp=pd.read_parquet(refs['CP1_input']);f=f.reindex(inp.index);assert np.allclose(f.close,inp.close,rtol=0,atol=1e-12);f['amount']=inp.amount;cp=pd.read_parquet(refs['CP1']).reindex(f.index)
 for path in [refs['facts'],refs['CP1'],refs['CP1_input']]:sources[path]=sha(path)
 n=f.index.get_loc(pd.Timestamp(date));f=f.iloc[:n+1];cp=cp.reindex(f.index)
 z=calc(f,cp)
 for stop in [len(f)-1,len(f)]:
  small=calc(f.iloc[:stop],cp.iloc[:stop]);pd.testing.assert_frame_equal(small,z.iloc[:stop],check_exact=True)
  checks.append(dict(sid=sid,cutoff=str(f.index[stop-1].date()),passed=True,rows=stop))
 sub=z.iloc[-21:].reset_index();sub['sid']=sid;sub['signal_day']=date;sub['known_original_outcome']=label;sub['relative_observation']=np.arange(-20,1);allrows.append(sub)
 r=z.iloc[-1].to_dict();a=first[first.sid.eq(sid)&first.signal_day.eq(date)];assert len(a)==1,(sid,date,len(a));a=a.iloc[0]
 assert bool(r['cp_receipt'])
 r.update(sid=sid,signal_day=date,known_original_outcome=label,original_round_pnl=float(a.round_pnl),original_PVR=float(a.PVR_decision),first_kind=a.first_kind)
 summ.append(r)
pd.concat(allrows).to_csv(O/'SIX_CASES_PRIOR20_AND_SIGNAL_DAILY.csv',index=False)
pd.DataFrame(summ).to_csv(O/'SIX_SIGNAL_SUMMARY.csv',index=False)
pd.DataFrame(checks).to_csv(O/'PREFIX_CHECKS.csv',index=False)
for path,h in sources.items():assert sha(path)==h,path
(O/'SOURCE_HASHES.json').write_text(json.dumps(sources,indent=2))
(O/'CHECKS.json').write_text(json.dumps(dict(cases=6,daily_rows=126,prefix_checks=len(checks),no_original_model_recompute=True,no_accounts=True,no_rank_test=True,no_parameter_search=True,no_full_universe_expansion=True,source_hashes_unchanged=True),indent=2))
print(pd.DataFrame(summ)[['sid','signal_day','known_original_outcome','state','peak_day','trough_day','raw_peak','raw_trough','raw_close','up_leg_mean_q','down_leg_mean_q','price_recovery_fraction','turnover_contraction_fraction','band_contraction_fraction','diagnostic_score','original_round_pnl']].to_string(index=False))
