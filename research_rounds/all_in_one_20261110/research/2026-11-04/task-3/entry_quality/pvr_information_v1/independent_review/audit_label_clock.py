"""Small independent scalar label oracle; no full labels or feature recomputation."""
from pathlib import Path
import gzip,hashlib,importlib.util,json,math,signal,time
import numpy as np,pandas as pd
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent;P=O.parent
CODE=P/'analysis/label_clock.py'
spec=importlib.util.spec_from_file_location('pvr_info_label_clock_under_review',CODE);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fail(*_):raise TimeoutError('Independent small label audit60second budget')
def scalar(features,quotes,key,calendar,h):
    q=quotes[(quotes.window==key['window'])&(quotes.sid==key['sid'])].set_index('day')
    f=features[(features.window==key['window'])&(features.sid==key['sid'])].set_index('day')
    i=calendar.index(key['day']) if key['day'] in calendar else -1
    mature=i>=0 and i+h<len(calendar)
    def good(day):
        if day not in q.index or day not in f.index:return False
        r=q.loc[day];return bool(f.loc[day,'stock_source_row_present'])and bool(r.observed)and bool(r.valid)and math.isfinite(r.close)and r.close>0
    def same(day):
        r=q.loc[key['day']];s=q.loc[day];a=f.loc[key['day'],'source_segment'];b=f.loc[day,'source_segment']
        return all(math.isfinite(v)for v in [r.block,s.block,a,b])and r.block==s.block and a==b
    start=i>=0 and good(key['day']);openok=False
    if start and i+1<len(calendar):
        nd=calendar[i+1];r=q.loc[nd];openok=good(nd)and same(nd)and math.isfinite(r.open)and r.open>0
    endgood=mature and start and good(calendar[i+h])and same(calendar[i+h])
    c=float(q.loc[key['day'],'close'])if start else np.nan
    op=float(q.loc[calendar[i+1],'open'])if openok else np.nan
    end=float(q.loc[calendar[i+h],'close'])if endgood else np.nan
    complete=mature and endgood and openok and all(good(d)for d in calendar[i+1:i+h+1])
    return dict(mature=mature,known=endgood and openok,close=end/c-1 if endgood else np.nan,open=end/op-1 if endgood and openok else np.nan,
                gap=op/c-1 if openok else np.nan,complete=complete,
                peak=max(float(q.loc[d,'close'])for d in calendar[i+1:i+h+1])/op-1 if complete else np.nan,
                trough=min(float(q.loc[d,'close'])for d in calendar[i+1:i+h+1])/op-1 if complete else np.nan)
def same(a,b):return bool(np.isnan(a)and np.isnan(b))or bool(np.isclose(a,b,atol=1e-12,rtol=1e-11))
def check(f,q,keys,cals):
    got,counts=M.build_labels(f,q,keys,cals);assert len(got)==len(keys)
    for _,r in got.iterrows():
        for h in [5,20,60]:
            z=scalar(f,q,r,cals[r.window],h);tag='h'+str(h)+'_'
            assert bool(r[tag+'mature'])==z['mature'] and (r[tag+'status']=='KNOWN')==z['known']
            assert same(r[tag+'decision_CLOSE_return'],z['close'])and same(r[tag+'next_OPEN_return'],z['open'])and same(r.next_OPEN_gap,z['gap'])
            if h==60:
                assert bool(r.h60_entire_future_path_valid)==z['complete']
                assert same(r.h60_max_CLOSE_from_next_OPEN,z['peak'])and same(r.h60_min_CLOSE_from_next_OPEN,z['trough'])
                assert bool(r.h60_future_tail_ge30)==(z['peak']>=.3) if z['complete'] else pd.isna(r.h60_future_tail_ge30)
    return got,counts
