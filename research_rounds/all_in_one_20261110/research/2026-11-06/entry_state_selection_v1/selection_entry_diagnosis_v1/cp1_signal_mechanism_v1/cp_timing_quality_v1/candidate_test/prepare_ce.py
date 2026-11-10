"""One frozen CP formation-time score. Cache-only; no future labels/model/account runs."""
from pathlib import Path
from collections import Counter
import sys,json,math,hashlib,time,traceback
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
B=O.parents[2]/'mobile_candidate_response_v1'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
MODEL=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
CUTS=['2022-03-31','2024-09-24','2026-01-15'];KEY=['account','day','sid']
FLOOR=math.log(1.001)**2
RESET_START={'start','E0_down_reset','lower_anchor'}
RESET_OFF={'unprepared','E0_invalid','source_reset'}
CASES=[('600056.SH','2022-03-03'),('600056.SH','2022-03-30'),('002385.SZ','2022-03-04'),('300182.SZ','2022-01-04'),('600606.SH','2022-03-22'),('601607.SH','2022-03-24'),('688582.SH','2024-07-29'),('000506.SZ','2024-10-15')]
COLS=['CE','variance_budget','formation_n','prior_valid_r_n','sigma_recent','sigma_frozen','anchor_index','credit_rebuilt','displacement_rebuilt','V_next','n_next','anchor_next_index']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
def prior_variance(r,seg):
    out=np.full(len(r),np.nan);counts=np.zeros(len(r),int)
    starts=np.r_[0,np.flatnonzero(seg[1:]!=seg[:-1])+1];ends=np.r_[starts[1:],len(r)]
    for lo,hi in zip(starts,ends):
        a=r[lo:hi];valid=np.isfinite(a);n=np.cumsum(valid)-valid
        counts[lo:hi]=np.minimum(n,21)
        means=pd.Series(a[valid]**2).rolling(21,min_periods=21).mean().to_numpy()
        where=np.flatnonzero(n>=21)
        if len(where):out[lo+where]=np.maximum(means[n[where]-1],FLOOR)
    return out,counts

def calc(cp,seg,audit=False):
    r=cp.r.to_numpy();m=cp.m.to_numpy();delta=cp.delta_frontier.to_numpy()
    credit=cp.credit.to_numpy();disp=cp.displacement.to_numpy();scale=cp.scale.to_numpy()
    anchor=cp.anchor.to_numpy();nanchor=cp.next_anchor.to_numpy();nscale=cp.next_scale.to_numpy()
    reason=cp.reset_reason.fillna('').to_numpy();receipt=cp.receipt.to_numpy();ready=cp.ready.to_numpy();ev=cp.e0_valid.to_numpy()
    v2,priorn=prior_variance(r,seg);out=np.full((len(cp),len(COLS)),np.nan)
    active=False;V=0.;n=0;ai=-1;cc=dd=0.;oldseg=None
    cnt=Counter();max_credit_error=max_D_error=max_anchor_error=max_scale_error=0.;pullback_rows=0
    for j in range(len(cp)):
        change=oldseg is None or seg[j]!=oldseg
        if change:
            active=False;V=0.;n=0;ai=-1;cc=dd=0.;cnt['source_change']+=1;oldseg=seg[j]
        rr=reason[j];cnt[str(rr) or 'ordinary']+=1
        if rr in RESET_OFF or not ready[j] or not ev[j]:
            active=False;V=0.;n=0;ai=-1;cc=dd=0.
        elif rr in RESET_START:
            active=True;V=0.;n=0;ai=j;cc=dd=0.
        else:
            if not active:raise AssertionError(('missing original formation boundary',str(cp.index[j]),rr))
            n+=1;V=math.fsum((V,float(v2[j])))
            if delta[j]>0:cc=math.fsum((cc,float(delta[j]*m[j])));dd=math.fsum((dd,float(delta[j])))
            if audit:
                assert n==j-ai
                ae=abs(float(anchor[j]-nanchor[ai]));se=abs(float(scale[j]-nscale[ai]))
                max_anchor_error=max(max_anchor_error,ae);max_scale_error=max(max_scale_error,se)
                assert ae<1e-12 and se<1e-12,(str(cp.index[j]),'anchor/scale lineage',ai,ae,se)
                if delta[j]==0:pullback_rows+=1
        if audit:
            ce=abs(float(credit[j]-cc));max_credit_error=max(max_credit_error,ce)
            assert ce<1e-12,(str(cp.index[j]),'credit clock',credit[j],cc)
            if np.isfinite(disp[j]):
                de=abs(float(disp[j]-dd));max_D_error=max(max_D_error,de)
                assert de<1e-12,(str(cp.index[j]),'D clock',disp[j],dd)
            if receipt[j]:assert rr=='receipt_consumed' and active and n>0 and delta[j]>0
        score=min(float(disp[j]),float(credit[j]))/math.sqrt(V) if receipt[j] and np.isfinite(V) and V>0 else math.nan
        out[j,:9]=[score,V,n,priorn[j],math.sqrt(v2[j]) if np.isfinite(v2[j]) else math.nan,scale[j],ai,cc,dd]
        if receipt[j]:
            # Consume only after publishing current certificate score.
            active=True;V=0.;n=0;ai=j;cc=dd=0.
        out[j,9:]=[V,n,ai]
    stats=dict(observations=len(cp),receipts=int(receipt.sum()),ordinary_zero_frontier_rows= pullback_rows,max_credit_error=max_credit_error,max_displacement_error=max_D_error,max_anchor_lineage_error=max_anchor_error,max_frozen_scale_error=max_scale_error,reset_counts=dict(cnt))
    return out,stats

