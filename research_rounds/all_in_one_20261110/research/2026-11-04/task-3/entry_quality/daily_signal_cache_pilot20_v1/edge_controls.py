"""At most8 observed signal/input branches; no return/outcome selection."""
import json,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import pandas as pd
import numpy as np
import pyarrow.dataset as ds
import pilot as p

B=Path(__file__).resolve().parent

def check(item):
    sid,day=item['sid'],item['day']
    g=ds.dataset(p.SOURCE).to_table(columns=p.COLS,filter=ds.field('symbol').isin([sid])&(ds.field('trade_date')<=pd.Timestamp(day))).to_pandas().sort_values('trade_date')
    out,profile=p.kernel(g)
    reference=pd.read_parquet(B/'full'/sid/'BASELINE_FULL_HISTORY.parquet').loc[:day]
    cells=p.compare_frames(out,reference,f'edge {item["branch"]} {sid} {day}')
    return dict(**item,status='PASS_ALL_COMMON_PREFIX_FIELDS',rows=len(out),columns=len(out.columns),exact_cells=cells,profile=profile,physical_input_max=str(g.trade_date.max().date()))

def main():
    f=p.validate();allrows=[]
    for sid in f['stocks']:
        x=pd.read_parquet(B/'full'/sid/'BASELINE_FULL_HISTORY.parquet')
        x=x.loc[x.index>=pd.Timestamp(p.START)].copy();x['sid']=sid;x['day']=x.index
        x['cold_to_warm']=x.native__g_grade.ge(2)&x.native__g_grade.shift().lt(2)
        allrows.append(x)
    a=pd.concat(allrows).sort_values(['day','sid'])
    raw=ds.dataset(p.SOURCE).to_table(columns=p.COLS,filter=ds.field('symbol').isin(f['stocks'])&(ds.field('trade_date')>=pd.Timestamp(p.START))&(ds.field('trade_date')<=pd.Timestamp(p.END))).to_pandas()
    keys=pd.MultiIndex.from_frame(raw[['symbol','trade_date']]);raw.index=keys
    rowkey=pd.MultiIndex.from_arrays([a.sid,a.day])
    vol=raw.volume.reindex(rowkey).to_numpy();amount=raw.amount.reindex(rowkey).to_numpy()
    conditions={
        'E0_exit_and_positive_event_same_close':a.native__e0_exited.eq(1)&a.native__numeric_event.eq(1),
        'I_restore_without_new_E0_entry':a.native__i_entered.eq(1)&~a.native__e0_entered.eq(1),
        'I_exit':a.native__i_exited.eq(1),
        'CP_receipt':a.cp__receipt.eq(True),
        'E0_down_with_I_still_active':a.native__numeric_event.eq(-1)&a.native__i_target.eq(1),
        'G1_cold_to_warm':a.cold_to_warm,
        'Eligible_price_bad_volume':a.native__close.notna()&(~np.isfinite(vol)|(vol<=0)),
        'Eligible_CP_input_bad_amount':a.native__close.notna()&(~np.isfinite(amount)|(amount<=0))}
    plan=[];missing=[];used=set()
    for name,mask in conditions.items():
        group=a.loc[mask.fillna(False)]
        if group.empty:missing.append(dict(branch=name,status='NOT_EXERCISED_NO_REAL_PILOT_FIXTURE'));continue
        group=group.loc[[(r.sid,str(r.day.date()))not in used for r in group.itertuples()]]
        if group.empty:missing.append(dict(branch=name,status='ONLY_ALREADY_SELECTED_CUTS'));continue
        row=group.iloc[0];key=(row.sid,str(row.day.date()));used.add(key)
        plan.append(dict(branch=name,sid=key[0],day=key[1]))
    p.save(B/'EDGE_PLAN.json',dict(status='MECHANICAL_FIRST_REAL_BRANCH_CUTS_NOT_OUTCOMES',plan=plan,not_exercised=missing,max_additional_kernel_calls=8))
    start=time.perf_counter();results=[]
    with ProcessPoolExecutor(max_workers=4)as pool:
        for future in as_completed([pool.submit(check,item)for item in plan]):
            r=future.result();results.append(r);print('EDGE_PASS',r['branch'],r['sid'],r['day'],flush=True)
    p.save(B/'EDGE_RECEIPT.json',dict(status='PASS_BOUNDED_REAL_BRANCH_PREFIX_CHECKS',additional_kernel_calls=len(results),results=results,not_exercised=missing,elapsed_seconds=time.perf_counter()-start,accounts=0))

if __name__=='__main__':main()
