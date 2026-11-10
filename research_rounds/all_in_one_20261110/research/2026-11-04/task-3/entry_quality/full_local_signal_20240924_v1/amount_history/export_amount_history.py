"""One fixed-date amount-history feature, no PVR/E0/I/account/ranking calls."""
from pathlib import Path
from fractions import Fraction
from statistics import median
from collections import Counter
import hashlib,json,time
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[1]
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
RAW=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet')
FEATURES=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
LIQUIDITY=ENTRY/'no_future_cap_selection_v1/LIQUIDITY20.parquet'
DAY='2024-09-24';EXPECTED_SOURCE_SHA='11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b'
CASES=['000620.SZ','002583.SZ','300666.SZ','300085.SZ']


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    if isinstance(x,(pd.Timestamp,np.datetime64)):return str(pd.Timestamp(x))
    if isinstance(x,np.generic):x=x.item()
    if x is None or x is pd.NA or x is pd.NaT:return None
    return None if isinstance(x,float)and not np.isfinite(x)else x


def save(n,x):(HERE/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def one(g):
    dates=g.trade_date.to_numpy(dtype='datetime64[ns]');day=np.datetime64(DAY,'ns')
    j=int(np.searchsorted(dates,day));r=dict(day=DAY,current_amount_native=np.nan,amount_hist252_percentile=np.nan,
        amount_hist252_knownN=0,amount_hist252_n_less=pd.NA,amount_hist252_n_equal=pd.NA,
        amount_hist252_window_start=pd.NaT,amount_hist252_window_end=pd.NaT,
        amount_hist252_status='MISSING_TARGET_BAR',amount20_recomputed_native=np.nan)
    if j==len(g)or dates[j]!=day:return r
    c=g.close.to_numpy(float);a=g.amount.to_numpy(float)
    known=g.source.notna()&g.source.astype('string').str.strip().ne('').fillna(False)
    valid=np.isfinite(c)&(c>0)&np.isfinite(a)&(a>0)&known.to_numpy(bool)
    r['current_amount_native']=a[j]
    if not valid[j]:r['amount_hist252_status']='INVALID_CURRENT_PRICE_AMOUNT_OR_SOURCE';return r
    source=g.source.astype(str).to_numpy()
    boundary=(~valid)|np.r_[True,~valid[:-1]]|np.r_[True,source[1:]!=source[:-1]]
    start=int(np.flatnonzero(boundary[:j+1])[-1]);n=min(252,j-start)
    r['amount_hist252_knownN']=n;r['amount_hist252_status']='INSUFFICIENT_PRIOR_VALID_BLOCK'
    if j-start>=20:r['amount20_recomputed_native']=float(np.median(a[j-20:j]))
    if n<252:return r
    history=a[j-252:j];assert len(history)==252 and np.isfinite(history).all()and(history>0).all()
    less=int((history<a[j]).sum());equal=int((history==a[j]).sum())
    r.update(amount_hist252_percentile=(less+.5*equal)/252,amount_hist252_n_less=less,amount_hist252_n_equal=equal,
        amount_hist252_window_start=pd.Timestamp(dates[j-252]),amount_hist252_window_end=pd.Timestamp(dates[j-1]),
        amount_hist252_status='KNOWN_252_PRIOR_VALID_STOCK_OBSERVATIONS')
    return r


def main():
    assert not(HERE/'AMOUNT_HISTORY_2024_09_24.parquet').exists()
    started=time.monotonic();source_stat=SOURCE.stat();assert sha(SOURCE)==EXPECTED_SOURCE_SHA
    feature_cols=['sid','day','score','pvr_status','target_row_present','current_close_qfq','current_amount_passthrough','E_fast','E_slow','fast_status','slow_status']
    feature=ds.dataset(FEATURES).to_table(columns=feature_cols,filter=ds.field('day')==DAY).to_pandas()
    liq=ds.dataset(LIQUIDITY).to_table(filter=ds.field('day')==DAY).to_pandas()
    assert len(feature)==len(liq)==5517 and feature.sid.nunique()==liq.sid.nunique()==5517
    frame=ds.dataset(SOURCE).to_table(columns=['symbol','trade_date','close','amount','source'],filter=ds.field('trade_date')<=pd.Timestamp(DAY)).to_pandas()
    assert frame.trade_date.max()<=pd.Timestamp(DAY)
    groups={sid:g.sort_values('trade_date').reset_index(drop=True)for sid,g in frame.groupby('symbol',sort=False)}
    result=[]
    for sid in sorted(feature.sid):
        g=groups.get(sid,pd.DataFrame(columns=['trade_date','close','amount','source']))
        r=one(g);r['sid']=sid;r['source_prefix_rows']=len(g);result.append(r)
    out=feature.merge(liq,on=['sid','day'],how='left',validate='one_to_one').merge(pd.DataFrame(result),on=['sid','day'],how='left',validate='one_to_one')
    assert len(out)==5517 and not out.duplicated(['sid','day']).any()
    a=out.current_amount_native.to_numpy(float);b=out.current_amount_passthrough.to_numpy(float);finite=np.isfinite(a)&np.isfinite(b)
    assert np.array_equal(np.isfinite(a),np.isfinite(b))and np.array_equal(a[finite].view(np.uint64),b[finite].view(np.uint64))
    a=out.amount20_recomputed_native.to_numpy(float);b=out.amount20_prior_native.to_numpy(float);finite=np.isfinite(a)&np.isfinite(b)
    assert np.array_equal(np.isfinite(a),np.isfinite(b))and np.array_equal(a[finite].view(np.uint64),b[finite].view(np.uint64))
    out=out.drop(columns='amount20_recomputed_native')
    out['amount_hist252_unit']='VENDOR_NATIVE_AMOUNT_NO_THRESHOLD_OR_RANKING'
    out['amount_hist252_clock']='252_PRIOR_VALID_STOCK_OBSERVATIONS_NOT252_MARKET_SESSIONS'
    for name in ['historical_listing_identity','historical_ST','historical_halt','historical_limit_state','executable_eligibility']:
        out[name]='UNKNOWN_NOT_CERTIFIED'
    out.to_parquet(HERE/'AMOUNT_HISTORY_2024_09_24.parquet',index=False,compression='zstd')
    # Independent original unadjusted amount, Python comparisons and median.
    raw=ds.dataset(RAW).to_table(columns=['symbol','trade_date','close','amount','source'],filter=ds.field('symbol').isin(CASES)&(ds.field('trade_date')<=pd.Timestamp(DAY))).to_pandas()
    hand=[];evidence=[]
    for sid in CASES:
        g=raw.loc[raw.symbol.eq(sid)].sort_values('trade_date').reset_index(drop=True)
        j=g.index[g.trade_date.eq(pd.Timestamp(DAY))].item();current=float(g.loc[j,'amount'])
        prior=g.loc[j-252:j-1,['trade_date','amount']];assert len(prior)==252
        assert np.isfinite(g.loc[j-252:j,'close']).all()and g.loc[j-252:j,'close'].gt(0).all()
        assert g.loc[j-252:j,'source'].nunique(dropna=False)==1
        values=[float(v)for v in prior.amount];assert all(np.isfinite(v)and v>0 for v in values)
        n_less=sum(v<current for v in values);n_equal=sum(v==current for v in values)
        fraction=Fraction(2*n_less+n_equal,504);hand_value=float(fraction)
        median20=float(median(values[-20:]))
        saved=out.loc[out.sid.eq(sid)].iloc[0]
        assert saved.amount_hist252_knownN==252 and saved.amount_hist252_n_less==n_less and saved.amount_hist252_n_equal==n_equal
        assert hand_value==saved.amount_hist252_percentile and median20==saved.amount20_prior_native and current==saved.current_amount_native
        standard=groups[sid].loc[:,['trade_date','amount']]
        standard=standard.loc[standard.trade_date.isin(g.loc[j-252:j,'trade_date'])].reset_index(drop=True)
        expected=g.loc[j-252:j,['trade_date','amount']].reset_index(drop=True)
        assert standard.equals(expected),(sid,'raw/standardized amount253 mismatch')
        hand.append(dict(sid=sid,day=DAY,current_amount_native=current,prior252_knownN=252,n_less=n_less,n_equal=n_equal,
            empirical_midrank_fraction=str(fraction),amount_hist252_percentile=hand_value,prior20_median_native=median20,
            window_start=str(prior.trade_date.iloc[0].date()),window_end=str(prior.trade_date.iloc[-1].date()),raw_standardized_253_amounts_exact=True))
        evidence.append(dict(sid=sid,day=DAY,current_amount_native=current,prior252_dates=prior.trade_date.dt.strftime('%Y-%m-%d').tolist(),prior252_amount_native=values))
    pd.DataFrame(hand).to_csv(HERE/'FOUR_RAW_HAND_CHECKS.csv',index=False);save('FOUR_RAW_252_WINDOWS.json',evidence)
    assert SOURCE.stat().st_size==source_stat.st_size and SOURCE.stat().st_mtime_ns==source_stat.st_mtime_ns
    sources=[SOURCE,RAW,FEATURES,LIQUIDITY,Path(__file__)]
    save('COMPLETION.json',dict(status='COMPLETE_FIXED_AMOUNT_HISTORY_NO_SIGNAL_OR_ACCOUNT',day=DAY,rows=5517,
        source_prefix_rows_read=len(frame),definition='(#prior252_amount < current + .5 * #prior252_amount == current)/252; excludes current; full same valid/source block required',
        status_counts=dict(Counter(out.amount_hist252_status)),prior20_status_counts=dict(Counter(out.amount20_status)),
        current_amount_equals_saved_PVR_input_exact=True,median20_equals_saved_prior20_exact=True,
        four_originalraw_handchecks=hand,source_sha256={str(p):sha(p)for p in sources},
        output_sha256=sha(HERE/'AMOUNT_HISTORY_2024_09_24.parquet'),elapsed_seconds=time.monotonic()-started,
        new_PVR_E0_I_G1_calls=0,new_accounts=0,new_cap_ST_sector_inputs=0,new_thresholds_or_rankings=0,forward_labels=False))
    print(json.dumps(clean(dict(rows=5517,status_counts=dict(Counter(out.amount_hist252_status)),handchecks=hand,seconds=time.monotonic()-started)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
