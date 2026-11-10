"""Two explicitly fixed amount-only dates. No future paths until cohorts freeze."""
from pathlib import Path
from fractions import Fraction
from statistics import median
from collections import Counter
import hashlib,importlib.util,json,time
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ENTRY=HERE.parents[2]
ORIGINAL=ENTRY/'full_local_signal_20240924_v1/amount_history/export_amount_history.py'
spec=importlib.util.spec_from_file_location('frozen924_amount_feature_only',ORIGINAL)
BASE=importlib.util.module_from_spec(spec);spec.loader.exec_module(BASE)
DAYS=['2022-01-24','2026-01-15'];CASES=['000620.SZ','002583.SZ','300666.SZ','300085.SZ']
SOURCE=BASE.SOURCE;RAW=BASE.RAW;FEATURES=BASE.FEATURES;LIQUIDITY=BASE.LIQUIDITY


def save(out,name,x):(out/name).write_text(json.dumps(BASE.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    started=time.monotonic();assert BASE.sha(SOURCE)==BASE.EXPECTED_SOURCE_SHA
    outputs={day:ROOT/day/'amount_history'for day in DAYS}
    for out in outputs.values():out.mkdir(parents=True,exist_ok=True);assert not(out/'COMPLETION.json').exists()
    feature_cols=['sid','day','score','pvr_status','target_row_present','current_close_qfq','current_amount_passthrough','E_fast','E_slow','fast_status','slow_status']
    feature=ds.dataset(FEATURES).to_table(columns=feature_cols,filter=ds.field('day').isin(DAYS)).to_pandas()
    liquidity=ds.dataset(LIQUIDITY).to_table(filter=ds.field('day').isin(DAYS)).to_pandas()
    assert len(feature)==len(liquidity)==11034
    data=ds.dataset(SOURCE).to_table(columns=['symbol','trade_date','close','amount','source'],filter=ds.field('trade_date')<=pd.Timestamp(max(DAYS))).to_pandas()
    groups={sid:g.sort_values('trade_date').reset_index(drop=True)for sid,g in data.groupby('symbol',sort=False)}
    raw=ds.dataset(RAW).to_table(columns=['symbol','trade_date','close','amount','source'],filter=ds.field('symbol').isin(CASES)&(ds.field('trade_date')<=pd.Timestamp(max(DAYS)))).to_pandas()
    raw_groups={sid:g.sort_values('trade_date').reset_index(drop=True)for sid,g in raw.groupby('symbol',sort=False)}
    hashes={str(p):BASE.sha(p)for p in [SOURCE,RAW,FEATURES,LIQUIDITY,ORIGINAL,Path(__file__)]}
    for day in DAYS:
        at=time.monotonic();outdir=outputs[day];current=feature.loc[feature.day.eq(day)];liq=liquidity.loc[liquidity.day.eq(day)]
        assert len(current)==len(liq)==5517
        BASE.DAY=day  # Only the user-authorized date differs; frozen252/midrank function unchanged.
        records=[];effective_prefix=0
        for sid in sorted(current.sid):
            g=groups.get(sid,pd.DataFrame(columns=['trade_date','close','amount','source']))
            # Physical day-prefix before calling the unchanged frozen one().
            g=g.loc[g.trade_date<=pd.Timestamp(day)].copy()
            assert g.empty or g.trade_date.max()<=pd.Timestamp(day)
            r=BASE.one(g);r['sid']=sid;r['source_prefix_rows']=len(g);records.append(r);effective_prefix+=len(g)
        out=current.merge(liq,on=['sid','day'],how='left',validate='one_to_one').merge(pd.DataFrame(records),on=['sid','day'],how='left',validate='one_to_one')
        assert len(out)==5517 and not out.duplicated(['sid','day']).any()
        for a,b in [('current_amount_native','current_amount_passthrough'),('amount20_recomputed_native','amount20_prior_native')]:
            x=out[a].to_numpy(float);y=out[b].to_numpy(float);known=np.isfinite(x)&np.isfinite(y)
            assert np.array_equal(np.isfinite(x),np.isfinite(y))and np.array_equal(x[known].view(np.uint64),y[known].view(np.uint64))
        out=out.drop(columns='amount20_recomputed_native');out['amount_history252_percentile']=out.amount_hist252_percentile
        out['amount_hist252_unit']='VENDOR_NATIVE_AMOUNT_NO_THRESHOLD_OR_RANKING'
        out['amount_hist252_clock']='252_PRIOR_VALID_STOCK_OBSERVATIONS_NOT252_MARKET_SESSIONS'
        for name in ['historical_listing_identity','historical_ST','historical_halt','historical_limit_state','executable_eligibility']:out[name]='UNKNOWN_NOT_CERTIFIED'
        filename='AMOUNT252_'+day.replace('-','_')+'.parquet';out.to_parquet(outdir/filename,index=False,compression='zstd')
        hand=[];windows=[]
        for sid in CASES:
            g=raw_groups[sid].loc[raw_groups[sid].trade_date<=pd.Timestamp(day)].reset_index(drop=True)
            j=g.index[g.trade_date.eq(pd.Timestamp(day))].item();now=float(g.loc[j,'amount']);prior=g.loc[j-252:j-1,['trade_date','amount']];assert len(prior)==252
            assert np.isfinite(g.loc[j-252:j,'close']).all()and g.loc[j-252:j,'close'].gt(0).all()
            assert g.loc[j-252:j,'source'].nunique(dropna=False)==1
            values=[float(v)for v in prior.amount];assert all(np.isfinite(v)and v>0 for v in values)
            less=sum(v<now for v in values);equal=sum(v==now for v in values);fraction=Fraction(2*less+equal,504);med=float(median(values[-20:]))
            saved=out.loc[out.sid.eq(sid)].iloc[0]
            assert saved.amount_hist252_knownN==252 and less==saved.amount_hist252_n_less and equal==saved.amount_hist252_n_equal
            assert float(fraction)==saved.amount_hist252_percentile and med==saved.amount20_prior_native and now==saved.current_amount_native
            standard=groups[sid].loc[groups[sid].trade_date.isin(g.loc[j-252:j,'trade_date']),['trade_date','amount']].reset_index(drop=True)
            assert standard.equals(g.loc[j-252:j,['trade_date','amount']].reset_index(drop=True))
            hand.append(dict(sid=sid,day=day,current_amount_native=now,prior252_knownN=252,n_less=less,n_equal=equal,
                empirical_midrank_fraction=str(fraction),amount_history252_percentile=float(fraction),prior20_median_native=med,
                window_start=str(prior.trade_date.iloc[0].date()),window_end=str(prior.trade_date.iloc[-1].date()),raw_standardized_253_amounts_exact=True))
            windows.append(dict(sid=sid,day=day,current_amount_native=now,prior252_dates=prior.trade_date.dt.strftime('%Y-%m-%d').tolist(),prior252_amount_native=values))
        pd.DataFrame(hand).to_csv(outdir/'FOUR_RAW_HAND_CHECKS.csv',index=False);save(outdir,'FOUR_RAW_252_WINDOWS.json',windows)
        receipt=dict(status='COMPLETE_FROZEN_AMOUNT_ONLY_NO_FUTURE_PATH_OR_COHORT_SELECTION',day=day,rows=5517,
            status_counts=dict(Counter(out.amount_hist252_status)),prior20_status_counts=dict(Counter(out.amount20_status)),
            formula='(#prior<A_t+.5*#prior=A_t)/252, current excluded, full252 same valid/source block, otherwise UNKNOWN',
            effective_source_prefix_rows=effective_prefix,source_columns_read_once_for_both_dates=True,
            per_target_function_input_physically_clipped_through_day=True,new_PVR_E0_I_G1_calls=0,
            current_amount_equals_saved_PVR_exact=True,prior20_equals_saved_liquidity_exact=True,
            source_sha256=hashes,four_original_raw_handchecks=hand,output_filename=filename,output_sha256=BASE.sha(outdir/filename),
            date_elapsed_seconds=time.monotonic()-at,total_elapsed_seconds=time.monotonic()-started,
            future_price_paths_computed=0,future_based_cohort_selection=False,new_accounts=0,new_rankings_or_thresholds=0)
        save(outdir,'COMPLETION.json',receipt)
        print(json.dumps(BASE.clean(dict(day=day,status_counts=receipt['status_counts'],output_sha256=receipt['output_sha256'],
            handchecks=hand,date_seconds=receipt['date_elapsed_seconds'],total_seconds=receipt['total_elapsed_seconds'])),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
