"""20-stock, once-per-stock daily signal cache pilot. No account/order engine.

Exports original rows; finite physical-prefix tests remain explicitly bounded.
CP uses original I-derived facts and preserves its first-invalid-input failure.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse, datetime, hashlib, importlib.util, json, math, os, sys, time
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parent
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
ADAPTER=ENTRY/'selection_qualification_closeout_v1/eligibility_source'
CPFILE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
PVRFILE=ENTRY/'pvr_information_v1/feature_design/features.py'
FEATURES=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
START='2022-01-01';END='2026-05-15';WORKERS=8
COLS=['symbol','trade_date','open','high','low','close','volume','amount','source']
FIELDS=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    if isinstance(x,np.generic):x=x.item()
    if x is pd.NA or x is pd.NaT:return None
    if isinstance(x,(pd.Timestamp,np.datetime64)):return str(pd.Timestamp(x))
    return None if isinstance(x,float)and not math.isfinite(x)else x
def save(p,x):Path(p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
def modules():
    sys.path.insert(0,str(ADAPTER));import stock_signal as native
    return native,load(CPFILE,'pilot_original_cp'),load(PVRFILE,'pilot_original_pvr')
def compare_frames(a,b,label):
    assert a.index.equals(b.index)and a.columns.equals(b.columns),(label,'schema')
    for col in a:
        u,v=a[col],b[col]
        assert u.isna().equals(v.isna()),(label,col,'NA mask')
        good=u.notna()
        if pd.api.types.is_numeric_dtype(u)and not pd.api.types.is_bool_dtype(u):
            x=u.loc[good].to_numpy(dtype=np.float64);y=v.loc[good].to_numpy(dtype=np.float64)
            assert np.array_equal(x.view(np.uint64),y.view(np.uint64)),(label,col,'numeric bits')
        else:assert u.loc[good].astype(str).equals(v.loc[good].astype(str)),(label,col,'value')
    return int(len(a)*len(a.columns))

def prepare():
    assert not(HERE/'FREEZE.json').exists()
    sourcehash=sha(SOURCE);assert sourcehash=='11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b'
    fixed=['000620.SZ','300666.SZ','603061.SH','301611.SZ','300085.SZ','002583.SZ','300604.SZ','002371.SZ','688012.SH','688498.SH','301308.SZ','000520.SZ','601601.SH','600030.SH','600519.SH','000001.SZ','000002.SZ','002500.SZ']
    feature=pd.read_parquet(FEATURES);g=feature.loc[feature.day.eq('2026-01-15')&feature.sid.str.endswith('.BJ')&feature.target_row_present&feature.source_observation_count_through_t.ge(100)]
    g=g.sort_values(['source_observation_count_through_t','sid'])
    ids=fixed+[g.iloc[0].sid,g.iloc[-1].sid]
    assert len(ids)==len(set(ids))==20
    for p in ['full','prefix','reports']: (HERE/p).mkdir(exist_ok=True)
    date_data=ds.dataset(SOURCE).to_table(columns=['trade_date'],filter=(ds.field('trade_date')>=pd.Timestamp(START))&(ds.field('trade_date')<=pd.Timestamp(END))).to_pandas()
    dates=sorted(date_data.trade_date.unique());pd.DataFrame({'day':pd.to_datetime(dates)}).to_parquet(HERE/'SOURCE_DATE_UNION.parquet',index=False)
    roster=pd.DataFrame({'sid':ids,'selection_reason':['11 previously fixed algorithm cases']*11+['7 fixed bank/broker/insurance/property/consumer/START-counterexample controls']*7+['BJ shortest >=100 prior observations at fixed2026/1/15','BJ longest prior observations at fixed2026/1/15']})
    roster.to_csv(HERE/'PILOT20_ROSTER.csv',index=False)
    old=json.loads((ENTRY/'full_local_signal_two_dates_v1/2026-01-15/signals/FREEZE.json').read_text())
    codes=old['original_algorithm_code_sha256'].copy()
    for path in [Path(__file__),CPFILE,PVRFILE]:codes[str(path.resolve())]=sha(path)
    for path,h in codes.items():assert sha(path)==h
    save(HERE/'FREEZE.json',dict(status='FIXED20_DAILY_SIGNAL_CACHE_IMPLEMENTATION_PILOT_NOT_ALPHA_TEST',stocks=ids,
        dates_start=START,actual_end=END,requested_H1_end='2026-06-30',H1_complete=False,source= str(SOURCE),source_sha256=sourcehash,source_size=SOURCE.stat().st_size,source_mtime_ns=SOURCE.stat().st_mtime_ns,
        full_source_origin_retained=True,output_dates_union_N=len(dates),output_grid_rows=20*len(dates),grid_not_official_calendar=True,
        original_code_sha256=codes,roster_sha256=sha(HERE/'PILOT20_ROSTER.csv'),date_union_sha256=sha(HERE/'SOURCE_DATE_UNION.parquet'),workers=WORKERS,
        content=['Original stock_signal19 fields','Original numeric confirmation row incl pivot occurrence date, current row=confirmed day','Original CP market-only receipt/candidate with e0_valid=I target,e0_down=numeric -1,i_floor=I floor;no position P','Original PVR eight values and its own valid/block clock','Frozen diagnostic E0 structure phase, not new permission'],
        CP_invalid_rule='Original CP forbids invalid close/amount in input. Cache valid history only before first invalid CP row, thereafter BLOCKED_BY_PRIOR_INVALID_INPUT;never drop/fill/resume or retroactively erase earlier valid CP.',
        physical_prefix_matrix='For each20: eligible ordinal65 warmup; middle actually-observed row after2022 with future remaining. Compare ALL common-prefix fields incl NA,not just target; optional max6 real branches chosen mechanically from baseline,not outcomes.',
        separate_checks=['All daily source-union serialization roundtrip vs baseline output','Same-source three old days all19 fields incl missing/rejected/unknown','Same-source seven old PVR dates','Limited physical-prefix cuts for complete kernel native/numeric/CP/PVR/phase'],
        not_claimed=['Exhaustive1054 physical-prefix calls per stock','Historic daily independent canonical CP cache exists','PIT ST/halt/listing/corporate-action/publication or execution eligibility','Actual holding CP protection/quantity/account state'],
        no_accounts=True,no_network=True,no_score_parameter_change=True))
    print('FROZEN20',ids,'grid',20*len(dates),flush=True)

def validate():
    f=json.loads((HERE/'FREEZE.json').read_text())
    s=SOURCE.stat();assert s.st_size==f['source_size']and s.st_mtime_ns==f['source_mtime_ns']
    for p,h in f['original_code_sha256'].items():assert sha(p)==h,p
    return f

def phases(native,events,cmp):
    phase='UNKNOWN';peak=None;reference=None;start=broken=breakout=None;rows=[]
    for day,r in native.iterrows():
        ev=events.loc[day];kind=int(ev.event)
        if kind==-1:peak=dict(price=float(ev.confirmed_pivot_price),occurred=str(ev.confirmed_pivot_date),confirmed=str(day.date()))
        active=bool(r.e0_target);ready=bool(r.e0_ready)
        if not ready:phase='UNKNOWN'
        elif not active:
            phase='BROKEN'if bool(r.e0_exited)else'INACTIVE';reference=None;breakout=None
        elif kind==-1:phase='RETRACED';reference=None;broken=str(day.date());breakout=None
        elif kind==1:phase='START';reference=peak.copy()if peak else None;start=str(day.date());breakout=None
        if active and phase=='START'and reference and cmp(float(r.close),reference['price'])>0:phase='BREAKOUT';breakout=str(day.date())
        rows.append(dict(phase=phase,reference_peak=reference['price']if reference else np.nan,
            reference_peak_occurred=reference['occurred']if reference else None,reference_peak_confirmed=reference['confirmed']if reference else None,
            start_date=start,breakout_date=breakout,downgrade_date=broken,last_peak=peak['price']if peak else np.nan,
            last_peak_occurred=peak['occurred']if peak else None,last_peak_confirmed=peak['confirmed']if peak else None))
    return pd.DataFrame(rows,index=native.index)

def kernel(g):
    """All numerical inputs must physically end at this call's cutoff."""
    native,cp,pvr=modules();assert g.trade_date.is_unique and g.source.nunique(dropna=False)==1 and g.source.notna().all()
    raw=g.set_index('trade_date')[['open','high','low','close','volume']].copy();raw['segment_id']=0
    timings={};cpu={}
    def timed(name,fn):
        w=time.perf_counter();c=time.process_time();v=fn();timings[name]=time.perf_counter()-w;cpu[name]=time.process_time()-c;return v
    capture={};original=native.event_frame_numeric
    def spy(*args,**kwargs):
        assert not capture
        v=original(*args,**kwargs);capture['events']=v;return v
    native.event_frame_numeric=spy
    try:n=timed('original_stock_signal',lambda:native.calculate(raw))
    finally:native.event_frame_numeric=original
    e=capture['events'];assert n.index.equals(e.index)
    pinput=g.set_index('trade_date')[['close','amount']].copy();pinput['segment_id']=0
    p=timed('original_PVR',lambda:pvr.original_pvr(pinput))
    valid,blocks=pvr.original_observation_clock(pinput);p['valid_observation']=valid;p['clock_block']=blocks
    cpinput=pd.DataFrame(index=n.index);cpinput['close']=n.close
    cpinput['amount']=g.set_index('trade_date').amount.reindex(n.index);cpinput['segment_id']=0
    cpinput['e0_valid']=n.i_target.astype(bool);cpinput['e0_down']=n.numeric_event.eq(-1).astype(bool);cpinput['i_floor']=n.i_floor
    bad=~(np.isfinite(cpinput.close)&cpinput.close.gt(0)&np.isfinite(cpinput.amount)&cpinput.amount.gt(0))
    stop=int(np.flatnonzero(bad.to_numpy())[0])if bad.any()else len(cpinput)
    if stop:q=timed('original_CP',lambda:cp.calculate(cpinput.iloc[:stop]))
    else:q=pd.DataFrame(index=n.index[:0]);timings['original_CP']=0.;cpu['original_CP']=0.
    q=q.reindex(n.index);q['input_status']='VALID_OR_WARMUP'
    if stop<len(n):q.loc[n.index[stop:],'input_status']='BLOCKED_BY_PRIOR_INVALID_INPUT'
    stage=timed('phase_annotation',lambda:phases(n,e,native.event_frame_numeric.__globals__['compare']))
    bundle=pd.concat([n.add_prefix('native__'),e.add_prefix('numeric__'),q.add_prefix('cp__'),p.add_prefix('pvr__'),stage.add_prefix('stage__')],axis=1)
    assert bundle.columns.is_unique
    return bundle,dict(component_wall_seconds=timings,component_CPU_seconds=cpu,input_rows=len(g),eligible_rows=len(n),
        cp_input_rows=len(cpinput),cp_first_bad_date=str(n.index[stop].date())if stop<len(n)else None,
        native_columns=len(n.columns),numeric_columns=len(e.columns),cp_columns=len(q.columns),pvr_columns=len(p.columns),stage_columns=len(stage.columns))

