"""Bounded independent scalar/metadata audit; no account or order construction."""
from pathlib import Path
from collections import Counter
import hashlib,importlib.util,json,math,sys,time,difflib
import numpy as np,pandas as pd
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parents[1];R=Path(__file__).resolve().parent
def j(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def known(v):return pd.notna(v)
def binary(v):return known(v)and v in (0,1,False,True)
def scalar(f):
    rows=[];cl=[];ema=None;prev_valid=False;prev_source=None;block=0;run=0;last_block=-1;last_on=False;last_b=None;seen_i=False;alpha=2/21
    for idx,(day,r)in enumerate(f.iterrows()):
        c=float(r.close);source=r.segment_id;valid=math.isfinite(c)and c>0 and known(source)
        changed=(not valid or not prev_valid or source!=prev_source)
        if changed:block+=1;cl=[];ema=None
        previous_c=cl[-1]if cl else None;previous_e=ema if len(cl)>=20 else None;prior_high=max(cl[-20:])if len(cl)>=20 else None
        if valid:
            if ema is None:ema=c
            elif ema!=c:ema=(1-alpha)*ema+alpha*c
            e=ema if len(cl)+1>=20 else None
        else:e=None
        on=bool(valid and binary(r.e0_target)and r.e0_target==1)
        if block!=last_block or on!=last_on:run+=1;last_b=None;seen_i=False
        old_b=last_b;prior_i=seen_i
        floor=float(r.e0_floor)if known(r.e0_floor)else math.nan;floorok=math.isfinite(floor)and c>floor
        B=bool(on and floorok and prior_high is not None and previous_e is not None and c>prior_high and c>e and e>previous_e)
        P=bool(on and floorok and previous_e is not None and c>e and e>previous_e and previous_c<=previous_e and old_b is not None and 1<=idx-old_b<=20)
        ion=bool(valid and binary(r.i_target)and r.i_target==1);state='OUTSIDE_E0'
        if valid and not binary(r.e0_target):state='UNKNOWN_E0'
        elif on:
            if not binary(r.i_target):state='UNKNOWN_I'
            elif not ion:state='A2_I_previously_started_now_off'if prior_i else'A_I_never_started_in_E0'
            elif not binary(r.i_buy):state='UNKNOWN_I_BUY'
            else:state='C_original_i_buy'if r.i_buy==1 else'B_I_on_no_i_buy'
        rows.append(dict(day=day,ema20=e,ema20_previous=previous_e,previous_close=previous_c,prior20_high=prior_high,B=B,P=P,prior_b_index=old_b,state=state,price_block=block,e0_run=run,valid=valid,E0=on,I=ion))
        if B:last_b=idx
        seen_i|=ion
        if valid:cl.append(c)
        prev_valid=valid;prev_source=source;last_block=block;last_on=on
    return rows
def compare(z,ss):
    assert len(z)==len(ss)
    for (day,r),s in zip(z.iterrows(),ss):
        for k in ['B','P','state','price_block','e0_run','valid','E0','I']:assert r[k]==s[k],(str(day),k,r[k],s[k])
        for k in ['ema20','ema20_previous','previous_close','prior20_high','prior_b_index']:
            if s[k]is None:assert pd.isna(r[k]),(str(day),k)
            else:assert math.isclose(float(r[k]),float(s[k]),rel_tol=1e-12,abs_tol=1e-10),(str(day),k,r[k],s[k])
def forward(f,ss,i,h,stop):
    end=i+h
    if end>=len(f)or f.index[end]>stop or ss[end]['price_block']!=ss[i]['price_block']:return None
    c=float(f.iloc[i].close);v=[float(x)for x in f.close.iloc[i+1:end+1]]
    return dict(end_day=str(f.index[end].date()),close_return_pct=(v[-1]/c-1)*100,min_close_return_pct=(min(v)/c-1)*100,max_close_return_pct=(max(v)/c-1)*100)
def main():
    start=time.monotonic();source=j(O/'EVENT_SOURCE_SHA256.json');assert all(sha(p)==h for p,h in source.items())
    spec=importlib.util.spec_from_file_location('audited_P_census',O/'build_event_census.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    records=j(m.M);summary=j(O/'EVENT_CENSUS_SUMMARY.json');events={k:j(O/(k+'_EVENTS.json'))for k in ['B','P']};episodes=j(O/'ALL_A_GAP_EPISODES.json');assert len(records)==1709
    selected={records[i]['symbol']for i in [0,150,500,1000,1708]}|{'300666.SZ','301611.SZ','603061.SH','688146.SH'}
    selected_data={};unknown=Counter();raw=Counter();checks=[];future_checks=0;prefixes=0
    lookup={k:{(r['window'],r['sid'],r['day']):r for r in rs}for k,rs in events.items()}
    assert all(len(lookup[k])==len(events[k])for k in events)
    for record in records:
        assert time.monotonic()-start<60,'review read-only budget exceeded'
        sid=record['symbol'];f=pd.read_parquet(record['refs']['facts'],columns=['close','segment_id','e0_target','e0_floor','i_target','i_buy'])
        valid=np.isfinite(f.close.astype(float))&f.close.astype(float).gt(0)&f.segment_id.notna()
        unknown['valid_price_unknown_E0']+=int((valid&~f.e0_target.isin([0,1])).sum());unknown['E0_on_unknown_I']+=int((valid&f.e0_target.eq(1)&~f.i_target.isin([0,1])).sum());unknown['I_on_unknown_i_buy']+=int((valid&f.i_target.eq(1)&~f.i_buy.isin([False,True])).sum())
        for w,lo,hi in m.WINDOWS:
            mask=(f.index>=lo)&(f.index<=hi);raw[w+'_E0_on_I_off']+=int((mask&valid&f.e0_target.eq(1)&f.i_target.eq(0)).sum())
        if sid not in selected:continue
        s=scalar(f);z=m.compute(f);compare(z,s);selected_data[sid]=(f,s)
        for cut in ['2022-01-01','2024-09-30','2026-03-31']:
            small=f.loc[:cut];compare(m.compute(small),s[:len(small)]);prefixes+=1
        count={}
        for w,lo,hi in m.WINDOWS:
            for k in ['B','P']:
                expected={str(day.date())for day,v in zip(f.index,s)if lo<=str(day.date())<=hi and v[k]};saved={r['day']for r in events[k]if r['sid']==sid and r['window']==w};assert expected==saved,(sid,w,k)
                for day in expected:
                    r=lookup[k][w,sid,day];i=f.index.get_loc(day);assert r['state']==s[i]['state']
                    for h in [5,20,60]:
                        v=forward(f,s,i,h,pd.Timestamp(hi));a=r['future'][str(h)]
                        if v is None:assert a is None
                        else:
                            assert a['end_day']==v['end_day']
                            for field in ['close_return_pct','min_close_return_pct','max_close_return_pct']:assert math.isclose(a[field],v[field],abs_tol=1e-10)
                        future_checks+=1
                    if k=='P':
                        b=s[i]['prior_b_index'];assert r['breakout_day']==str(f.index[b].date())and r['breakout_age_observations']==i-b
                        touch=next(v for v in range(b+1,i+1)if float(f.close.iloc[v])<=s[v]['ema20']);assert r['first_EMA20_close_touch']==str(f.index[touch].date())
                count[w+'_'+k]=len(expected)
        checks.append(dict(sid=sid,full_warm_rows=len(f),event_counts=count))
    assert not any(unknown.values());assert raw['long_E0_on_I_off']==83396 and raw['strong_E0_on_I_off']==21572
    for g in summary['groups']:
        a=[r for r in events[g['event']]if r['window']==g['window']and r['state']==g['state']]
        assert (g['events'],g['stocks'],g['stock_source_E0_epochs'])==(len(a),len({r['sid']for r in a}),len({(r['sid'],r['source_segment'],r['e0_run_start'])for r in a}))
        for h in ['5','20','60']:
            v=[r['future'][h]for r in a if r['future'][h]is not None];x=g['future'][h];assert (x['known'],x['unknown'],x['negative_close_returns'],x['min_close_below_minus10pct'])==(len(v),len(a)-len(v),sum(r['close_return_pct']<0 for r in v),sum(r['min_close_return_pct']<=-10 for r in v))
            if v:
                assert math.isclose(x['mean_close_return_pct'],float(np.mean([r['close_return_pct']for r in v])),abs_tol=1e-12);assert math.isclose(x['median_close_return_pct'],float(np.median([r['close_return_pct']for r in v])),abs_tol=1e-12)
    assert len(episodes)==summary['A_gap_episodes']==13295;assert len({(r['window'],r['sid'],r['e0_run_start'])for r in episodes})==len(episodes)
    # Future missing-E0 support is a separate proposed implementation fix; do
    # not change the executed source, whose actual input exposure is zero.
    old=(O/'build_event_census.py').read_text();needle='on = valid & f.e0_target.eq(1)';assert old.count(needle)==1
    replacement='on = (valid & f.e0_target.eq(1).fillna(False)).astype(bool)';fixed=old.replace(needle,replacement)
    (R/'NULLABLE_E0_BOUNDARY_FIX.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),fixed.splitlines(True),fromfile='executed_source_unchanged',tofile='future_nullable_E0_fix_not_applied')))
    ns={'np':np,'pd':pd};import ast
    tree=ast.parse(fixed);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name=='compute');exec(compile(ast.Module(body=[node],type_ignores=[]),'proposed_nullable_fix','exec'),ns)
    idx=pd.bdate_range('2020-01-01',periods=96);cl=np.r_[np.repeat(10.,25),[11,12,13,14,15,16,17,16,15,14,8,14,15],np.repeat(16.,58)]
    f=pd.DataFrame(dict(close=cl,segment_id=pd.Series([0]*65+[1]*31,index=idx,dtype='Int64'),e0_target=pd.Series([1]*96,index=idx,dtype='Int64'),e0_floor=pd.Series([5.]*96,index=idx,dtype='Float64'),i_target=pd.Series([0]*96,index=idx,dtype='Int64'),i_buy=pd.Series([False]*96,index=idx,dtype='boolean')),index=idx)
    f.loc[idx[53],'close']=np.nan;f.loc[idx[69],'segment_id']=pd.NA;f.loc[idx[81],'e0_target']=pd.NA;f.loc[idx[46],'e0_target']=0;f.loc[idx[40:46],'i_target']=1;f.loc[idx[42],'i_target']=pd.NA;f.loc[idx[43],'i_buy']=pd.NA
    compare(ns['compute'](f),scalar(f));assert len(ns['compute'](f.iloc[:0]))==0
    assert m.compute(f.iloc[:0]).prior_b_index.dtype==np.dtype('float64')
    result=dict(passed=True,status='PASS_EXECUTED_EVENT_CENSUS_WITH_UNEXPOSED_NULLABLE_E0_FIX_PENDING',scope='Executed actual complete-input events and labels only; no financial authority.',executed_source_sha256=sha(O/'build_event_census.py'),source_hashes=len(source),stocks_with_raw_unknown_check=1709,raw_unknown_counts=dict(unknown),raw_E0_on_I_off=dict(raw),independent_scalar_stocks=len(checks),independent_scalar_rows=sum(r['full_warm_rows']for r in checks),scalar_checks=checks,independent_physical_prefix_checks=prefixes,independently_checked_forward_labels=future_checks,all_saved_event_summary_groups_exact=True,A_gap_episodes=13295,synthetic_source_price_invalid_empty_and_nullable_corrected=True,nullable_fix_applied_to_executed_source=False,nullable_gap_actual_exposure=0,seconds=time.monotonic()-start,accounts=0,authorizations=0,remaining_before_account=['Apply separately reviewed missing-E0 continuation reset fix before any future implementation; current complete actual-input census is unaffected.','Review all-B and per-E0 first-B waiting/unknown postprocess; event presence is not S0 or funding permission.','Freeze A entry plus holding/exit/epoch contract independently if pursuing I-off; no original CORE permission is inferred.'])
    (R/'PRICE_EVENT_CENSUS_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='scalar_checks'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