def order(g):
    base=g.sort_values(['original_priority_rank','sid']);indices=list(base.index)
    eligible=base[base.slot_replaceable].copy();eligible['ce_round12']=eligible.CE.round(12);eligible['pvr_round12']=eligible.original_PVR.round(12)
    eligible=eligible.sort_values(['ce_round12','pvr_round12','original_priority_rank','sid'],ascending=[False,False,True,True])
    it=iter(eligible.index);alt=[next(it) if base.at[i,'slot_replaceable'] else i for i in indices]
    assert set(indices)==set(alt)
    assert all(i==alt[j] for j,i in enumerate(indices) if not base.at[i,'slot_replaceable'])
    return indices,alt

def synthetic_tests():
    # Audit only the new bookkeeping, not any reimplemented CP indicator.
    c=pd.DataFrame(dict(r=[.01]*24,m=[1.]*24,delta_frontier=[0.]*24,credit=[0.]*24,displacement=[np.nan]*24,scale=[.01]*24,anchor=[1.]*24,next_anchor=[1.]*24,next_scale=[.01]*24,reset_reason=['unprepared']*21+['start','','receipt_consumed'],receipt=[False]*23+[True],ready=[False]*21+[True]*3,e0_valid=[True]*24),index=pd.bdate_range('2020-01-01',periods=24))
    c.iloc[22,c.columns.get_loc('displacement')]=0
    c.iloc[23,c.columns.get_loc('delta_frontier')]=.03;c.iloc[23,c.columns.get_loc('credit')]=.03;c.iloc[23,c.columns.get_loc('displacement')]=.03
    c.iloc[23,c.columns.get_loc('next_anchor')]=1.03
    a,_=calc(c,np.zeros(24),True);assert a[-1,2]==2 and abs(a[-1,1]-.0002)<1e-15 and abs(a[-1,0]-.03/math.sqrt(.0002))<1e-12 and a[-1,9]==0
    poisoned=c.copy();poisoned.iloc[-1,poisoned.columns.get_loc('r')]=.9;b,_=calc(poisoned,np.zeros(24),True);assert np.array_equal(a[-1],b[-1],equal_nan=True)
    rv,n=prior_variance(np.array([.01]*23),np.array([0]*22+[1]));assert np.isnan(rv[-1]) and n[-1]==0
    rv,n=prior_variance(np.array([0.]*22),np.zeros(22));assert rv[-1]==FLOOR
    return dict(passed=True,tests=['anchor day excludes budget','ordinary pullback accumulates budget and n','current receipt evaluated before consumption','current r excluded from same-day v','source change clears variance history','economic variance floor'])

