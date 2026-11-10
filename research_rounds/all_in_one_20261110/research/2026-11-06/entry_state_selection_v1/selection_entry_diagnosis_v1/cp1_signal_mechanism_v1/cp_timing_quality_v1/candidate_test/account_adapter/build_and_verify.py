"""Prepare independent full fixed-pool receipt inputs, not another economic test."""
from pathlib import Path
import json,hashlib,sys,time,traceback
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;P=O.parent;sys.path.insert(0,str(P))
from prepare_ce import calc,COLS,CUTS,M
from ce_adapter import CELookup

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
def main():
    started=time.monotonic();assert not (O/'ADAPTER_MANIFEST.json').exists(),'Do not overwrite a built adapter.'
    original={str(p):sha(p) for p in P.iterdir() if p.is_file()};dump('ORIGINAL_TEST_FILES_BEFORE.json',original)
    sources={str(p):sha(p) for p in [M,P/'prepare_ce.py',O/'ce_adapter.py',Path(__file__)]};dump('BUILD_FREEZE.json',dict(formula_source=str(P/'prepare_ce.py'),formula_sha256=sources[str(P/'prepare_ce.py')],same_frozen_formula=True,domain='All original cached fresh CP receipts for all 1709 fixed-pool symbols; independent of any account held state',unknown='Explicit UNKNOWN and original PVR-slot fallback',ranking='Finite CE and PVR slots only; same round12/ties; no truncation or K',no_account_run=True,no_original_indicator_recalculation=True,input_sha256=sources))
    manifest=json.loads(M.read_text());assert len(manifest)==1709
    parts=[];coverage=[];prefix=[];audits=[];hashes=[]
    columns=['r','m','s','z','scale','anchor','frontier','delta_frontier','credit','displacement','receipt','reset_reason','next_anchor','next_scale','next_credit','ready','e0_valid']
    for no,x in enumerate(manifest):
        sid=x['symbol'];status=x['status'];ref=x.get('refs',{})
        if status!='complete':
            coverage.append(dict(sid=sid,source_status=status,observations=0,receipt_rows=0,CE_known=0,CE_unknown=0,first_day='',last_day='',source_reason='Original manifest: no local observation by original end'))
            continue
        cpfile=Path(ref['CP1']);ffile=Path(ref['facts']);before={str(p):sha(p) for p in [cpfile,ffile]}
        cp=pd.read_parquet(cpfile,columns=columns);f=pd.read_parquet(ffile,columns=['segment_id']);assert cp.index.equals(f.index) and cp.index.is_unique and cp.index.is_monotonic_increasing
        seg=f.segment_id.to_numpy();a,stat=calc(cp,seg,True);audits.append(dict(sid=sid,**stat));ix=np.flatnonzero(cp.receipt.to_numpy())
        z=pd.DataFrame(a[ix],columns=COLS);z.insert(0,'day',[str(d.date()) for d in cp.index[ix]]);z.insert(0,'sid',sid)
        z['source_displacement']=cp.displacement.to_numpy()[ix];z['source_credit']=cp.credit.to_numpy()[ix];z['source_r']=cp.r.to_numpy()[ix];z['source_m']=cp.m.to_numpy()[ix]
        z['source_receipt']=True;z['formation_anchor_day']=[str(cp.index[int(j)].date()) if j>=0 else '' for j in z.anchor_index];z['CE_known']=np.isfinite(z.CE);parts.append(z)
        coverage.append(dict(sid=sid,source_status=status,observations=len(cp),receipt_rows=len(z),CE_known=int(z.CE_known.sum()),CE_unknown=int((~z.CE_known).sum()),first_day=str(cp.index[0].date()) if len(cp) else '',last_day=str(cp.index[-1].date()) if len(cp) else '',source_reason=''))
        for cut in CUTS:
            stop=int(cp.index.searchsorted(pd.Timestamp(cut),side='right'));small,_=calc(cp.iloc[:stop],seg[:stop]) if stop else (a[:0],{})
            assert np.array_equal(a[:stop],small,equal_nan=True),(sid,cut,'prefix')
            prefix.append(dict(sid=sid,cutoff=cut,prefix_observations=stop,full_observations=len(cp),all_state_columns_exact=True))
        for path,h in before.items():
            assert sha(path)==h;expected=x.get('output_sha256',{}).get(path);assert expected is None or expected==h
            hashes.append(dict(sid=sid,path=path,sha256=h,manifest_expected=expected,unchanged=True))
        if (no+1)%300==0:print('ADAPTER_STOCKS',no+1,'seconds',round(time.monotonic()-started,1),flush=True)
    scores=pd.concat(parts,ignore_index=True);assert not scores.duplicated(['sid','day']).any()
    scores.to_parquet(O/'ALL_NATIVE_CP_RECEIPT_CE.parquet',index=False);stock=pd.DataFrame(coverage);stock.to_csv(O/'STOCK_COVERAGE.csv',index=False);stock[stock.source_status!='complete'].to_csv(O/'EXPLICIT_UNAVAILABLE_STOCKS.csv',index=False);pd.DataFrame(prefix).to_csv(O/'PREFIX_CHECKS.csv',index=False);pd.DataFrame(hashes).to_csv(O/'CACHE_SOURCE_HASHES.csv',index=False);dump('FULL_SOURCE_CLOCK_AUDIT.json',audits)
    dump('ADAPTER_MANIFEST.json',dict(status='BUILT_PENDING_INTERFACE_AUDIT',fixed_pool_symbols=1709,complete_source_symbols=int(stock.source_status.eq('complete').sum()),unavailable_source_symbols=int(stock.source_status.ne('complete').sum()),native_receipt_rows=len(scores),CE_known=int(scores.CE_known.sum()),CE_unknown=int((~scores.CE_known).sum()),artifact_sha256={n:sha(O/n) for n in ['ce_adapter.py','ALL_NATIVE_CP_RECEIPT_CE.parquet','STOCK_COVERAGE.csv']},frozen_formula_sha256=sha(P/'prepare_ce.py'),input_manifest_sha256=sha(M),source_hash_table_sha256=sha(O/'CACHE_SOURCE_HASHES.csv'),no_K=True,no_account_state_dependency=True))
    # Exact score comparison to all old original account-specific candidate rows.
    old=pd.read_parquet(P/'CANDIDATE_CE.parquet');joined=old[['account','sid','day']+COLS].merge(scores[['sid','day']+COLS],on=['sid','day'],how='left',suffixes=('_old','_adapter'),validate='many_to_one')
    assert len(joined)==103766
    for col in COLS:assert np.array_equal(joined[col+'_old'].to_numpy(),joined[col+'_adapter'].to_numpy(),equal_nan=True),col
    loader=CELookup();assert len(loader.stocks)==1709
    # Interface scores and all queues must reproduce the previous sealed complete order.
    moves=pd.read_parquet(P/'FULL_QUEUE_ORDERS.parquet');expected={(a,d):g.sort_values('CE_rank').sid.tolist() for (a,d),g in moves.groupby(['account','day'])};fixedslots=0
    for (account,day),g in old.groupby(['account','day']):
        ranked=loader.rank_frame(g);assert ranked.sid.tolist()==expected[(account,day)];assert len(ranked)==len(g)
        assert np.array_equal(ranked.CE.to_numpy(),g.set_index('sid').loc[ranked.sid].CE.to_numpy(),equal_nan=True)
        fixed=ranked[~ranked.CE_slot_replaceable];fixedslots+=len(fixed);assert fixed.CE_rank.eq(fixed.CE_original_slot).all()
    # Explicit unknowns never delete or move the original slot, including missing-source/day/outside-pool.
    missing_sid=stock[stock.source_status!='complete'].sid.iloc[0];assert not loader.query(missing_sid,'2022-01-04')['CE_known'];assert not loader.query('NOT_IN_POOL','2022-01-04')['CE_known'];assert not loader.query('600056.SH','1900-01-01')['CE_known']
    fixture=pd.DataFrame([dict(sid='600056.SH',day='2022-03-03',original_PVR=80.,original_priority_rank=3.),dict(sid=missing_sid,day='2022-03-03',original_PVR=90.,original_priority_rank=2.),dict(sid='600299.SH',day='2022-03-03',original_PVR=np.nan,original_priority_rank=1.)]);rr=loader.rank_frame(fixture);assert rr.sid.tolist()==['600299.SH',missing_sid,'600056.SH'] and len(rr)==3
    originalkeys=pd.MultiIndex.from_frame(old[['sid','day']].drop_duplicates());extra=~pd.MultiIndex.from_frame(scores[['sid','day']]).isin(originalkeys)
    for p,h in original.items():assert sha(p)==h,(p,'old sealed test changed')
    for p,h in sources.items():assert sha(p)==h,(p,'source changed')
    check=dict(status='READY_READ_ONLY_FULL_FIXED_POOL_CE_ADAPTER',fixed_pool_symbols=1709,source_complete_symbols=1687,source_unavailable_symbols=22,original_source_observations=int(stock.observations.sum()),native_receipt_rows=len(scores),CE_known=int(scores.CE_known.sum()),CE_unknown=int((~scores.CE_known).sum()),additional_receipt_keys_outside_original_candidate_domain=int(extra.sum()),old_candidate_rows_exact=103766,old_unique_stock_days_exact=54852,old_full_queues_exact=len(expected),original_PVR_unknown_slots_exact=fixedslots,full_prefix_checks=len(prefix),all_state_columns_prefix_exact=True,source_hashes_unchanged=True,all_old_test_artifacts_unchanged=True,explicit_unknown_cases_verified=True,no_top_K_or_truncation=True,no_account_state_dependency=True,no_original_indicator_recalculation=True,account_runs=0,seconds=time.monotonic()-started)
    dump('ADAPTER_AUDIT.json',check)
    mm=json.loads((O/'ADAPTER_MANIFEST.json').read_text());mm['status']='READY_READ_ONLY_FULL_FIXED_POOL_CE_ADAPTER';mm['audit_sha256']=sha(O/'ADAPTER_AUDIT.json');dump('ADAPTER_MANIFEST.json',mm)
    print(json.dumps(check,ensure_ascii=False),flush=True)
if __name__=='__main__':
    try:main()
    except Exception:(O/('TECHNICAL_FAILURE_'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc());raise
