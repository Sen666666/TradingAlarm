"""One-date stock-only signal/PVR/liquidity joins, no account or models."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ENTRY=HERE.parents[1]
DAY='2026-01-15'
SIGNALS=HERE/'signals/ALL_SIGNALS.parquet'
FEATURES=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
RANKS=ENTRY/'local_observable_selection_v1/ranks/ALL_FIXED_DATE_RANKS.parquet'
AMOUNT=HERE/'amount_history/AMOUNT252_2026_01_15.parquet'
NAMES=json.loads((HERE/'FREEZE.json').read_text())['named_cases']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rank(out,mask,column):
    result=pd.Series(pd.NA,index=out.index,dtype='Int64')
    ix=out.loc[mask].sort_values(['score','sid'],ascending=[False,True]).index
    result.loc[ix]=np.arange(1,len(ix)+1);out[column]=result
    return len(ix)


def main():
    assert not(HERE/'FULL5517_CANDIDATES.parquet').exists()
    s=pd.read_parquet(SIGNALS)
    if 'status'in s and'signal_status'not in s:s=s.rename(columns={'status':'signal_status'})
    assert len(s)==5517 and s.sid.nunique()==5517 and s.day.eq(DAY).all()
    # Whitelist signals/provenance: reused35 also carry sparse legacy score columns.
    # Those are never a substitute for the complete frozen canonical PVR export.
    model_fields=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited',
        'i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason',
        'g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons',
        'numeric_event','numeric_leg_direction','close']
    provenance=['sid','day','signal_status','target_source_row_present','prefix_end_day',
        'input_prefix_rows','input_prefix_first','algorithm_binding','full_S0_eligibility_q',
        'model_invoked','model_seconds','model_cpu_seconds','eligible_price_observations',
        'reuse_source','reuse_kind']
    keep=list(dict.fromkeys(provenance+model_fields+[n for n in s if n.startswith('source_')]))
    s=s[[n for n in keep if n in s]]
    f=pd.read_parquet(FEATURES);f=f.loc[f.day.eq(DAY)].copy()
    assert len(f)==5517
    # Original features retain source/reference clock information. No cap join.
    x=f.merge(s,on=['sid','day'],how='left',validate='one_to_one',suffixes=('','_stock_signal'))
    annotations=pd.read_parquet(RANKS,columns=['sid','day','scope','current_name','in_old1709_exact'])
    annotations=annotations.loc[annotations.day.eq(DAY)&annotations.scope.eq('FULL_LOCAL')].drop(columns='scope')
    x=x.merge(annotations,on=['sid','day'],validate='one_to_one')
    a=pd.read_parquet(AMOUNT)
    fields=['sid','day']+[n for n in a if n.startswith('amount') or n=='current_amount_native']
    x=x.merge(a[fields],on=['sid','day'],validate='one_to_one')
    assert len(x)==5517 and not x.duplicated(['sid','day']).any()
    exact=x.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL')
    assert exact.sum()==x.target_row_present.sum(), 'present rows not completely modeled; inspect status'
    assert np.array_equal(x.loc[exact,'close'].to_numpy(float).view(np.uint64),x.loc[exact,'current_close_qfq'].to_numpy(float).view(np.uint64))
    x['research_PVR_pool']=(x.target_row_present.eq(True)&x.pvr_valid_observation.eq(True)&x.pvr_status.eq('KNOWN')&np.isfinite(x.score))
    x['I_hold_research']=pd.Series(pd.NA,index=x.index,dtype='boolean')
    x['i_buy_research']=pd.Series(pd.NA,index=x.index,dtype='boolean')
    hold_known=exact&x.e0_ready.eq(1)
    buy_known=hold_known&x.g_ready.eq(True)
    x.loc[hold_known,'I_hold_research']=x.loc[hold_known,'i_target'].eq(1)
    x.loc[buy_known,'i_buy_research']=x.loc[buy_known,'i_target'].eq(1)&x.loc[buy_known,'i_buy'].eq(True)
    x['hold_signal_interpretation']=np.where(hold_known,'KNOWN_ORIGINAL_STOCK_STATE','UNKNOWN_MISSING_ERROR_OR_NOT_READY')
    x['i_buy_interpretation']=np.where(buy_known,'KNOWN_ORIGINAL_CURRENT_OPPORTUNITY','UNKNOWN_MISSING_ERROR_OR_E0_G1_NOT_READY')
    x['historical_listing_identity']='UNKNOWN_NOT_CERTIFIED'
    for n in ['historical_ST','historical_halt','historical_limit_state','executable_eligibility']:
        x[n]='UNKNOWN_NOT_CERTIFIED'
    x['market_data_status']=np.where(x.target_row_present,'EXACT_LOCAL_BAR_NOT_TRADABILITY_PROOF','MISSING_TARGET_BAR_NOT_STATUS_INFERENCE')
    x['price_cutoff_day']=DAY
    x['historical_publication_time']='UNKNOWN_NOT_CERTIFIED'
    summary=[];top=[]
    scopes={'ALL_LOCAL':pd.Series(True,index=x.index),'OLD1709_STATIC_REFERENCE':x.in_old1709_exact.eq(True),'OUTSIDE_OLD1709':x.in_old1709_exact.eq(False)}
    queues={'PVR':x.research_PVR_pool,'I_HOLD':x.research_PVR_pool&x.I_hold_research.eq(True).fillna(False),'I_BUY':x.research_PVR_pool&x.i_buy_research.eq(True).fillna(False)}
    for scope,scope_mask in scopes.items():
        for queue,queue_mask in queues.items():
            column=f'rank_{scope}_{queue}';n=rank(x,scope_mask&queue_mask,column)
            summary.append(dict(scope=scope,queue=queue,N=n))
            z=x.loc[x[column].le(20).fillna(False)].sort_values(column).copy()
            z['ranking_scope']=scope;z['ranking_queue']=queue;z['queue_rank']=z[column];z['queue_N']=n;top.append(z)
    # Verify bare ranks against the already audited same-coordinate original export.
    old=pd.read_parquet(RANKS,columns=['sid','day','scope','rank_PVR'])
    old=old.loc[old.day.eq(DAY)&old.scope.eq('FULL_LOCAL')].set_index('sid')
    z=x.set_index('sid');assert z.rank_ALL_LOCAL_PVR.astype('Float64').equals(old.loc[z.index,'rank_PVR'].astype('Float64'))
    x=x.sort_values(['rank_ALL_LOCAL_PVR','sid'],na_position='last').reset_index(drop=True)
    x.to_parquet(HERE/'FULL5517_CANDIDATES.parquet',index=False,compression='zstd')
    x.to_csv(HERE/'FULL5517_CANDIDATES.csv',index=False)
    topcols=['ranking_scope','ranking_queue','queue_rank','queue_N','sid','day','current_name',
             'score','rank_ALL_LOCAL_PVR','e0_ready','e0_target','g_ready','g_grade',
             'i_target','i_floor','i_buy','I_hold_research','i_buy_research',
             'amount20_prior_native','amount_history252_percentile','amount_hist252_knownN',
             'historical_listing_identity','historical_ST','historical_halt',
             'historical_limit_state','executable_eligibility']
    pd.concat(top,ignore_index=True)[topcols].to_csv(HERE/'TOP20_NINE_QUEUES.csv',index=False)
    pd.DataFrame(summary).to_csv(HERE/'QUEUE_COUNTS.csv',index=False)
    named=x.loc[x.sid.isin(NAMES)].copy();assert len(named)==15
    named.to_csv(HERE/'NAMED15_SIGNAL_RANKS.csv',index=False)
    counts=dict(rows=5517,day=DAY,exact_target_bar=int(x.target_row_present.sum()),missing_target_bar=int((~x.target_row_present).sum()),
        signal_status=x.signal_status.value_counts().to_dict(),E0_ready=int(hold_known.sum()),G1_and_E0_ready=int(buy_known.sum()),
        I_hold_true=int(x.I_hold_research.eq(True).sum()),i_buy_true=int(x.i_buy_research.eq(True).sum()),
        hold_unknown=int(x.I_hold_research.isna().sum()),i_buy_unknown=int(x.i_buy_research.isna().sum()),
        PVR_known=int(x.research_PVR_pool.sum()),amount252_known=int(x.amount_history252_percentile.notna().sum()),
        full_S0_evaluated=False,certified_executable_eligibility=0,queues=summary,
        new_account_runs=0,network_calls=0,new_model_calls_in_assembly=0,
        source_sha256={str(p):sha(p)for p in [SIGNALS,FEATURES,RANKS,AMOUNT,HERE/'FREEZE.json',Path(__file__).resolve()]})
    (HERE/'ASSEMBLY_RECEIPT.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(counts,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
