"""Read-only per-date raw19/PVR/queue/prior audit. No market model imports."""
from pathlib import Path
import hashlib,json,math
import numpy as np,pandas as pd

R=Path(__file__).resolve().parents[1];ROOT=R.parent;E=ROOT.parent;O=R/'independent_review';S=R/'signals';DAY=R.name
FIELDS=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']
KEY=['sid','day'];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def null(v):return v is None or v is pd.NA or v is pd.NaT or(isinstance(v,(float,np.floating))and math.isnan(float(v)))
def eq(a,b):
    if null(a)or null(b):return null(a)and null(b)
    if isinstance(a,(float,np.floating,int,np.integer))and not isinstance(a,(bool,np.bool_)):return np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64)
    return a==b
def bits(a,b):assert np.array_equal(np.asarray(a,float).view(np.uint64),np.asarray(b,float).view(np.uint64))
def main():
    assert(S/'ALL_SIGNALS.parquet').exists()and(R/'FULL5517_CANDIDATES.parquet').exists(),'Await official saved outputs; no models'
    freeze=read(S/'FREEZE.json');receipt=read(R/'ASSEMBLY_RECEIPT.json');producer=read(S/'COMPLETION.json')
    assert freeze['day']==DAY and sha(ROOT/'run_two_dates.py')==freeze['date_wrapper_sha256']
    assert sha(freeze['immutable_worker_driver_path'])==freeze['immutable_worker_driver_sha256']
    for p,h in freeze['original_algorithm_code_sha256'].items():assert sha(p)==h
    for p,h in receipt['source_sha256'].items():assert sha(p)==h
    s=pd.read_parquet(S/'ALL_SIGNALS.parquet').set_index(KEY).sort_index();x=pd.read_parquet(R/'FULL5517_CANDIDATES.parquet').set_index(KEY).sort_index()
    featurepath=E/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet';allfeatures=pd.read_parquet(featurepath)
    f=allfeatures[allfeatures.day.eq(DAY)].set_index(KEY).sort_index();assert len(s)==len(x)==len(f)==5517 and x.index.equals(s.index)and x.index.equals(f.index)and s.index.is_unique
    journal={};rows=duplicates=0;prefixes=0
    paths=[S/'REUSED_TARGETS.jsonl']+sorted((S/'controls').glob('*.jsonl'))+sorted((S/'full').glob('*.jsonl'))
    for p in paths:
        for line in p.open():
            r=json.loads(line);key=(r['sid'],r['day']);rows+=1
            if key in journal:
                duplicates+=1
                for c in FIELDS:assert eq(journal[key].get(c),r.get(c)),(key,c,'control duplicate')
            else:journal[key]=r
    assert len(journal)==5517 and set(journal)==set(s.index)
    for key,r in journal.items():
        z=s.loc[key];assert z.signal_status==r['signal_status']
        for c in FIELDS:assert eq(z.get(c),r.get(c)),(key,c,'raw journal')
        end=next((r[k]for k in ['prefix_end_day','source_last_prefix_day','actual_max_input_day','input_prefix_last']if k in r and not null(r[k])),None)
        if end is not None:assert str(end)[:10]<=DAY;prefixes+=1
        if r['signal_status']=='EXACT_TARGET_STOCK_SIGNAL':assert str(end)[:10]==DAY
    for c in f.columns:pd.testing.assert_series_equal(x[c],f[c],check_names=False)
    for c in FIELDS:pd.testing.assert_series_equal(x[c],s[c],check_names=False)
    for c in ['score','E','e','E_fast','E_slow']:bits(x[c],f[c])
    exact=s.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL');observed=int(f.target_row_present.sum());missing=5517-observed
    assert np.array_equal(exact,f.target_row_present)and s.signal_status.value_counts().to_dict()=={'EXACT_TARGET_STOCK_SIGNAL':observed,'MISSING_TARGET_BAR':missing}
    bits(x.loc[exact,'close'],f.loc[exact,'current_close_qfq'])
    assert x.full_S0_eligibility_q.isna().all()
    for c in ['historical_listing_identity','historical_ST','historical_halt','historical_limit_state','executable_eligibility','historical_publication_time']:assert x[c].eq('UNKNOWN_NOT_CERTIFIED').all()
    holdknown=exact&x.e0_ready.eq(1);buyknown=holdknown&x.g_ready.eq(True)
    assert x.loc[~holdknown,'I_hold_research'].isna().all()and x.loc[~buyknown,'i_buy_research'].isna().all()
    assert x.loc[holdknown,'I_hold_research'].tolist()==x.loc[holdknown,'i_target'].eq(1).tolist()
    assert x.loc[buyknown,'i_buy_research'].tolist()==(x.loc[buyknown,'i_target'].eq(1)&x.loc[buyknown,'i_buy'].eq(True)).tolist()
    pool=f.target_row_present.eq(True)&f.pvr_valid_observation.eq(True)&f.pvr_status.eq('KNOWN')&np.isfinite(f.score);assert np.array_equal(x.research_PVR_pool,pool)
    rankingpath=E/'local_observable_selection_v1/ranks/ALL_FIXED_DATE_RANKS.parquet';ranks=pd.read_parquet(rankingpath);old=ranks[ranks.day.eq(DAY)&ranks.scope.eq('FULL_LOCAL')].set_index(KEY).sort_index()
    for c in ['current_name','in_old1709_exact']:pd.testing.assert_series_equal(x[c],old[c],check_names=False)
    np.testing.assert_allclose(x.rank_ALL_LOCAL_PVR.to_numpy(float,na_value=np.nan),old.rank_PVR.to_numpy(float),rtol=0,atol=0,equal_nan=True)
    scopes={'ALL_LOCAL':pd.Series(True,index=x.index),'OLD1709_STATIC_REFERENCE':x.in_old1709_exact.eq(True),'OUTSIDE_OLD1709':x.in_old1709_exact.eq(False)}
    queues={'PVR':pool,'I_HOLD':pool&x.I_hold_research.eq(True).fillna(False),'I_BUY':pool&x.i_buy_research.eq(True).fillna(False)};counts=[];tops=[]
    for scope,sm in scopes.items():
        for queue,qm in queues.items():
            mask=sm&qm;column='rank_'+scope+'_'+queue;g=x[mask].reset_index().sort_values(['score','sid'],ascending=[False,True]);assert g[column].tolist()==list(range(1,len(g)+1))and x.loc[~mask,column].isna().all()
            counts.append({'scope':scope,'queue':queue,'N':len(g)});tops.extend((scope,queue,sid,j+1,len(g))for j,sid in enumerate(g.sid.head(20)))
    pd.testing.assert_frame_equal(pd.DataFrame(counts),pd.read_csv(R/'QUEUE_COUNTS.csv'))
    top=pd.read_csv(R/'TOP20_NINE_QUEUES.csv',float_precision='round_trip');assert len(top)==len(tops)and set(top[['ranking_scope','ranking_queue','sid','queue_rank','queue_N']].itertuples(index=False,name=None))==set(tops)
    for r in top.to_dict('records'):
        for c in ['score','e0_ready','e0_target','g_ready','g_grade','i_target','i_floor','i_buy','I_hold_research','i_buy_research','amount20_prior_native','amount_history252_percentile','amount_hist252_knownN']:assert eq(r[c],x.loc[(r['sid'],DAY),c]),(r['sid'],c,'top row')
    names=pd.read_csv(R/'NAMED15_SIGNAL_RANKS.csv',float_precision='round_trip',converters={'i_exit_reason':str,'g_up_reasons':str}).set_index(KEY)
    assert len(names)==15 and set(names.index.get_level_values('sid'))==set(read(R/'FREEZE.json')['named_cases'])
    for key in names.index:
        for c in FIELDS+['score','I_hold_research','i_buy_research']:
            a,b=names.loc[key,c],x.loc[key,c]
            if c in ['i_exit_reason','g_up_reasons']and a==''and null(b):continue
            assert eq(a,b),(key,c,'named CSV')
    priorpath=E/'no_future_cap_selection_v1/target_signal_completion/TARGET42.parquet';previous=pd.read_parquet(priorpath);previous=previous[previous.day.eq(DAY)].set_index(KEY)
    assert len(previous)==6
    for key in previous.index:
        for c in FIELDS:assert eq(previous.loc[key,c],s.loc[key,c]),(key,c,'prior TARGET42')
    amountpath=R/'amount_history'/('AMOUNT252_'+DAY.replace('-','_')+'.parquet');amount=pd.read_parquet(amountpath).set_index(KEY).sort_index();assert amount.index.equals(x.index)
    for c in amount.columns:
        if c.startswith('amount')or c=='current_amount_native':pd.testing.assert_series_equal(x[c],amount[c],check_names=False)
    rawcounts={'rows':5517,'exact_target_bar':observed,'missing_target_bar':missing,'E0_ready':int(holdknown.sum()),'G1_and_E0_ready':int(buyknown.sum()),'I_hold_true':int(x.I_hold_research.eq(True).sum()),'i_buy_true':int(x.i_buy_research.eq(True).sum()),'hold_unknown':int(x.I_hold_research.isna().sum()),'i_buy_unknown':int(x.i_buy_research.isna().sum()),'PVR_known':int(pool.sum()),'amount252_known':int(x.amount_history252_percentile.notna().sum())}
    for c,v in rawcounts.items():assert receipt[c]==v,(c,'receipt count')
    extra={'i_buy_true_but_PVR_unknown':int((x.i_buy_research.eq(True).fillna(False)&~pool).sum()),'I_hold_true_but_PVR_unknown':int((x.I_hold_research.eq(True).fillna(False)&~pool).sum())}
    files=[ROOT/'run_two_dates.py',R/'FREEZE.json',S/'FREEZE.json',S/'COMPLETION.json',S/'ALL_SIGNALS.parquet',R/'FULL5517_CANDIDATES.parquet',R/'ASSEMBLY_RECEIPT.json',R/'assemble_candidates.py',R/'TOP20_NINE_QUEUES.csv',R/'QUEUE_COUNTS.csv',R/'NAMED15_SIGNAL_RANKS.csv',featurepath,rankingpath,priorpath,amountpath,Path(__file__)]+paths
    result={'status':'PASS_BOUNDED_DATE_RAW5517_CANONICAL_JOIN_AND_NINE_RANKINGS','day':DAY,'remaining_blocks':[],'counts':rawcounts,'unranked_signal_counts':extra,'queue_counts':counts,'journal_rows':rows,'journal_unique':5517,'duplicate_controls':duplicates,'prefix_metadata_nonempty':prefixes,'original19_field_cells_compared':5517*19,'all_exact_close_bit_checks':observed,'top20_rows':len(top),'named_examples':15,'prior_target42_requests_checked':6,'limits':['No new model/account;all saved raw19 fields and feature/rank joins independently checked, not recursive-signal recomputation.','i_buy signal population may exceed knownPVR ranking population;unknownPVR stays separate for later prior/label audit.','Amount table field equality only;no full raw amount recalculation in this output review.','Static universe/current names/qfq vintage notPIT;legal/executable/S0/H1/sector/CP/account effects not certified.','Previous924 causal6-call gate reused as bounded same-algorithm evidence, not rerun or generalized to every new branch.'],'source_sha256':{str(p.resolve()):sha(p)for p in files},'new_model_calls':0,'new_accounts':0}
    p=O/'OUTPUT_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':result['status'],'day':DAY,'sha256':sha(p),'counts':rawcounts,'unranked_signal_counts':extra,'queues':counts},ensure_ascii=False))
if __name__=='__main__':main()
