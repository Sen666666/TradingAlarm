"""Fixed35 same-day PVR-list union, original stock E0/G1_I only, no account."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import hashlib,json,time,sys
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

HERE=Path(__file__).resolve().parent;PARENT=HERE.parent;ENTRY=HERE.parents[2]
sys.path.insert(0,str(PARENT))
import stock_signal as pure
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
LISTS=ENTRY/'local_observable_selection_v1/ranks/ALL_TOP20_LISTS.csv'
FEATURES=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
DAY='2024-09-24'


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [clean(v)for v in x]
    if isinstance(x,(pd.Timestamp,np.datetime64)):return str(pd.Timestamp(x))
    if isinstance(x,np.generic):x=x.item()
    if x is None or x is pd.NA or x is pd.NaT:return None
    return None if isinstance(x,float)and not np.isfinite(x)else x


def save(n,z):(HERE/n).write_text(json.dumps(clean(z),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def work(sid):
    started=time.monotonic()
    columns=['trade_date','open','high','low','close','volume','amount','source','adjustment_factor','raw_adjustment_factor','reference_adjustment_factor','reference_trade_date']
    g=ds.dataset(SOURCE).to_table(columns=columns,filter=(ds.field('symbol')==sid)&(ds.field('trade_date')<=pd.Timestamp(DAY))).to_pandas().sort_values('trade_date')
    assert len(g)and g.source.nunique(dropna=False)==1 and g.source.notna().all()
    frame=g.set_index('trade_date')[['open','high','low','close','volume']].copy();frame['segment_id']=0
    output=pure.calculate(frame)
    assert pd.Timestamp(DAY)in output.index,(sid,'fixed list target missing/rejected')
    r=dict(sid=sid,day=DAY,input_prefix_rows=len(g),eligible_price_observations=len(output),
           source_first_day=str(g.trade_date.iloc[0].date()),source_last_prefix_day=str(g.trade_date.iloc[-1].date()),
           signal_status='EXACT_TARGET_STOCK_SIGNAL',target_source_row_present=True)
    r.update(output.loc[pd.Timestamp(DAY)].to_dict());r['stock_hold_signal']=bool(r['i_target'])if bool(r['e0_ready'])else None
    r['stock_fresh_core_signal']=bool(r['i_target']and r['i_buy'])if bool(r['e0_ready'])else None
    current=g.iloc[-1]
    for key in ['amount','adjustment_factor','raw_adjustment_factor','reference_adjustment_factor','reference_trade_date']:r[key]=current[key]
    r['S0_eligibility_q']=None;r['S0_status']='NOT_EVALUATED_STOCK_ONLY_NO_CAP_SECTOR_OR_MARKET_GATE'
    r['compute_seconds']=time.monotonic()-started;r['reused_stopped_partial']=False
    return clean(r)


def main():
    assert not(HERE/'FIXED35_2024_09_24.parquet').exists()
    started=time.monotonic();original=json.loads((PARENT/'FULL_SIGNAL_RUN_STARTED.json').read_text())
    assert sha(SOURCE)==original['source_sha256'][str(SOURCE)]
    for path,h in original['source_sha256'].items():
        if path.endswith('.py'):assert sha(path)==h,('source/code differs, no partial reuse',path)
    lists=pd.read_csv(LISTS);lists=lists.loc[lists.day.eq(DAY)&lists.queue.eq('PVR')&lists.scope.isin(['FULL_LOCAL','OLD1709_EXACT_SUBPOOL'])]
    assert lists.scope.value_counts().to_dict()=={'FULL_LOCAL':20,'OLD1709_EXACT_SUBPOOL':20}
    symbols=sorted(set(lists.sid));assert len(symbols)==35 and not lists.duplicated(['scope','sid']).any()
    partial={}
    for path in sorted(PARENT.glob('SHARD_*_STOCK_SIGNAL.jsonl')):
        for line in path.open():
            r=json.loads(line)
            if r['sid']in symbols:
                assert r['day']==DAY and r['signal_status']=='EXACT_TARGET_STOCK_SIGNAL'
                r['reused_stopped_partial']=True;partial[r['sid']]=r
    missing=[s for s in symbols if s not in partial]
    save('SAMPLE_FREEZE.json',dict(day=DAY,symbols=symbols,rows=35,selection='FULL_LOCAL PVRtop20 union OLD1709_EXACT_SUBPOOL PVRtop20, no future labels',
        list_rows=40,intersection=5,source_sha256={str(SOURCE):sha(SOURCE),str(LISTS):sha(LISTS),str(FEATURES):sha(FEATURES)},
        algorithm_code_sha256=original['source_sha256'],reused_symbols=sorted(partial),new_symbols=missing,processes=6,
        new_parameters=0,new_accounts=0,not_global_signal_qualified_top20=True))
    with ProcessPoolExecutor(max_workers=6,mp_context=mp.get_context('spawn'))as pool:computed=list(pool.map(work,missing))
    signal=pd.DataFrame(list(partial.values())+computed)
    assert len(signal)==35 and signal.sid.nunique()==35
    features=pd.read_parquet(FEATURES);features=features.loc[features.day.eq(DAY)&features.sid.isin(symbols),['sid','day','score','E','e','E_fast','E_slow','current_close_qfq','raw_close','current_amount_passthrough']]
    assert len(features)==35
    out=signal.merge(features,on=['sid','day'],how='left',validate='one_to_one')
    assert np.array_equal(out.close.to_numpy(float).view(np.uint64),out.current_close_qfq.to_numpy(float).view(np.uint64))
    out=out.sort_values(['score','sid'],ascending=[False,True]).reset_index(drop=True)
    out['fixed35_bare_PVR_rank']=np.arange(1,len(out)+1)
    for scope in ['FULL_LOCAL','OLD1709_EXACT_SUBPOOL']:
        rows=lists.loc[lists.scope.eq(scope)].set_index('sid')
        out[scope+'_top20_member']=out.sid.isin(rows.index)
        out[scope+'_original_PVR_queue_rank']=out.sid.map(rows.queue_rank)
    for name,field in [('hold','stock_hold_signal'),('fresh','stock_fresh_core_signal')]:
        selected=out[field].eq(True);rank=pd.Series(pd.NA,index=out.index,dtype='Int64');rank.loc[selected]=np.arange(1,int(selected.sum())+1)
        out['fixed35_'+name+'_PVR_rank']=rank
    out.to_parquet(HERE/'FIXED35_2024_09_24.parquet',index=False,compression='zstd')
    out.to_csv(HERE/'FIXED35_2024_09_24.csv',index=False)
    summary=dict(status='COMPLETE_FIXED35_STOCK_ONLY_SIGNAL_EXAMPLE',day=DAY,rows=35,reused=len(partial),new_pure_signal_calculations=len(computed),
        e0_ready=int(out.e0_ready.eq(1).sum()),e0_target=int(out.e0_target.eq(1).sum()),i_target=int(out.i_target.eq(1).sum()),
        i_buy=int(out.i_buy.eq(True).sum()),hold_signal=int(out.stock_hold_signal.eq(True).sum()),fresh_core_signal=int(out.stock_fresh_core_signal.eq(True).sum()),
        by_original_scope={scope:dict(members=int(g[scope+'_top20_member'].sum()),hold_signal=int(g.loc[g[scope+'_top20_member'],'stock_hold_signal'].eq(True).sum()),fresh_signal=int(g.loc[g[scope+'_top20_member'],'stock_fresh_core_signal'].eq(True).sum()))for scope,g in [(s,out)for s in ['FULL_LOCAL','OLD1709_EXACT_SUBPOOL']]},
        output_sha256=sha(HERE/'FIXED35_2024_09_24.parquet'),source_close_bitexact_to_original_PVR_feature_export=True,
        elapsed_seconds=time.monotonic()-started,full_S0_evaluated=False,not_all_local_signal_qualified_population=True,new_accounts=0,future_labels=False)
    save('COMPLETION.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
