"""Small fixed inputs + physical-prefix checks only. No PnL/model/universe export."""
from pathlib import Path
import hashlib,json,time,types
import pandas as pd
import numpy as np
from features import compute_features, PVR_COLUMNS, FEATURE_COLUMNS, ORIGINAL_PVR_SOURCE_SHA256
O=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def normalized(x):
 if isinstance(x,dict):return {str(k):normalized(v) for k,v in x.items()}
 if isinstance(x,list):return [normalized(v) for v in x]
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,(np.bool_,bool)):return bool(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 if isinstance(x,pd.Timestamp):return str(x.date())
 return x

t0=time.monotonic();source=W/'pvr-current-v3-information-capital-20261101/original_score_function.py';assert sha(source)==ORIGINAL_PVR_SOURCE_SHA256
namespace={'pd':pd,'np':np};exec(compile(source.read_text(),str(source),'exec'),namespace);score=namespace['score']
def fixture(n=180):
 t=np.arange(n);c=100*np.exp(.003*t+.035*np.sin(t/7))
 return pd.DataFrame(dict(open=c,high=c*1.01,low=c*.99,close=c,amount=1e8*(1+.15*np.cos(t/9)),segment_id=0,price_eligible=True,observed_bar=True,is_observed_bar=True,source_invalid=False,synthetic_event_bar=False,raw_close=c,adjustment_factor=1.),index=pd.bdate_range('2020-01-02',periods=n))
checks=[];inputs={};samples=[]
def run(label,f):
 before=f.copy(deep=True);z=compute_features(f);pd.testing.assert_frame_equal(before,f,check_exact=True)
 pd.testing.assert_frame_equal(z[list(PVR_COLUMNS)],score(f),check_exact=True);checks.append(label+':original_eight_columns_exact')
 cuts=sorted(set(x for x in [0,1,5,20,21,22,63,64,65,83,84,85,95,len(f)//2,len(f)-1,len(f)] if 0<=x<=len(f)))
 for cut in cuts:pd.testing.assert_frame_equal(compute_features(f.iloc[:cut]),z.iloc[:cut],check_exact=True)
 checks.append(label+':all_columns_physical_prefix_exact_'+str(len(cuts)))
 cut=min(90,len(f));changed=f.copy(deep=True)
 if cut<len(f):
  ix=changed.index[cut:];changed.loc[ix,'close']*=np.linspace(2,5,len(ix));changed.loc[ix,'high']=changed.loc[ix,'close']*1.1;changed.loc[ix,'low']=changed.loc[ix,'close']*.9;changed.loc[ix,'amount']*=123
  pd.testing.assert_frame_equal(compute_features(changed).iloc[:cut],z.iloc[:cut],check_exact=True);checks.append(label+':future_perturbation_prefix_exact')
 samples.append(dict(label=label,input_rows=len(f),original_PVR_known=int(z.score.notna().sum()),original_valid=int(z.pvr_valid_observation.sum()),first_PVR_known=None if not z.score.notna().any() else str(z.index[z.score.notna()][0].date()),sample_last=normalized(z.iloc[-1].to_dict()) if len(z) else None))
 return z
base=fixture();z=run('synthetic_contiguous',base)
assert z.sign_persistence21_w09.iloc[:21].isna().all() and z.sign_persistence21_w09.iloc[21:].notna().all();assert z.logreturn_std20.iloc[:20].isna().all() and z.logreturn_std20.iloc[20:].notna().all();assert z.return5.iloc[:5].isna().all() and z.return5.iloc[5:].notna().all();assert z.close_gap_prior_high20.iloc[:20].isna().all();assert z.score.iloc[:84].isna().all() and np.isfinite(z.score.iloc[84]);checks.append('exact_warmups_5_20_21_84_zero_based')
# Scalar independent reconstruction, last20/21 endpoints fixed, includes current return.
i=105;r=np.log(base.close).diff();weights=.9**np.arange(20,-1,-1);weights/=weights.sum();expected=float(np.dot(weights,np.sign(r.iloc[i-20:i+1].to_numpy())))
assert z.sign_persistence21_w09.iloc[i]==expected;assert abs(z.logreturn_std20.iloc[i]-np.std(r.iloc[i-19:i+1],ddof=0))<1e-15;assert z.return5.iloc[i]==base.close.iloc[i]/base.close.iloc[i-5]-1;assert z.return20.iloc[i]==base.close.iloc[i]/base.close.iloc[i-20]-1;assert z.close_gap_prior_high20.iloc[i]==base.close.iloc[i]/max(base.close.iloc[i-20:i])-1;checks.append('independent_scalar_weight_std_endpoint_reconstructions')
# Constant close: equal high is NOT a breakout, ties retain zero; no epsilon gate.
c=fixture(100);c.loc[:,['open','close']]=100.;c.loc[:,'high']=102.;c.loc[:,'low']=98.;c.loc[:,'amount']=1e8;cz=run('synthetic_constant',c);assert cz.score.iloc[-1]==50 and cz.sign_persistence21_w09.iloc[-1]==0 and cz.logreturn_std20.iloc[-1]==0 and cz.return20.iloc[-1]==0 and cz.breakout_prior_high20.iloc[-1]==False;assert cz.close_location_in_day_range.iloc[-1]==.5;checks.append('constant_zero_return_zero_persistence_no_breakout')
q=base.copy();q.loc[q.index[30],'amount']=np.nan;q.loc[q.index[65],'observed_bar']=False;q.loc[q.index[100],'synthetic_event_bar']=True;q.loc[q.index[130],'source_invalid']=True;q.loc[q.index[150]:,'segment_id']=1;qz=run('synthetic_invalid_and_source_reset',q)
for i in [30,65,100,130]:assert not qz.pvr_valid_observation.iloc[i] and qz.pvr_block_observation.iloc[i+1]==0 and pd.isna(qz.return5.iloc[i+1]);assert qz.pvr_status.iloc[i]=='INVALID_ORIGINAL_PVR_OBSERVATION'
assert qz.pvr_block_observation.iloc[150]==0 and pd.isna(qz.return20.iloc[169]) and pd.notna(qz.return20.iloc[170]);checks.append('invalid_and_source_boundaries_reset_no_crossing')
zero=base.copy();zero.loc[zero.index[90],['high','low']]=zero.close.iloc[90];zz=compute_features(zero);assert pd.isna(zz.close_location_in_day_range.iloc[90]) and zz.close_location_in_day_range_status.iloc[90]=='UNKNOWN_ZERO_RANGE';pd.testing.assert_frame_equal(zz.drop(columns=['close_location_in_day_range','close_location_in_day_range_status']),z.drop(columns=['close_location_in_day_range','close_location_in_day_range_status']),check_exact=True);checks.append('zero_range_unknown_does_not_change_PVR_or_other_features')
raw=base.copy();raw.loc[:,'raw_close']=.001;raw.loc[:,'adjustment_factor']=777.;pd.testing.assert_frame_equal(compute_features(raw),z,check_exact=True);checks.append('raw_and_factor_columns_never_mixed_into_signal_features')
# Lexically first three original fixed identities; no return/wealth or feature criterion.
manifest_path=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';manifest=json.loads(manifest_path.read_text());chosen=sorted(manifest,key=lambda x:x['symbol'])[:3]
for record in chosen:
 p=next(Path(p) for p in record['source_sha256'] if p.endswith('/signal.parquet'));assert sha(p)==record['source_sha256'][str(p)];f=pd.read_parquet(p);run('original_signal:'+record['symbol'],f);inputs[str(p)]=sha(p)
 if {'raw_close','adjustment_factor'}<=set(f):
  good=np.isfinite(f.close)&np.isfinite(f.raw_close)&np.isfinite(f.adjustment_factor);error=float(np.max(np.abs(f.loc[good,'close']-f.loc[good,'raw_close']*f.loc[good,'adjustment_factor']))) if good.any() else None;checks.append(record['symbol']+':signal_raw_factor_max_abs_error='+str(error))
seconds=time.monotonic()-t0;assert seconds<60
save('SMALL_SAMPLE_CHECKS.json',dict(passed=True,seconds=seconds,checks=checks,number_real_symbols=len(chosen),real_symbol_selection='lexically first3 in frozen original1709 manifest, no feature/outcome selection',samples=samples,new_accounts=0,models_replayed=0,universe_feature_export=False,no_future_labels_generated=True));save('SOURCE_SHA256.json',dict(original_PVR_function={str(source):sha(source)},manifest={str(manifest_path):sha(manifest_path)},small_real_inputs=inputs,feature_code_sha256=sha(O/'features.py'),verify_code_sha256=sha(Path(__file__))))
print('PASS',len(checks),'checks, seconds',round(seconds,3),flush=True)