def main():
    start=time.monotonic()
    freeze=dict(name='CP formation-time normalized evidence CE',formula='v_j^2=max(mean(last 21 finite same-source r strictly before j squared), log(1.001)^2); V_t=sum(v_j^2 from observation after actual original CP anchor through t); CE=min(original displacement,original credit)/sqrt(V_t), on original fresh receipt only.',history='Require 21 prior same-source valid r for v. Insufficient history is UNKNOWN, no filling. Original CP readiness normally requires 63, independently retained.',clock='Reset V/n on original start/E0_down_reset/lower_anchor/E0_invalid/unprepared/source change. Anchor day excluded; ordinary pullback accumulates. Compute receipt CE before consumption, then reset V/n at original new anchor. No n cap, threshold, delay, old certificate revival, or new CP.',ranking='Original priority then sid; same K=min(20,N). Only finite CE AND original PVR slots are permutable: CE.round(12) descending, original_PVR.round(12) descending, original_priority_rank then sid. CE unknown and 91 original PVR-unknown slots retain exact original position.',domain='All original 103766 legal EMPTY MOBILE candidates, never filter i_buy or accepted, PVR and E31 separately.',interpretation='Amplitude-duration normalized evidence; not a probability, p-value, or account return.',validation='Compare actual original credit/displacement incremental lineage, anchor and frozen-scale identity. Complete truncated-input prefix checks at all three cutoffs. No original model or account run.',cases=CASES,prefix_cutoffs=CUTS,parameter_scans=0,labels_read=False,all_history_previously_consumed_development=True)
    dump('FORMULA_FREEZE.json',freeze);dump('SYNTHETIC_TESTS.json',synthetic_tests())
    c=pd.read_parquet(B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');assert len(c)==103766 and not c.duplicated(KEY).any()
    assert c.groupby('account').size().to_dict()=={'E31':50645,'PVR':53121}
    manifest={x['symbol']:x for x in json.loads(M.read_text())}
    source={str(p):sha(p) for p in [M,B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',B/'SEALED_SAME_K_SELECTIONS.parquet',MODEL,Path(__file__)]};dump('SOURCE_BEFORE_SCORES.json',source)
    parts=[];tests=[];hashes=[];audits=[];cases=[];traces=[]
    cpcols=['r','m','s','z','scale','anchor','frontier','delta_frontier','credit','displacement','receipt','reset_reason','next_anchor','next_scale','next_credit','ready','e0_valid']
    for no,(sid,g) in enumerate(c[['sid','day']].drop_duplicates().groupby('sid',sort=True)):
        ref=manifest[sid]['refs'];paths=[Path(ref['CP1']),Path(ref['facts'])];before={str(p):sha(p) for p in paths}
        cp=pd.read_parquet(paths[0],columns=cpcols);f=pd.read_parquet(paths[1],columns=['segment_id','i_buy'])
        assert cp.index.equals(f.index) and cp.index.is_unique and cp.index.is_monotonic_increasing
        seg=f.segment_id.to_numpy();a,stat=calc(cp,seg,True);audits.append(dict(sid=sid,**stat))
        for cut in CUTS:
            stop=int(cp.index.searchsorted(pd.Timestamp(cut),side='right'))
            small,_=calc(cp.iloc[:stop],seg[:stop]) if stop else (a[:0],{})
            assert np.array_equal(a[:stop],small,equal_nan=True),(sid,cut,'prefix')
            tests.append(dict(sid=sid,cutoff=cut,full_observations=len(cp),prefix_observations=stop,all_state_columns_exact=True))
        dates=pd.DatetimeIndex(g.day);loc=cp.index.get_indexer(dates);assert (loc>=0).all();assert cp.receipt.to_numpy()[loc].all()
        z=g.copy();z[COLS]=a[loc];z['source_i_buy']=f.i_buy.to_numpy()[loc];z['source_receipt']=cp.receipt.to_numpy()[loc]
        z['source_r']=cp.r.to_numpy()[loc];z['source_m']=cp.m.to_numpy()[loc];z['source_s']=cp.s.to_numpy()[loc];z['source_z']=cp.z.to_numpy()[loc];z['source_displacement']=cp.displacement.to_numpy()[loc];z['source_credit']=cp.credit.to_numpy()[loc]
        z['formation_anchor_day']=[str(cp.index[int(j)].date()) if j>=0 else None for j in z.anchor_index]
        z['CE_known']=np.isfinite(z.CE);z['short_history']=z.prior_valid_r_n.lt(21);parts.append(z)
        for ss,day in CASES:
            if sid!=ss:continue
            ix=cp.index.get_loc(pd.Timestamp(day));row=dict(sid=sid,day=day,**dict(zip(COLS,a[ix])),source_s=cp.s.iloc[ix],source_z=cp.z.iloc[ix],source_r=cp.r.iloc[ix],source_m=cp.m.iloc[ix],source_credit=cp.credit.iloc[ix],source_displacement=cp.displacement.iloc[ix],source_receipt=bool(cp.receipt.iloc[ix]),original_anchor=cp.anchor.iloc[ix],formation_anchor_day=str(cp.index[int(a[ix,6])].date()),legal_candidate_accounts=c[(c.sid==sid)&(c.day==day)].account.tolist())
            row['recent_to_frozen_sigma']=row['sigma_recent']/row['sigma_frozen'];cases.append(row)
            lo=max(0,ix-21);tt=cp.iloc[lo:ix+1].copy().reset_index().rename(columns={'date':'day'});tt['sid']=sid;tt['case_day']=day;tt[COLS]=a[lo:ix+1];traces.append(tt)
        for path,h in before.items():
            assert sha(path)==h;expected=manifest[sid].get('output_sha256',{}).get(path);assert expected is None or h==expected
            hashes.append(dict(sid=sid,path=path,sha256=h,manifest_expected=expected,unchanged=True))
        if (no+1)%200==0:print('SCORED',no+1,'seconds',round(time.monotonic()-start,1),flush=True)
    scores=pd.concat(parts,ignore_index=True);sc=c.merge(scores,on=['sid','day'],validate='many_to_one');sc['slot_replaceable']=sc.CE_known & np.isfinite(sc.original_PVR)
    assert len(sc)==103766 and len(scores)==54852 and sc.sid.nunique()==1631 and len(cases)==8
    sc.to_parquet(O/'CANDIDATE_CE.parquet',index=False);pd.DataFrame(tests).to_csv(O/'PREFIX_TESTS.csv',index=False);pd.DataFrame(hashes).to_csv(O/'CACHE_SOURCE_AUDIT.csv',index=False);dump('CLOCK_AUDIT_BY_STOCK.json',audits)
    pd.DataFrame(cases).to_csv(O/'FIXED_EIGHT_CASES.csv',index=False);pd.concat(traces,ignore_index=True).to_csv(O/'FIXED_CASE_PRE_SIGNAL_TRACES.csv',index=False)
    coverage=sc.groupby(['account','year']).agg(candidates=('sid','size'),known=('CE_known','sum'),short_history=('short_history','sum'),i_buy_false=('source_i_buy',lambda x:int((~x).sum())),median_formation_n=('formation_n','median'),max_formation_n=('formation_n','max')).reset_index();coverage['unknown']=coverage.candidates-coverage.known;coverage.to_csv(O/'SCORE_COVERAGE_BY_YEAR.csv',index=False)
    # Seal full queues and same-K selection, then verify old baseline without future labels.
    selections=[];moves=[];queues=[]
    for (account,day),g in sc.groupby(['account','day'],sort=True):
        base,alt=order(g);k=min(20,len(base));bp={i:j+1 for j,i in enumerate(base)};ap={i:j+1 for j,i in enumerate(alt)}
        for strategy,ix in [('ORIGINAL_PVR',base[:k]),('CP_TIMING_CE',alt[:k])]:
            z=sc.loc[ix].copy();z['strategy']=strategy;z['selected_rank']=range(1,len(z)+1);selections.append(z)
        for i in base:moves.append(dict(account=account,day=day,sid=sc.at[i,'sid'],year=sc.at[i,'year'],epoch=sc.at[i,'epoch'],CP1_id=sc.at[i,'CP1_id'],original_rank=bp[i],CE_rank=ap[i],K=k,CE=sc.at[i,'CE'],original_PVR=sc.at[i,'original_PVR'],CE_known=sc.at[i,'CE_known'],original_selected=bp[i]<=k,CE_selected=ap[i]<=k))
        queues.append(dict(account=account,day=day,year=g.year.iloc[0],N=len(base),K=k,CE_known=int(g.CE_known.sum()),CE_unknown=int((~g.CE_known).sum()),PVR_unknown=int((~np.isfinite(g.original_PVR)).sum()),top_overlap=len(set(base[:k])&set(alt[:k])),added=len(set(alt[:k])-set(base[:k]))))
    selected=pd.concat(selections,ignore_index=True);assert selected.groupby(['account','day','strategy']).size().unstack().nunique(axis=1).eq(1).all()
    old=pd.read_parquet(B/'SEALED_SAME_K_SELECTIONS.parquet',columns=['account','day','selected_rank','sid','CP1_id','strategy']);cols=['account','day','selected_rank','sid','CP1_id']
    base=selected[selected.strategy=='ORIGINAL_PVR'][cols].sort_values(cols[:3]).reset_index(drop=True);prior=old[old.strategy=='ORIGINAL_PVR'][cols].sort_values(cols[:3]).reset_index(drop=True);pd.testing.assert_frame_equal(base,prior,check_dtype=False);assert len(base)==27990
    selected.to_parquet(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet',index=False);pd.DataFrame(moves).to_parquet(O/'FULL_QUEUE_ORDERS.parquet',index=False);pd.DataFrame(queues).to_csv(O/'QUEUE_COUNTS.csv',index=False)
    seal=dict(score_sha256=sha(O/'CANDIDATE_CE.parquet'),selections_sha256=sha(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet'),script_sha256=sha(__file__),rank_columns=['CE','CE_known','original_PVR','original_priority_rank','sid'],future_labels_read=False,all_equal_K=True,baseline_exact_rows=len(base));dump('RANK_SEAL.json',seal)
    for p,h in source.items():assert sha(p)==h
    out=dict(status='SCORED_AND_SEALED_WAITING_FOR_EVALUATION',candidate_rows=len(sc),unique_stock_days=len(scores),stocks=sc.sid.nunique(),known=int(sc.CE_known.sum()),unknown=int((~sc.CE_known).sum()),PVR_unknown_fixed_slots=int((~np.isfinite(sc.original_PVR)).sum()),replaceable=int(sc.slot_replaceable.sum()),short_history=int(sc.short_history.sum()),false_i_buy_preserved=int((~sc.source_i_buy).sum()),prefix_checks=len(tests),full_cache_observations=sum(x['observations'] for x in audits),all_cache_credit_clock_verified=True,max_credit_error=max(x['max_credit_error'] for x in audits),max_displacement_error=max(x['max_displacement_error'] for x in audits),max_anchor_lineage_error=max(x['max_anchor_lineage_error'] for x in audits),max_frozen_scale_error=max(x['max_frozen_scale_error'] for x in audits),baseline_rows=len(base),seconds=time.monotonic()-start,labels_read=False,original_indicator_runs=0,account_runs=0,parameter_scans=0)
    dump('SCORE_COVERAGE.json',out);print(json.dumps(out,ensure_ascii=False));print(pd.DataFrame(cases)[['sid','day','CE','formation_n','formation_anchor_day','sigma_frozen','sigma_recent','recent_to_frozen_sigma']].to_string(index=False))
if __name__=='__main__':
    try:main()
    except Exception:
        (O/('TECHNICAL_FAILURE_'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc());raise
