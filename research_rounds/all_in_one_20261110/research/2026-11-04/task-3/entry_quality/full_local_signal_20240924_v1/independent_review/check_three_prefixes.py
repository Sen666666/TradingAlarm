"""Six authorized pure signal calculations:3stocks x2physical prefixes, no account."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import hashlib,importlib.util,json,time,sys
import numpy as np,pandas as pd
import pyarrow.dataset as ds

OUT=Path(__file__).resolve().parent;E=OUT.parents[1]
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
HELPER=E/'selection_qualification_closeout_v1/eligibility_source/stock_signal.py'
PREVIOUS=E/'no_future_cap_selection_v1/target_signal_completion'
SIDS=['000620.SZ','002583.SZ','300085.SZ'];CUT='2024-09-24';EXT='2024-10-08'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return{k:clean(x)for k,x in v.items()}
    if isinstance(v,(list,tuple)):return[clean(x)for x in v]
    if isinstance(v,np.generic):v=v.item()
    if v is pd.NA or v is pd.NaT:return None
    if isinstance(v,float)and not np.isfinite(v):return None
    return v
def calculate_one(sid):
    spec=importlib.util.spec_from_file_location('prefix_original_stock_signal',HELPER)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    original=m.event_frame_numeric;captured=[]
    def observe_events(*args,**kwargs):
        answer=original(*args,**kwargs);captured.append(answer.copy(deep=True));return answer
    # Observe original return unchanged; no second event or model calculation.
    m.event_frame_numeric=observe_events
    calls=[];inputs=[];outputs=[];events=[]
    for end in [CUT,EXT]:
        t=time.monotonic()
        raw=ds.dataset(SOURCE).to_table(columns=['trade_date','open','high','low','close','volume','source'],filter=(ds.field('symbol')==sid)&(ds.field('trade_date')<=pd.Timestamp(end))).to_pandas().sort_values('trade_date')
        assert raw.trade_date.is_unique and raw.trade_date.max()<=pd.Timestamp(end)
        assert raw.source.notna().all()and raw.source.nunique()==1
        frame=raw.set_index('trade_date')[['open','high','low','close','volume']].copy();frame['segment_id']=0
        answer=m.calculate(frame);assert len(captured)==len(calls)+1
        events.append(captured[-1]);inputs.append(frame);outputs.append(answer)
        calls.append({'input_cutoff':end,'input_rows':len(frame),'input_first_day':str(frame.index.min().date()),'input_last_day':str(frame.index.max().date()),'signal_rows':len(answer),'seconds':time.monotonic()-t,'use':'FORMAL_PREFIX_ONLY'if end==CUT else'FUTURE_APPEND_CAUSAL_TEST_ONLY_NOT_FORMAL_SIGNAL'})
        print(json.dumps({'sid':sid,'completed_prefix':end,'seconds':calls[-1]['seconds']}),flush=True)
    pd.testing.assert_frame_equal(inputs[0],inputs[1].loc[:CUT],check_exact=True)
    pd.testing.assert_frame_equal(outputs[0],outputs[1].loc[:CUT],check_exact=True)
    pd.testing.assert_frame_equal(events[0],events[1].loc[:CUT],check_exact=True)
    numeric_bits=0
    for k in outputs[0].select_dtypes(include='number').columns:
        a=outputs[0][k].to_numpy(float);b=outputs[1].loc[:CUT,k].to_numpy(float)
        valid=np.isfinite(a);assert np.array_equal(valid,np.isfinite(b))and np.array_equal(a[valid].view(np.uint64),b[valid].view(np.uint64));numeric_bits+=int(valid.sum())
    confirmed=events[0].confirmed_pivot_date.dropna()
    assert all(pd.Timestamp(v)<=at for at,v in confirmed.items())
    for i,label in enumerate(['PREFIX_ONLY','FUTURE_APPEND_TEST_ONLY']):
        outputs[i].to_parquet(OUT/(sid.replace('.','_')+'_'+label+'_SIGNALS.parquet'))
        events[i].to_parquet(OUT/(sid.replace('.','_')+'_'+label+'_EVENTS.parquet'))
    return {'sid':sid,'calls':calls,'common_prefix_signals_all_fields_exact':True,'common_prefix_events_all_fields_exact':True,'finite_numeric_signal_bit_checks':numeric_bits,'confirmed_pivot_date_is_occurrence_not_known_date':True,'event_rows_are_known_at_event_row_not_backdated':True,'extra_future_source_rows_for_test':len(inputs[1])-len(inputs[0]),'target_signal':clean(outputs[0].loc[pd.Timestamp(CUT)].to_dict()),'model_calls':2}
def main():
    assert not(OUT/'PREFIX_CAUSALITY_AUDIT.json').exists(),'No automatic re-execution'
    old=json.loads((PREVIOUS/'FREEZE.json').read_text())
    assert sha(SOURCE)==old['source_sha256']
    for p,h in old['original_algorithm_code_sha256'].items():assert sha(p)==h,(p,'source changed')
    start=time.monotonic()
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'))as pool:results=list(pool.map(calculate_one,SIDS))
    previous=json.loads((PREVIOUS/'TARGET42.json').read_text())
    for r in results:
        oldsignal=next(x['signal']for x in previous if x['sid']==r['sid']and x['day']==CUT)
        assert r['target_signal']==oldsignal,(r['sid'],'previous formal signal')
    result={'status':'PASS_BOUNDED_THREE_STOCK_TWO_PREFIX_CAUSALITY_AND_SOURCE_GATE','remaining_blocks':[],'formal_target_date':CUT,'test_extension_cutoff':EXT,'cases':results,'authorized_model_calls':6,'new_accounts':0,'full_universe_model_runs':0,'elapsed_seconds':time.monotonic()-start,'source_sha256':{**old['original_algorithm_code_sha256'],str(SOURCE):sha(SOURCE),str(Path(__file__).resolve()):sha(Path(__file__))},'output_sha256':{p.name:sha(p)for p in OUT.glob('*.parquet')},'limits':['Three selected stocks and one target cutoff versus one real5-observation extension only; not a proof for every source/unknown/segment branch or all5517 stocks.','Future-appended runs are isolated causal tests, never used as formal target-date signals.','Original event dataframe itself, including confirmed-pivot dates, and complete signal dataframes match all shared prefix rows; do not backdate confirmation to historical pivot occurrence.','Input is the same canonical qfq vintage. This does not certify historical factor versions, publication time or tradability.','Ready=False/unknown must be nullable UNKNOWN in downstream stock permission views, never a fabricated legal execution grant; i_buy is current opportunity, not first actual trade.']}
    p=OUT/'PREFIX_CAUSALITY_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'sha256':sha(p),'seconds':result['elapsed_seconds'],'cases':[{'sid':r['sid'],'rows':r['calls'][0]['signal_rows'],'future_test_rows':r['extra_future_source_rows_for_test']}for r in results]}),flush=True)
if __name__=='__main__':main()
