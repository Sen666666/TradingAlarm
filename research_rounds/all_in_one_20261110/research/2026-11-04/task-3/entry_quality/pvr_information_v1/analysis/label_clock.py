"""Frozen price-reference labels only; no filling, strategy or financial import."""
import numpy as np
import pandas as pd

KEY=['window','day','sid']
HORIZONS=(5,20,60)
def prefix(x):return np.pad(np.cumsum(x,axis=1,dtype=np.int32),((0,0),(1,0)))
def build_labels(features,quotes,keys,calendars):
 out=[];checks=[]
 for window,calendar in calendars.items():
  q=quotes.loc[quotes.window.eq(window)].reset_index(drop=True);f=features.loc[features.window.eq(window)].reset_index(drop=True);kk=keys.loc[keys.window.eq(window)].reset_index(drop=True)
  assert q[KEY].equals(f[KEY]);symbols=np.asarray(pd.unique(q.sid));n=len(calendar);assert len(q)==len(symbols)*n
  assert np.array_equal(q.day.to_numpy().reshape(-1,n),np.tile(np.asarray(calendar),(len(symbols),1)))
  assert np.array_equal(q.sid.to_numpy().reshape(-1,n),np.repeat(symbols[:,None],n,axis=1))
  shape=(len(symbols),n);array=lambda z:np.asarray(z).reshape(shape)
  op=array(q.open.to_numpy(float));cl=array(q.close.to_numpy(float));obs=array(q.observed.to_numpy(bool));valid=array(q.valid.to_numpy(bool));present=array(f.stock_source_row_present.to_numpy(bool));block=array(q.block.to_numpy(float,na_value=np.nan));segment=array(f.source_segment.to_numpy(float));good=present&obs&valid&np.isfinite(cl)&(cl>0)
  si=pd.Index(symbols).get_indexer(kk.sid);ti=pd.Index(calendar).get_indexer(kk.day);inside=(si>=0)&(ti>=0);ss=si.clip(0);tt=ti.clip(0);nn=(tt+1).clip(max=n-1);next_mature=inside&(ti+1<n)
  curpresent=inside&present[ss,tt];curobs=inside&obs[ss,tt];curvalid=inside&valid[ss,tt];curprice=inside&np.isfinite(cl[ss,tt])&(cl[ss,tt]>0)
  npresent=next_mature&present[ss,nn];nobs=next_mature&obs[ss,nn];nvalid=next_mature&valid[ss,nn];nprice=next_mature&np.isfinite(op[ss,nn])&(op[ss,nn]>0)
  nextblock=np.isfinite(block[ss,tt])&np.isfinite(block[ss,nn])&(block[ss,tt]==block[ss,nn]);nextsegment=np.isfinite(segment[ss,tt])&np.isfinite(segment[ss,nn])&(segment[ss,tt]==segment[ss,nn])
  start=curpresent&curobs&curvalid&curprice;openok=start&npresent&nobs&nvalid&nprice&nextblock&nextsegment
  row=kk.copy();row['current_row_missing']=inside&~curpresent;row['current_not_observed']=inside&curpresent&~curobs;row['current_joint_invalid']=inside&curpresent&~curvalid;row['current_close_nonpositive_or_nonfinite']=inside&~curprice;row['next_shared_session_unavailable']=~next_mature;row['next_row_missing']=next_mature&~npresent;row['next_not_observed']=npresent&~nobs;row['next_joint_invalid']=npresent&~nvalid;row['next_open_nonpositive_or_nonfinite']=next_mature&~nprice;row['halt_status']='NOT_RECORDED_UNKNOWN'
  row['next_sourceblock_transition']=next_mature&np.isfinite(block[ss,tt])&np.isfinite(block[ss,nn])&~nextblock;row['next_source_segment_transition']=next_mature&np.isfinite(segment[ss,tt])&np.isfinite(segment[ss,nn])&~nextsegment;row['next_source_id_unknown']=next_mature&(~np.isfinite(block[ss,tt])|~np.isfinite(block[ss,nn])|~np.isfinite(segment[ss,tt])|~np.isfinite(segment[ss,nn]))
  with np.errstate(divide='ignore',invalid='ignore'):row['next_OPEN_gap']=np.where(openok,op[ss,nn]/cl[ss,tt]-1,np.nan)
  badprefix=prefix(~good);missingprefix=prefix(~present);nonobsprefix=prefix(present&~obs);invalidprefix=prefix(present&~valid)
  for h in HORIZONS:
   end=(tt+h).clip(max=n-1);mature=inside&(ti+h<n);ep=mature&present[ss,end];eo=mature&obs[ss,end];ev=mature&valid[ss,end];eprice=mature&np.isfinite(cl[ss,end])&(cl[ss,end]>0)
   knownblock=np.isfinite(block[ss,tt])&np.isfinite(block[ss,end]);sameblock=knownblock&(block[ss,tt]==block[ss,end]);knownsegment=np.isfinite(segment[ss,tt])&np.isfinite(segment[ss,end]);samesegment=knownsegment&(segment[ss,tt]==segment[ss,end])
   endpoint=mature&start&ep&eo&ev&eprice&sameblock&samesegment;eligible=endpoint&openok
   status=np.full(len(kk),'KNOWN',object)
   reasons=[('OUTSIDE_WINDOW_CALENDAR',~inside),('HORIZON_UNMATURED',inside&~mature),('CURRENT_ROW_MISSING',~curpresent),('CURRENT_NOT_OBSERVED',~curobs),('CURRENT_JOINT_INVALID',~curvalid),('CURRENT_CLOSE_INVALID',~curprice),('NEXT_SHARED_ROW_MISSING',~npresent),('NEXT_NOT_OBSERVED',~nobs),('NEXT_JOINT_INVALID',~nvalid),('NEXT_OPEN_INVALID',~nprice),('ENDPOINT_ROW_MISSING',~ep),('ENDPOINT_NOT_OBSERVED',~eo),('ENDPOINT_JOINT_INVALID',~ev),('ENDPOINT_CLOSE_INVALID',~eprice),('SOURCE_BLOCK_TRANSITION',knownblock&~sameblock),('SOURCE_SEGMENT_TRANSITION',knownsegment&~samesegment),('SOURCE_ID_UNKNOWN',~knownblock|~knownsegment)]
   # Earlier reason wins; nonexclusive flags below preserve concurrent failures.
   for name,mask in reversed(reasons):status[mask]=name
   assert np.array_equal(status=='KNOWN',eligible)
   tag='h'+str(h)+'_';row[tag+'status']=status;row[tag+'mature']=mature;row[tag+'endpoint_missing']=mature&~ep;row[tag+'endpoint_not_observed']=ep&~eo;row[tag+'endpoint_joint_invalid']=ep&~ev;row[tag+'endpoint_close_invalid']=mature&~eprice;row[tag+'sourceblock_transition']=mature&knownblock&~sameblock;row[tag+'source_segment_transition']=mature&knownsegment&~samesegment;row[tag+'source_id_unknown']=mature&(~knownblock|~knownsegment)
   count=lambda p:p[ss,end+1]-p[ss,tt+1]
   for name,p in [('any_future_missing',missingprefix),('any_future_nonobserved',nonobsprefix),('any_future_joint_invalid',invalidprefix)]:row[tag+name]=pd.arrays.BooleanArray(count(p)>0,~mature)
   with np.errstate(divide='ignore',invalid='ignore'):
    ro=np.where(eligible,cl[ss,end]/op[ss,nn]-1,np.nan);rc=np.where(endpoint,cl[ss,end]/cl[ss,tt]-1,np.nan)
   row[tag+'next_OPEN_return']=ro;row[tag+'decision_CLOSE_return']=rc
   both=eligible;lhs=1+rc[both];rhs=(1+row.loc[both,'next_OPEN_gap'].to_numpy(float))*(1+ro[both]);assert np.allclose(lhs,rhs,rtol=1e-10,atol=1e-12)
   checks.append(dict(window=window,horizon=h,keys=len(kk),mature=int(mature.sum()),primary_known=int(eligible.sum()),close_known=int(endpoint.sum()),identity_count=int(both.sum()),identity_max_abs_error=float(np.max(np.abs(lhs-rhs))) if both.any() else 0))
   if h==60:
    complete=eligible&(count(badprefix)==0);masked=np.where(good,cl,np.nan);high=pd.DataFrame(masked.T).rolling(60,min_periods=60).max().to_numpy().T;low=pd.DataFrame(masked.T).rolling(60,min_periods=60).min().to_numpy().T
    with np.errstate(divide='ignore',invalid='ignore'):peak=np.where(complete,high[ss,end]/op[ss,nn]-1,np.nan);trough=np.where(complete,low[ss,end]/op[ss,nn]-1,np.nan)
    row['h60_entire_future_path_valid']=complete;row['h60_max_CLOSE_from_next_OPEN']=peak;row['h60_min_CLOSE_from_next_OPEN']=trough;row['h60_future_tail_ge30']=pd.arrays.BooleanArray(peak>=.3,~complete)
  out.append(row)
 return pd.concat(out,ignore_index=True),checks
