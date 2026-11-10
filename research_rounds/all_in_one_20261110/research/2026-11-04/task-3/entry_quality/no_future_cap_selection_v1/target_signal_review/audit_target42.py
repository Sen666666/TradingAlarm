"""Read saved six-stock42-prefix signals only. No model imports or calculations."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent;D=ROOT/'target_signal_completion';E=ROOT.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def null(v):return v is None or(v is pd.NA)or(isinstance(v,(float,np.floating))and not np.isfinite(v))
def scalar_equal(a,b):
    if null(a)or null(b):return null(a)and null(b)
    if isinstance(a,(int,float,np.integer,np.floating))and not isinstance(a,(bool,np.bool_)):
        return np.float64(a).view(np.uint64)==np.float64(b).view(np.uint64)
    return a==b
def main():
    freeze=read(D/'FREEZE.json');complete=read(D/'COMPLETION.json');rows=read(D/'TARGET42.json')
    assert complete['status']=='COMPLETE_BOUNDED_6_STOCK_7_DATE_ORIGINAL_SIGNAL_COMPLETION'
    assert sha(D/'complete_targets.py')==freeze['driver_sha256']
    assert sha(freeze['source_path'])==freeze['source_sha256']
    for p,h in freeze['original_algorithm_code_sha256'].items():assert sha(p)==h,(p,'code hash')
    expected={(s,d)for s in freeze['symbols']for d in freeze['days']}
    assert len(rows)==42 and {(r['sid'],r['day'])for r in rows}==expected and len(expected)==42
    expected_missing={(r['sid'],r['day'])for r in freeze['expected_missing_requests']}
    assert {(r['sid'],r['day'])for r in rows if r['status']=='MISSING_TARGET_BAR'}==expected_missing
    assert sum(r['model_invoked']for r in rows)==38 and sum(r['target_source_row_present']for r in rows)==38
    assert complete['status_counts']=={'EXACT_TARGET_STOCK_SIGNAL':38,'MISSING_TARGET_BAR':4}
    for worker in complete['per_worker']:
        sid=worker['sid'];path=D/(sid.replace('.','_')+'.jsonl');assert sha(path)==worker['output_sha256']and worker['requests']==7
        saved=[r for r in rows if r['sid']==sid];original=[json.loads(line)for line in path.read_text().splitlines()]
        assert saved==original
    fixed_path=E/'selection_qualification_closeout_v1/eligibility_source/fixed35/FIXED35_2024_09_24.parquet'
    fixed=pd.read_parquet(fixed_path).set_index('sid')
    pilot_path=E/'selection_qualification_closeout_v1/eligibility_source/PILOT.json'
    pilot={r['sid']:r['target']for r in read(pilot_path)['rows']}
    legacy={'300085.SZ':fixed.loc['300085.SZ'].to_dict(),'000620.SZ':pilot['000620.SZ'],'002583.SZ':pilot['002583.SZ']}
    featurepath=E/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
    features=pd.read_parquet(featurepath).set_index(['sid','day'])
    flat=pd.read_parquet(D/'TARGET42.parquet').set_index(['sid','day'])
    assert len(flat)==42 and flat.index.is_unique
    csv=pd.read_csv(D/'TARGET42.csv',float_precision='round_trip').set_index(['sid','day'])
    assert set(csv.index)==set(flat.index)
    checked=[];oldchecks=[];ready=0
    for r in rows:
        sid,day=r['sid'],r['day'];f=features.loc[(sid,day)];p=flat.loc[(sid,day)]
        assert r['future_rows_passed']==0 and r['full_S0_eligibility_q']is None
        assert r['scope']=='STOCK_ONLY_E0_G1_I_NOT_ORDER_OR_TRADING_AUTHORIZATION'
        assert r['input_prefix_first']is None or r['input_prefix_first']<=day
        for c in ['prefix_end_day','input_prefix_last','actual_max_input_day']:assert r[c]is None or r[c]<=day
        assert r['prefix_end_day']==r['input_prefix_last']==r['actual_max_input_day']
        assert r['target_source_row_present']==bool(f.target_row_present)
        if r['status']=='MISSING_TARGET_BAR':
            assert not r['model_invoked'] and not r['target_source_row_present']and 'signal'not in r
            assert pd.isna(p.get('close'))
            continue
        assert r['status']=='EXACT_TARGET_STOCK_SIGNAL'and r['model_invoked']and r['target_source_row_present']
        assert r['prefix_end_day']==day and r['input_prefix_rows']>=r['eligible_price_observations']
        target=r['source_target_row'];signal=r['signal'];assert pd.Timestamp(target['trade_date']).date().isoformat()==day
        assert scalar_equal(signal['close'],f.current_close_qfq)and scalar_equal(signal['close'],target['close'])
        for key,val in signal.items():assert scalar_equal(val,p[key]),(sid,day,key,'parquet')
        assert scalar_equal(p.close,csv.loc[(sid,day),'close'])
        for col in ['adjustment_factor','raw_adjustment_factor','reference_adjustment_factor']:
            sourcecol='qfq_adjustment_factor'if col=='adjustment_factor'else col
            assert scalar_equal(target[col],f[sourcecol]),(sid,day,col)
        assert target['source']==f.source and scalar_equal(target['amount'],f.current_amount_passthrough)
        assert r['qfq_reference_after_target']==(pd.Timestamp(target['reference_trade_date'])>pd.Timestamp(day))
        if day=='2024-09-24'and sid in legacy:
            for key,value in signal.items():assert scalar_equal(value,legacy[sid][key]),(sid,key,'previous saved signal')
            oldchecks.append({'sid':sid,'day':day,'all_signal_fields_bitexact_or_equal':True})
        ready+=int(signal['e0_ready']==1)
        checked.append({'sid':sid,'day':day,'prefix_rows':r['input_prefix_rows'],'max_input_day':r['actual_max_input_day'],'close_qfq':signal['close'],'e0_ready':signal['e0_ready'],'i_target':signal['i_target'],'i_buy':signal['i_buy'],'g_grade':signal['g_grade'],'g_fresh_up':signal['g_fresh_up']})
    assert len(checked)==38 and len(oldchecks)==3
    files=[D/'FREEZE.json',D/'COMPLETION.json',D/'complete_targets.py',D/'TARGET42.json',D/'TARGET42.parquet',D/'TARGET42.csv',fixed_path,pilot_path,featurepath,Path(__file__)]
    result={'status':'PASS_BOUNDED_42_SAVED_TARGET_SIGNAL_INPUT_CLOCK_AND_SOURCE_JOIN','remaining_blocks':[],'counts':{'requests':42,'exact_present_signals':38,'missing_target_requests':4,'recomputed_in_review':0,'ready_present_signals':ready,'saved_2024_09_24_prior_signal_checks':3},'checks':['42 frozen stock-date Cartesian requests retained, each <=target prefix metadata consistent with the physical dataset filter in actual driver.','38 target closes and source factor/amount fields match sealed canonical/PVR feature export at IEEE float bits;4 missing source dates never receive model output.','Six worker JSONL/DONE receipts and aggregate rows agree;TARGET42 JSON/parquet signal fields and CSV target closes agree.','Three2024Sep24 saved signal dictionaries agree with previous fixed35/pilot at all fields, floating values bitexact.','Original stock_signal+numeric/participation/evidence/G1/E0 code hashes match freeze; cap/roster are not model frame inputs.','Full_S0_eligibility_q stays None. Signal ready/hold/fresh are not executable permission.'], 'prior_saved_checks':oldchecks,'all_present_checks':checked,'limits':['Read-only source/output audit, no recursive E0/I/model rerun, no independent full raw-prefix rescan. Prefix guarantee is actual filter/source binding plus saved per-request max/count metadata, not a second model invocation.','Canonical qfq reference/vintage and historical bar availability are not certified PIT; <=trade_date alone does not establish publication time.','Only six fixed stocks/seven dates. This is not global5517 signal qualification, full S0/H1/industry/CP/market/legal permission, account or strategy effectiveness.','Original pure helper state outputs such as I_target/i_buy are conditional stock signals. Missing or unready source/legal facts do not grant execution.'],'source_sha256':{str(p.resolve()):sha(p)for p in files},'new_accounts':0,'new_models':0,'network_calls':0}
    f=OUT/'TARGET42_SIGNAL_AUDIT.json';f.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'sha256':sha(f),'counts':result['counts']},ensure_ascii=False))
if __name__=='__main__':main()
