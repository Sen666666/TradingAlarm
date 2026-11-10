"""Read-only full saved signal/feature join/rank audit. Never imports models."""
from pathlib import Path
import json,hashlib,math
import numpy as np,pandas as pd

R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;E=R.parent;S=R/'signals';DAY='2024-09-24'
FIELDS=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']
KEY=['sid','day'];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def isnull(x):return x is None or x is pd.NA or x is pd.NaT or(isinstance(x,(float,np.floating))and math.isnan(float(x)))
def eq(a,b):
    if isnull(a)or isnull(b):return isnull(a)and isnull(b)
    if isinstance(a,(float,np.floating,int,np.integer))and not isinstance(a,(bool,np.bool_)):
        return np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64)
    return a==b
def bits(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float);assert np.array_equal(a.view(np.uint64),b.view(np.uint64))
def main():
    needed=[S/'ALL_SIGNALS.parquet',R/'FULL5517_CANDIDATES.parquet',R/'ASSEMBLY_RECEIPT.json']
    assert all(p.exists()for p in needed),'Wait for final saved outputs; do not run models'
    freeze=read(S/'FREEZE.json');rootfreeze=read(R/'FREEZE.json');receipt=read(R/'ASSEMBLY_RECEIPT.json')
    assert sha(S/'run_signals.py')==freeze['driver_sha256']
    for p,h in freeze['original_algorithm_code_sha256'].items():assert sha(p)==h,(p,'original code')
    for p,h in receipt['source_sha256'].items():assert sha(p)==h,(p,'assembly source')
    s=pd.read_parquet(S/'ALL_SIGNALS.parquet').set_index(KEY).sort_index()
    x=pd.read_parquet(R/'FULL5517_CANDIDATES.parquet').set_index(KEY).sort_index()
    featurespath=E/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
    f=pd.read_parquet(featurespath);f=f[f.day.eq(DAY)].set_index(KEY).sort_index()
    ranks=pd.read_parquet(E/'local_observable_selection_v1/ranks/ALL_FIXED_DATE_RANKS.parquet')
    assert len(s)==len(x)==len(f)==5517 and s.index.is_unique and x.index.equals(s.index)and x.index.equals(f.index)
    assert set(x.index.get_level_values('day'))=={DAY}
    # Complete raw journals are independent of the assembly; controls may duplicate.
    paths=[S/'REUSED110.jsonl']+sorted((S/'pilot').glob('*.jsonl'))+sorted((S/'full').glob('*.jsonl'))
    journal={};duplicates=0;journal_rows=0
    for p in paths:
        for line in p.open():
            r=json.loads(line);key=(r['sid'],r['day']);journal_rows+=1
            if key in journal:
                duplicates+=1
                for c in FIELDS:assert eq(journal[key].get(c),r.get(c)),(key,c,'duplicate control')
            else:journal[key]=r
    assert len(journal)==5517 and set(journal)==set(s.index)
    prefixes=0
    for key,r in journal.items():
        saved=s.loc[key]
        assert saved.signal_status==r['signal_status'],(key,'status')
        for c in FIELDS:assert eq(saved.get(c),r.get(c)),(key,c,'raw saved vs journal')
        endpoint=next((r[k]for k in ['prefix_end_day','source_last_prefix_day','actual_max_input_day','input_prefix_last']if k in r and not isnull(r[k])),None)
        if endpoint is not None:
            assert str(endpoint)[:10]<=DAY,(key,'future input metadata');prefixes+=1
        if r['signal_status']=='EXACT_TARGET_STOCK_SIGNAL':assert str(endpoint)[:10]==DAY,(key,'exact prefix')
    for col in f.columns:
        pd.testing.assert_series_equal(x[col],f[col],check_names=False)
    for col in FIELDS:pd.testing.assert_series_equal(x[col],s[col],check_names=False)
    for col in ['score','E','e','E_fast','E_slow']:bits(x[col],f[col])
    exact=s.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL');assert exact.sum()==5309
    assert s.signal_status.value_counts().to_dict()=={'EXACT_TARGET_STOCK_SIGNAL':5309,'MISSING_TARGET_BAR':208}
    assert np.array_equal(exact.to_numpy(),f.target_row_present.to_numpy())
    bits(x.loc[exact,'close'],f.loc[exact,'current_close_qfq'])
    assert x.full_S0_eligibility_q.isna().all()
    for c in ['historical_listing_identity','historical_ST','historical_halt','historical_limit_state','executable_eligibility','historical_publication_time']:assert x[c].eq('UNKNOWN_NOT_CERTIFIED').all()
    holdknown=exact&x.e0_ready.eq(1);buyknown=holdknown&x.g_ready.eq(True)
    assert x.loc[~holdknown,'I_hold_research'].isna().all()and x.loc[~buyknown,'i_buy_research'].isna().all()
    assert x.loc[holdknown,'I_hold_research'].tolist()==x.loc[holdknown,'i_target'].eq(1).tolist()
    assert x.loc[buyknown,'i_buy_research'].tolist()==(x.loc[buyknown,'i_target'].eq(1)&x.loc[buyknown,'i_buy'].eq(True)).tolist()
    expectedpool=f.target_row_present.eq(True)&f.pvr_valid_observation.eq(True)&f.pvr_status.eq('KNOWN')&np.isfinite(f.score)
    assert x.research_PVR_pool.equals(expectedpool.rename('research_PVR_pool'))and expectedpool.sum()==5281
    old=ranks[ranks.day.eq(DAY)&ranks.scope.eq('FULL_LOCAL')].set_index(KEY).sort_index()
    pd.testing.assert_series_equal(x.in_old1709_exact,old.in_old1709_exact,check_names=False)
    pd.testing.assert_series_equal(x.current_name,old.current_name,check_names=False)
    scopes={'ALL_LOCAL':pd.Series(True,index=x.index),'OLD1709_STATIC_REFERENCE':x.in_old1709_exact.eq(True),'OUTSIDE_OLD1709':x.in_old1709_exact.eq(False)}
    queues={'PVR':expectedpool,'I_HOLD':expectedpool&x.I_hold_research.eq(True).fillna(False),'I_BUY':expectedpool&x.i_buy_research.eq(True).fillna(False)}
    expectedtops=[];counts=[]
    for scope,scope_mask in scopes.items():
        for queue,queue_mask in queues.items():
            name='rank_'+scope+'_'+queue;mask=scope_mask&queue_mask
            selected=x[mask].reset_index().sort_values(['score','sid'],ascending=[False,True])
            assert selected[name].tolist()==list(range(1,len(selected)+1)),name
            assert x.loc[~mask,name].isna().all()
            counts.append({'scope':scope,'queue':queue,'N':len(selected)})
            expectedtops.extend((scope,queue,sid,i+1,len(selected))for i,sid in enumerate(selected.sid.head(20)))
    cq=pd.read_csv(R/'QUEUE_COUNTS.csv');pd.testing.assert_frame_equal(pd.DataFrame(counts),cq)
    top=pd.read_csv(R/'TOP20_NINE_QUEUES.csv',float_precision='round_trip')
    assert len(top)==180 and set(top[['ranking_scope','ranking_queue','sid','queue_rank','queue_N']].itertuples(index=False,name=None))==set(expectedtops)
    for r in top.to_dict('records'):
        for c in ['score','e0_ready','e0_target','g_ready','g_grade','i_target','i_floor','i_buy','I_hold_research','i_buy_research','amount20_prior_native','amount_history252_percentile','amount_hist252_knownN']:
            assert eq(r[c],x.loc[(r['sid'],DAY),c]),(r['sid'],r['ranking_queue'],c,'top data')
    # Empty native reason/reasons are genuine empty strings, not missing floats.
    named=pd.read_csv(R/'NAMED15_SIGNAL_RANKS.csv',float_precision='round_trip',converters={'i_exit_reason':str,'g_up_reasons':str}).set_index(KEY).sort_index()
    assert len(named)==15 and set(named.index.get_level_values('sid'))==set(rootfreeze['named_cases'])
    for c in FIELDS+['score','I_hold_research','i_buy_research']:
        for key in named.index:assert eq(named.loc[key,c],x.loc[key,c]),(key,c,'named')
    priorpath=E/'no_future_cap_selection_v1/target_signal_completion/TARGET42.parquet'
    prior=pd.read_parquet(priorpath);prior=prior[prior.day.eq(DAY)].set_index(KEY)
    for key in prior.index:
        for c in FIELDS:assert eq(prior.loc[key,c],s.loc[key,c]),(key,c,'prior6')
    fixedpath=E/'selection_qualification_closeout_v1/eligibility_source/fixed35/FIXED35_2024_09_24.parquet'
    fixed=pd.read_parquet(fixedpath).set_index(KEY)
    for key in fixed.index:
        for c in FIELDS:assert eq(fixed.loc[key,c],s.loc[key,c]),(key,c,'prior35')
    amountpath=R/'amount_history/AMOUNT252_2024_09_24.parquet'
    amount=pd.read_parquet(amountpath).set_index(KEY).sort_index()
    assert amount.index.equals(x.index)
    for c in amount.columns:
        if c.startswith('amount')or c=='current_amount_native':pd.testing.assert_series_equal(x[c],amount[c],check_names=False)
    independent_counts={'rows':5517,'exact_target_bar':5309,'missing_target_bar':208,'E0_ready':int(holdknown.sum()),'G1_and_E0_ready':int(buyknown.sum()),'I_hold_true':int(x.I_hold_research.eq(True).sum()),'i_buy_true':int(x.i_buy_research.eq(True).sum()),'hold_unknown':int(x.I_hold_research.isna().sum()),'i_buy_unknown':int(x.i_buy_research.isna().sum()),'PVR_known':5281,'amount252_known':int(x.amount_history252_percentile.notna().sum())}
    for k,v in independent_counts.items():assert receipt[k]==v,(k,'receipt count')
    files=[S/'ALL_SIGNALS.parquet',S/'FREEZE.json',S/'run_signals.py',R/'FULL5517_CANDIDATES.parquet',R/'ASSEMBLY_RECEIPT.json',R/'assemble_candidates.py',R/'FREEZE.json',R/'TOP20_NINE_QUEUES.csv',R/'QUEUE_COUNTS.csv',R/'NAMED15_SIGNAL_RANKS.csv',amountpath,featurespath,priorpath,fixedpath,O/'SOURCE_PREFIX_GATE.json',Path(__file__)]+paths
    result={'status':'PASS_BOUNDED_FULL5517_SAVED_SIGNALS_JOIN_AND_NINE_RANKINGS','remaining_blocks':[],'counts':independent_counts,'queue_counts':counts,'journal_rows':journal_rows,'journal_unique_stock_dates':5517,'duplicate_control_rows_checked':duplicates,'saved_prefix_metadata_rows_checked':prefixes,'all19_original_signal_cells_compared':5517*19,'all_target_close_finite_bit_checks':5309,'top20_rows_nine_queues':180,'named_examples':15,'scope':['All saved journal original19 fields compared to ALL_SIGNALS, then root table, without rerunning recursive model.','All5517 original feature columns, including complete frozen PVR/E/e/FAST/SLOW, compared without sparse reused-score substitution.','All9 score/sid rankings and top20 source fields independently checked; 208missing and ready/gready masks preserve UNKNOWN.','Saved35 and6 prior target signals checked at all19 original fields.','Amount owner table joined field-exactly; its full252 computations are bound, not independently rerun here.'],'limits':['This audit is saved-output/source-clock/ranking verification, not an independent full-model recomputation. Separate3-stock6-call prefix gate remains bounded.','No fullS0/H1/sector/CP/market/legal/realexecution certification. i_buy is a current stock opportunity and may repeat inside an existing structure, not first trade.','Static5517 universe, current names/old1709 annotation, qfq vintages and historical price publication are not PIT;239retired archives remain separate.','No account, money/quantity, forward-return label, new model or parameter search in this output audit.'],'source_sha256':{str(p.resolve()):sha(p)for p in files},'new_model_calls':0,'new_accounts':0}
    result['audit_technical_note']='Initial read-only audit reached named CSV after passing all raw fields/ranks, then stopped because default read_csv converted native empty i_exit_reason to NaN. The audit now preserves the two native text columns with converters=str; no producer, table, model or numeric tolerance changed.'
    p=O/'OUTPUT_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'sha256':sha(p),'counts':independent_counts,'queue_counts':counts},ensure_ascii=False))
if __name__=='__main__':main()
