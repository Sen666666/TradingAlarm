"""Read saved outputs only. No model imports, signal calculation or account."""
from pathlib import Path
from collections import Counter
import hashlib,json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ENTRY=HERE.parents[1]
S=ENTRY/'selection_qualification_closeout_v1/eligibility_source'
F35=S/'fixed35'
FEATURES=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
DAYS=['2022-01-10','2022-01-24','2024-09-24','2024-10-08','2026-01-15','2026-01-20','2026-05-15']
TARGETS={'000620.SZ':'盈新','300085.SZ':'银之杰','002583.SZ':'海能达','300666.SZ':'江丰电子','603061.SH':'金海通','301611.SZ':'珂玛科技'}
FIELDS=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x)for x in v]
    if isinstance(v,np.generic):v=v.item()
    if isinstance(v,(pd.Timestamp,np.datetime64)):return str(v)
    if v is pd.NA or v is pd.NaT:return None
    return None if isinstance(v,float)and not np.isfinite(v)else v
def save(n,v):(HERE/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def bit(a,b):return np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64)

def main():
    assert not(HERE/'SEAL.json').exists()
    seal=read(F35/'SEAL.json');freeze=read(F35/'SAMPLE_FREEZE.json')
    completion=read(F35/'COMPLETION.json');stopseal=read(S/'STOP_SEAL.json')
    checks=[]
    for folder,receipt,names in [(F35,seal,['FIXED35_2024_09_24.parquet','SAMPLE_FREEZE.json','COMPLETION.json','run_fixed35.py']),
                                (S,stopseal,['stock_signal.py','pilot.py','PILOT.json','FULL_SIGNAL_RUN_STARTED.json'])]:
        for name in names:
            p=folder/name;actual=sha(p);expected=receipt['files'][name]
            assert actual==expected
            checks.append(dict(path=str(p),actual_sha256=actual,recorded_sha256=expected,matches=True))
    for p,h in freeze['algorithm_code_sha256'].items():
        if p.endswith('.py'):
            assert sha(p)==h
            checks.append(dict(path=p,actual_sha256=sha(p),recorded_sha256=h,matches=True))
    assert sha(FEATURES)==freeze['source_sha256'][str(FEATURES)]
    checks.append(dict(path=str(FEATURES),actual_sha256=sha(FEATURES),recorded_sha256=freeze['source_sha256'][str(FEATURES)],matches=True))
    f=pd.read_parquet(F35/'FIXED35_2024_09_24.parquet')
    feat=pd.read_parquet(FEATURES)
    assert len(f)==35 and f.sid.nunique()==35 and set(f.day)=={'2024-09-24'}
    assert set(f.sid)==set(freeze['symbols'])
    assert f.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL').all()
    assert f.target_source_row_present.all()and f.S0_eligibility_q.isna().all()
    m=f.merge(feat,on=['sid','day'],validate='one_to_one',suffixes=('_signal','_feature'))
    assert np.array_equal(m.close.to_numpy(float).view(np.uint64),m.current_close_qfq_feature.to_numpy(float).view(np.uint64))
    assert ((f.e0_ready.eq(1)&f.i_target.eq(1))==f.stock_hold_signal).all()
    assert ((f.e0_ready.eq(1)&f.i_target.eq(1)&f.i_buy.eq(True))==f.stock_fresh_core_signal).all()
    keep=['sid','day']+FIELDS+['stock_hold_signal','stock_fresh_core_signal','S0_eligibility_q','S0_status','score','FULL_LOCAL_top20_member','OLD1709_EXACT_SUBPOOL_top20_member','fixed35_bare_PVR_rank','fixed35_hold_PVR_rank','fixed35_fresh_PVR_rank','reference_trade_date','adjustment_factor','raw_adjustment_factor','reference_adjustment_factor']
    f[keep].to_csv(HERE/'FIXED35_REUSED_SIGNAL_ROWS.csv',index=False)
    fixed=[]
    for day in DAYS:
        g=feat.loc[feat.day.eq(day)&feat.sid.isin(f.sid)]
        fixed.append(dict(day=day,frozen_symbols=35,saved_exact_E0_I_rows=35 if day=='2024-09-24'else 0,
            unknown_E0_I_rows=0 if day=='2024-09-24'else 35,
            saved_price_rows=int(g.target_row_present.eq(True).sum()),
            signal_status='COMPLETE_FIXED35_STOCK_ONLY'if day=='2024-09-24'else'UNKNOWN_NO_SAVED_SAME_SOURCE_SIGNAL'))
    pd.DataFrame(fixed).to_csv(HERE/'FIXED35_SEVEN_DATE_SIGNAL_COVERAGE.csv',index=False)
    pilot=read(S/'PILOT.json');pilby={r['sid']:r for r in pilot['rows']if 'target'in r}
    for r in pilby.values():
        ft=feat.loc[feat.sid.eq(r['sid'])&feat.day.eq('2024-09-24')].iloc[0]
        assert bit(r['target']['close'],ft.current_close_qfq)
    # A stopped partial is never a full population. Check only the named IDs.
    partial_named=[]
    for p in sorted(S.glob('SHARD_*_STOCK_SIGNAL.jsonl')):
        for line in p.open():
            r=json.loads(line)
            if r['sid']in TARGETS:partial_named.append(dict(sid=r['sid'],day=r['day'],path=str(p)))
    assert not partial_named
    targetrows=[]
    for sid,name in TARGETS.items():
        for day in DAYS:
            pr=feat.loc[feat.sid.eq(sid)&feat.day.eq(day)].iloc[0]
            record=dict(sid=sid,name=name,day=day,saved_E0_I_status='UNKNOWN_NO_SAVED_SAME_SOURCE_SIGNAL',
                original_signal_data_hash_bound=None,signal_output_path=None,
                target_price_row_present=pr.target_row_present,target_price_status=pr.target_status,
                canonical_qfq_close=pr.current_close_qfq,canonical_observations_through_t=pr.source_observation_count_through_t,
                canonical_qfq_reference_later_than_t=pr.qfq_reference_later_than_target,
                price_source=pr.source,full_S0_eligibility='UNKNOWN_NOT_EVALUATED')
            record.update({k:None for k in FIELDS})
            if day=='2024-09-24'and sid in set(f.sid):
                r=f.set_index('sid').loc[sid]
                record.update({k:r[k]for k in FIELDS})
                record.update(saved_E0_I_status='SAVED_EXACT_SIGNAL_SOURCE_AND_CODE_HASH_BOUND',
                    original_signal_data_hash_bound=True,signal_output_path=str(F35/'FIXED35_2024_09_24.parquet'))
            elif day=='2024-09-24'and sid in pilby:
                record.update(pilby[sid]['target'])
                record.update(saved_E0_I_status='SAVED_SAME_SOURCE_PILOT_PATH_BOUND_INPUT_HASH_NOT_STORED',
                    original_signal_data_hash_bound=False,signal_output_path=str(S/'PILOT.json'))
            targetrows.append(record)
    out=pd.DataFrame(targetrows)
    out.to_csv(HERE/'TARGET6_SEVEN_DATE_SIGNAL_AVAILABILITY.csv',index=False)
    save('TARGET6_SEVEN_DATE_SIGNAL_AVAILABILITY.json',targetrows)
    save('REVIEW_RECEIPT.json',dict(status='SAVED_OUTPUT_READ_ONLY_REVIEW_COMPLETE',
        frozen_days=DAYS,target_symbols=TARGETS,source_hash_checks=checks,
        fixed35=dict(rows=35,day='2024-09-24',ready=int(f.e0_ready.eq(1).sum()),
            e0_target=int(f.e0_target.eq(1).sum()),i_target=int(f.i_target.eq(1).sum()),i_buy=int(f.i_buy.eq(True).sum()),
            same_close_bitexact_to_saved_canonical_features=True,
            qfq_reference_after_t=int(m.qfq_reference_later_than_target.eq(True).sum()),
            full_S0_not_evaluated=True,signal_qualified_all_market_population=False,
            counts_by_original_top20_membership=completion['by_original_scope']),
        target42=dict(cells=len(out),saved_signal_status_counts=dict(Counter(out.saved_E0_I_status)),
            price_row_present=int(out.target_price_row_present.eq(True).sum()),price_row_absent=int(out.target_price_row_present.eq(False).sum()),
            no_price_row_not_listing_or_delisting_fact=True,partial_named_rows=partial_named),
        canonical_source_binding=dict(path=str(SOURCE),sha256_recorded_by_fixed35_producer=freeze['source_sha256'][str(SOURCE)],
            rehashed_canonical_large_file_in_this_read_only_review=False,
            note='Verified saved fixed35 output/receipt/algorithm hashes and saved canonical feature hash; no canonical file rewrite or new signal execution. Pilot receipt stores code hashes, not input file hash.'),
        zero_accounts=True,zero_models_executed=True,zero_new_rankings=True,zero_future_outcome_labels=True,
        no_current_cap_input_used=True,not_a_new_parameter_or_strategy_test=True))
    excerpts=[]
    for p,ranges in [(S/'stock_signal.py',[(18,55)]),(S/'fixed35/run_fixed35.py',[(35,73)]),
        (S/'pilot.py',[(10,35)]),
        (Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py'),[(6,34)])]:
        lines=p.read_text().splitlines();excerpts.append(str(p)+'\nSHA256 '+sha(p))
        for lo,hi in ranges:excerpts.append('\n'.join(f'{i:5d} {lines[i-1]}'for i in range(lo,min(hi,len(lines))+1)))
    (HERE/'SIGNAL_MEANING_SOURCE_EXCERPTS.txt').write_text('\n\n'.join(excerpts)+'\n')
    print(json.dumps(dict(fixed35=dict(ready=35,I_target=34,i_buy=32),target_status_counts=dict(Counter(out.saved_E0_I_status)),target_price_rows=int(out.target_price_row_present.eq(True).sum())),ensure_ascii=False))

if __name__=='__main__':main()