def original_matches(sid,bundle,g):
    checks=[]
    for day in ['2022-01-24','2024-09-24','2026-01-15']:
        path=ENTRY/'full_local_signal_20240924_v1/signals/ALL_SIGNALS.parquet'if day=='2024-09-24'else ENTRY/'full_local_signal_two_dates_v1'/day/'signals/ALL_SIGNALS.parquet'
        old=pd.read_parquet(path).set_index('sid').loc[sid]
        stamp=pd.Timestamp(day)
        if stamp not in bundle.index or pd.isna(bundle.loc[stamp,'native__close']):
            assert old.signal_status!='EXACT_TARGET_STOCK_SIGNAL'
            checks.append(dict(day=day,status=str(old.signal_status),exact_fields=0));continue
        a=bundle.loc[[stamp],['native__'+c for c in FIELDS]].copy();a.columns=FIELDS
        v=pd.DataFrame([{c:old[c]for c in FIELDS}],index=a.index)
        compare_frames(a,v,f'old19 {sid} {day}')
        checks.append(dict(day=day,status='EXACT19',exact_fields=19))
    oldp=pd.read_parquet(FEATURES);oldp=oldp.loc[oldp.sid.eq(sid)]
    pcols=['r','scale','amount_ref','u','b','e','E','score'];pc=[]
    for _,r in oldp.iterrows():
        stamp=pd.Timestamp(r.day)
        if stamp not in bundle.index:assert not r.target_row_present;continue
        a=bundle.loc[[stamp],['pvr__'+c for c in pcols]].copy();a.columns=pcols
        v=pd.DataFrame([{c:r[c]for c in pcols}],index=a.index)
        compare_frames(a,v,f'oldPVR {sid} {r.day}');pc.append(str(r.day))
    return checks,pc

