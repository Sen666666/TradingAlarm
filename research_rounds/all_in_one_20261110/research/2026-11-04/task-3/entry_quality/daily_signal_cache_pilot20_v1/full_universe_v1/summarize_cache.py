"""After generation: saved-cache coverage, fixed-date query checks, no models."""
from pathlib import Path
import datetime,hashlib,json,time
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

B=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    complete=json.loads((B/'GENERATION_COMPLETION.json').read_text())
    assert complete['status']=='COMPLETE_GENERATION_PENDING_INDEPENDENT_AUDIT'and complete['done']==5517 and not complete['unknown']and not complete['errors']
    freeze=json.loads((B/'FREEZE.json').read_text());receipts=[];files=[]
    for p in sorted((B/'receipts').glob('*.json')):
        r=json.loads(p.read_text());assert r['status']=='DONE_VALIDATED'and r['cache_identity']==freeze['cache_identity']
        path=B/r['file'];assert sha(path)==r['file_sha256'];files.append(str(path));receipts.append(r)
    assert len(files)==5517 and len({r['sid']for r in receipts})==5517
    dataset=ds.dataset(files,format='parquet')
    columns=['day','source_row_present','stock_eligible_price_observation','native__e0_ready','native__g_ready','native__i_target','native__i_buy','cp__ready','cp__receipt','cp__input_status','pvr__score']
    annual={};rows=0;started=time.perf_counter()
    for batch in dataset.scanner(columns=columns,batch_size=32768).to_batches():
        a=batch.to_pandas();years=a.day.dt.year
        for year,g in a.groupby(years):
            e0=g.native__e0_ready.eq(1)&g.stock_eligible_price_observation
            fresh=e0&g.native__g_ready.eq(True)
            values=dict(grid_rows=len(g),source_present=int(g.source_row_present.sum()),source_missing=int((~g.source_row_present).sum()),
                eligible_price_rows=int(g.stock_eligible_price_observation.sum()),E0_known_rows=int(e0.sum()),fresh_known_rows=int(fresh.sum()),
                I_hold_true_stockdays=int((e0&g.native__i_target.eq(1)).sum()),i_buy_true_stockdays=int((fresh&g.native__i_target.eq(1)&g.native__i_buy.eq(True)).sum()),
                PVR_known_rows=int(np.isfinite(g.pvr__score).sum()),CP_scale_ready_rows=int(g.cp__ready.eq(True).sum()),CP_market_receipts=int(g.cp__receipt.eq(True).sum()),CP_blocked_rows=int(g.cp__input_status.eq('BLOCKED_BY_PRIOR_INVALID_INPUT').sum()))
            r=annual.setdefault(int(year),{k:0 for k in values})
            for k,v in values.items():r[k]+=v
        rows+=len(a)
    assert rows==5814918 and sum(v['source_present']for v in annual.values())==5424843
    summary=pd.DataFrame([dict(year=y,**r)for y,r in sorted(annual.items())]);summary.to_csv(B/'ANNUAL_SIGNAL_COVERAGE.csv',index=False)
    queries=[]
    qcols=['sid','day','source_row_present','native__e0_ready','native__g_ready','native__i_target','native__i_buy','pvr__score']
    for day,expected,rankable in [('2022-01-24',177,175),('2024-09-24',2313,2313),('2026-01-15',779,779)]:
        tick=time.perf_counter();a=dataset.to_table(columns=qcols,filter=ds.field('day')==pa.scalar(pd.Timestamp(day))).to_pandas()
        assert len(a)==5517 and a.sid.nunique()==5517
        known=a.native__e0_ready.eq(1)&a.native__g_ready.eq(True)
        member=known&a.native__i_target.eq(1)&a.native__i_buy.eq(True)
        N=int(member.sum());scored=int((member&np.isfinite(a.pvr__score)).sum())
        assert N==expected and scored==rankable
        queries.append(dict(day=day,cache_rows=len(a),source_present=int(a.source_row_present.sum()),i_buy=N,score_known=scored,query_wall_seconds=time.perf_counter()-tick,new_model_calls=0))
    save(B/'READONLY_FIXED_DATE_QUERY_CHECKS.json',dict(status='PASS_READ_CACHE_ONLY_SAME_ORIGINAL_COHORTS',queries=queries,not_new_signal_execution=True))
    totals={k:sum(v[k]for v in annual.values())for k in next(iter(annual.values()))}
    old19={};oldp={}
    for r in receipts:
        for q in r['details']['checks']['old19']:old19[q['status']]=old19.get(q['status'],0)+1
        for q in r['details']['checks']['oldPVR']:oldp[q['status']]=oldp.get(q['status'],0)+1
    cpus={};new_cpus={};input_rows=0
    for r in receipts:
        profile=r['details']['profile'];input_rows+=profile['input_rows']
        for k,v in profile['component_CPU_seconds'].items():
            cpus[k]=cpus.get(k,0.)+v
            if r['origin']=='NEW_SINGLE_PREFIX_KERNEL':new_cpus[k]=new_cpus.get(k,0.)+v
    assert input_rows==15739264
    manifest=dict(status='ALL5517_GENERATED_VALIDATED_PENDING_FINAL_INDEPENDENT_SIGNOFF',cache_identity=freeze['cache_identity'],
        source_sha256=freeze['source_sha256'],date_start=freeze['start'],date_end=freeze['actual_end'],H1_complete=False,rows=rows,columns=len(freeze['schema_columns']),
        files={r['file']:r['file_sha256']for r in receipts},file_count=5517,artifact_bytes=sum(r['file_bytes']for r in receipts),
        schema_file='DAILY_SCHEMA.arrow',schema_sha256=sha(B/'DAILY_SCHEMA.arrow'),source_grid_is_not_certified_exchange_calendar=True,
        no_account_or_execution_claim=True,source_status_and_corporate_actions_nonPIT=True)
    save(B/'CACHE_DATASET.json',manifest)
    result=dict(status='COMPLETE_SAVED_CACHE_COVERAGE_AND_QUERY_SUMMARY',totals=totals,old19_request_counts=old19,oldPVR_request_counts=oldp,
        full_input_rows=input_rows,all_output_component_CPU_reference_including_reused20=cpus,new5497_component_CPU_core_seconds=new_cpus,generation_elapsed_seconds=complete['elapsed_seconds'],
        summary_and_three_queries_wall_seconds=time.perf_counter()-started,artifact_bytes=manifest['artifact_bytes'],file_count=5517,
        origin_counts={k:sum(r['origin']==k for r in receipts)for k in sorted({r['origin']for r in receipts})},
        no_accounts=True,no_model_calls_in_this_script=True)
    save(B/'SUMMARY_RECEIPT.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