def synthetic():
    cals={'long':[str(x.date())for x in pd.bdate_range('2024-01-02',periods=65)],'strong':[str(x.date())for x in pd.bdate_range('2025-07-01',periods=65)]}
    qs=[];fs=[]
    for w,cal in cals.items():
        qs.append(pd.DataFrame(dict(window=w,day=cal,sid='X',open=np.ones(65)*100,close=100+np.arange(65,dtype=float),valid=True,block=0.,observed=True)))
        fs.append(pd.DataFrame(dict(window=w,day=cal,sid='X',stock_source_row_present=True,source_segment=0.)))
    q=pd.concat(qs,ignore_index=True);f=pd.concat(fs,ignore_index=True);keys=pd.DataFrame([dict(window=w,day=cals[w][i],sid='X')for w in cals for i in [0,4,60,64]])
    tests=[]
    for name in ['base_crosswindow_censor','positive_gap','next_open_zero','next_row_absent','next_not_observed','endpoint_absent','block_transition','segment_transition','interior_missing_only','future_max_excludes_signal_close']:
        x=q.copy();y=f.copy()
        if name=='positive_gap':x.loc[1,'open']=120
        elif name=='next_open_zero':x.loc[1,'open']=0
        elif name=='next_row_absent':y.loc[1,'stock_source_row_present']=False;x.loc[1,['open','close']]=np.nan
        elif name=='next_not_observed':x.loc[1,'observed']=False
        elif name=='endpoint_absent':y.loc[5,'stock_source_row_present']=False;x.loc[5,'close']=np.nan
        elif name=='block_transition':x.loc[1:64,'block']=1
        elif name=='segment_transition':y.loc[1:64,'source_segment']=1
        elif name=='interior_missing_only':y.loc[2,'stock_source_row_present']=False;x.loc[2,['open','close']]=np.nan
        elif name=='future_max_excludes_signal_close':x.loc[0,'close']=1000
        got,_=check(y,x,keys,cals)
        if name=='interior_missing_only':assert got.iloc[0].h60_status=='KNOWN'and not got.iloc[0].h60_entire_future_path_valid
        if name=='base_crosswindow_censor':assert got.iloc[3].h5_status=='HORIZON_UNMATURED'
        if name=='block_transition':assert got.iloc[0].next_sourceblock_transition
        if name=='segment_transition':assert got.iloc[0].next_source_segment_transition
        tests.append(name)
    return tests
def main():
    start=time.monotonic();signal.signal(signal.SIGALRM,fail);signal.setitimer(signal.ITIMER_REAL,60);source={str(CODE):sha(CODE)}
    tests=synthetic();sm=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');records=json.loads(sm.read_text());ids=[r['symbol']for r in records]
    sids=['000001.SZ','000620.SZ','300319.SZ','688146.SH','301319.SZ','920808.BJ'];fp=P/'export/features.parquet';qp=P/'export/reference_quotes.parquet'
    ff=pq.ParquetFile(fp);qq=pq.ParquetFile(qp);assert ff.num_row_groups==qq.num_row_groups==1709
    f=pd.concat([ff.read_row_group(ids.index(s),columns=['sid','day','window','stock_source_row_present','source_segment']).to_pandas()for s in sids],ignore_index=True)
    q=pd.concat([qq.read_row_group(ids.index(s)).to_pandas()for s in sids],ignore_index=True)
    observed={};primary=P/'universe_audit/PRIMARY_CANDIDATES.jsonl'
    with primary.open()as stream:
        for l in stream:
            r=json.loads(l)
            if r['sid']in sids:observed.setdefault((r['window'],r['sid']),[]).append({k:r[k]for k in M.KEY})
    selected=[]
    for rs in observed.values():
        for j in sorted({0,len(rs)//2,len(rs)-1}):selected.append(rs[j])
    cals={}
    for w in ['2022_2024','strong']:
        p=P.parent/'trend_exit_controls_v1/runs/BASELINE'/w/'pair/daily.jsonl.gz'
        with gzip.open(p,'rt')as stream:cals[w]=[json.loads(l)['at'][:10]for l in stream]
        source[str(p)]=sha(p)
    _,checks=check(f,q,pd.DataFrame(selected),cals)
    for p in [fp,qp,primary,sm,P/'analysis/ANALYSIS_SCHEMA.json']:source[str(p)]=sha(p)
    assert sha(CODE)==source[str(CODE)]
    out=dict(status='PASS_LABEL_CLOCK_STATIC_AND_SMALL_SCALAR_ORACLE_WITH_LIMITS',synthetic_counterexamples=tests,real_primary_keys=len(selected),real_symbols=sids,real_label_checks=checks,source_sha256=source,script_sha256=sha(__file__),elapsed_seconds=time.monotonic()-start,
             limits=['Only10 synthetic boundary families and sampled real PRIMARY keys; not a full future-label table audit.','halt_status remainsNOT_RECORDED_UNKNOWN; missing/nonobserved is not exchange halt certification.','Endpoint returns may remain known with interior missing flags; max/min60 require all future60 actual valid CLOSEs.','Separate per-window calendar prevents long→strong jumps; annual groups must remain signal-date reporting only.'],new_accounts=0,new_full_label_exports=0)
    (O/'LABEL_CLOCK_FLAGS_V2_SMALL_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(out['status'],len(tests),len(selected),round(out['elapsed_seconds'],2),flush=True)
if __name__=='__main__':main()