def full_stock(sid):
    validate();begin=time.perf_counter()
    g=ds.dataset(SOURCE).to_table(columns=COLS,filter=ds.field('symbol').isin([sid])&(ds.field('trade_date')<=pd.Timestamp(END))).to_pandas().sort_values('trade_date')
    assert not g.empty
    data,meta=kernel(g)
    folder=HERE/'full'/sid;folder.mkdir(exist_ok=True)
    assert not(folder/'RECEIPT.json').exists()
    # Full history is a bounded20-stock verification baseline, not the proposed all-market payload.
    data.to_parquet(folder/'BASELINE_FULL_HISTORY.parquet',compression='zstd')
    restored=pd.read_parquet(folder/'BASELINE_FULL_HISTORY.parquet');cells=compare_frames(data,restored,sid+' full roundtrip')
    dates=pd.DatetimeIndex(pd.read_parquet(HERE/'SOURCE_DATE_UNION.parquet').day)
    out=data.reindex(dates).copy();out.insert(0,'day',dates);out.insert(0,'sid',sid)
    out['source_row_present']=dates.isin(g.trade_date)
    out['stock_eligible_price_observation']=out['native__close'].notna()
    known=(out.native__e0_ready.eq(1)&out.native__g_ready.eq(True)).fillna(False)
    out['stock_signal_knowledge']=np.where(~out.source_row_present,'MISSING_SOURCE_ROW',np.where(~out.stock_eligible_price_observation,'INVALID_ORIGINAL_PRICE_MASK',np.where(known,'READY','WARMUP_OR_STRENGTH_UNKNOWN')))
    rawprice=g.set_index('trade_date')[['open','high','low','close','volume','amount']].add_prefix('price__')
    out=out.join(rawprice.reindex(dates));out['historical_trading_eligibility']='UNKNOWN_NONPIT'
    target=folder/'DAILY2022_20260515.parquet';out.to_parquet(target,index=False,compression='zstd')
    reread=pd.read_parquet(target).set_index('day');reread.index.name=data.index.name
    same=out.set_index('day');same.index.name=data.index.name
    dailycells=compare_frames(same,reread,sid+' daily roundtrip')
    old,oldp=original_matches(sid,data,g)
    # Fixed ordinal65 and internal middle cut; retain whole old origin and all common-prefix rows.
    eligible=data.index[data.native__close.notna()]
    warm=eligible[min(64,len(eligible)-1)]
    observed=eligible[(eligible>=pd.Timestamp(START))&(eligible<pd.Timestamp(END))]
    middle=observed[len(observed)//2]if len(observed)else eligible[len(eligible)//2]
    cuts=sorted(set([warm,middle]))
    for day in cuts:
        clipped=g.loc[g.trade_date.le(day)].copy();prefix,pm=kernel(clipped)
        baseline=data.loc[data.index<=day]
        commoncells=compare_frames(prefix,baseline,f'physical prefix {sid} {day.date()}')
        save(folder/f'PREFIX_{day.date()}.json',dict(sid=sid,cut=str(day.date()),input_max=str(clipped.trade_date.max().date()),input_rows=len(clipped),compared_rows=len(prefix),compared_columns=len(prefix.columns),bitexact_cells=commoncells,component_profile=pm,full_future_not_in_prefix_input=True))
    receipt=dict(sid=sid,status='PASS20_STOCK_BASELINE_DAILY_ROUNDTRIP_OLD19_PVR_AND_TWO_PREFIX_CUTS',
        source_first=str(g.trade_date.min().date()),source_last=str(g.trade_date.max().date()),profile=meta,
        daily_grid_rows=len(out),source_rows_in_output=int(out.source_row_present.sum()),price_eligible_output_rows=int(out.stock_eligible_price_observation.sum()),
        baseline_rows=len(data),all_columns=len(data.columns),output_columns=len(out.columns),full_roundtrip_cells=cells,daily_roundtrip_cells=dailycells,
        old19_checks=old,oldPVR_dates=oldp,physical_prefix_cuts=[str(d.date())for d in cuts],
        physical_prefix_total_calls=len(cuts),old_same_source_daily_CP_history_available=False,
        file_bytes={p.name:p.stat().st_size for p in folder.glob('*.parquet')},file_sha256={p.name:sha(p)for p in folder.glob('*.parquet')},
        wall_seconds=time.perf_counter()-begin,no_accounts=True)
    save(folder/'RECEIPT.json',receipt)
    return receipt

def run():
    f=validate();pending=[s for s in f['stocks']if not(HERE/'full'/s/'RECEIPT.json').exists()]
    start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=WORKERS)as pool:
        futures=[pool.submit(full_stock,s)for s in pending]
        for future in as_completed(futures):
            r=future.result();print('COMPLETE',r['sid'],'rows',r['daily_grid_rows'],'prefix',r['physical_prefix_cuts'],'seconds',round(r['wall_seconds'],2),flush=True)
            done=[s for s in f['stocks']if(HERE/'full'/s/'RECEIPT.json').exists()]
            save(HERE/'LIVE_PROGRESS.json',dict(completed=len(done),total=20,elapsed_seconds=time.perf_counter()-start))
    records=[json.loads((HERE/'full'/s/'RECEIPT.json').read_text())for s in f['stocks']]
    save(HERE/'RUN_RECEIPT.json',dict(status='COMPLETE20_BASELINE_AND_TWO_PHYSICAL_PREFIXES_PER_STOCK',stocks=len(records),elapsed_seconds=time.perf_counter()-start,records=records,
         calls_new_full_signal=20+sum(r['physical_prefix_total_calls']for r in records),accounts=0,
         no_all5517_run=True,not_exhaustive_every_date_physical_recompute=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);a=p.parse_args()
    if a.mode=='prepare':prepare()
    else:run()
