"""Frozen six-case conditional arithmetic only. Does not import strategy/account code."""
from pathlib import Path
import hashlib,json,math,datetime
import numpy as np,pandas as pd
OUT=Path(__file__).resolve().parent
FD=OUT/'FROZEN_DEFINITION.json'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen_hash=digest(FD)
definition=json.loads(FD.read_text())
assert all(digest(p)==h for p,h in definition['source_sha256'].items())
BASE=OUT.parent
original=pd.read_csv(BASE/'ANCHOR_TO_SIGNAL_DAILY.csv')
frames={}; diagnostics=[]; cohort_rows=[]; top_rows=[]; overlap_rows=[]; daily=[]; extensions=[]; summary=[]; tests=[]

def build(sid):
    refs=definition['source_refs'][sid]
    f=pd.read_parquet(refs['facts']);c=pd.read_parquet(refs['CP1']);inp=pd.read_parquet(refs['CP1_input'])
    raw=pd.read_parquet(refs['raw']).set_index('trade_date');raw.index=pd.to_datetime(raw.index)
    assert inp.index.is_unique and inp.index.is_monotonic_increasing and not inp.index.hasnans
    assert c.index.is_unique and c.index.is_monotonic_increasing and inp.index.isin(c.index).all()
    cp_extra_dates=c.index.difference(inp.index)
    c=c.reindex(inp.index)
    x=inp.copy();x['factor']=f.factor.reindex(inp.index)
    for k in ['open','high','low','close']:
        x['raw_'+k]=raw[k].reindex(inp.index)
        x[k]=x['raw_'+k]*x.factor
    assert np.allclose(x.close,inp.close,rtol=1e-12,atol=1e-12)
    assert np.allclose(x.close,f.close.reindex(inp.index),rtol=1e-12,atol=1e-12)
    assert np.array_equal(raw.amount.reindex(inp.index).to_numpy(),inp.amount.to_numpy())
    for k in c:x['cp_'+k]=c[k]
    x['i_target']=f.i_target.reindex(inp.index);x['i_buy']=f.i_buy.reindex(inp.index)
    blocks=x.segment_id[x.segment_id.ne(x.segment_id.shift())]
    assert not blocks.duplicated().any()
    x['position']=x.groupby('segment_id',sort=False).cumcount()
    x['ohlc_complete']=np.isfinite(x[['open','high','low','close','amount']]).all(axis=1)&x[['open','high','low','close','amount']].gt(0).all(axis=1)
    x['ohlc_ordered']=(x.high>=x[['open','close','low']].max(axis=1))&(x.low<=x[['open','close','high']].min(axis=1))
    x['B_z_known']=np.isfinite(x[['cp_B','cp_z']]).all(axis=1)&x[['cp_B','cp_z']].gt(0).all(axis=1)
    x['eligible']=x.ohlc_complete&x.ohlc_ordered&x.B_z_known
    x['q']=x.amount/x.cp_B;x['p']=np.log(x.close);x['h']=np.log(x.high);x['l']=np.log(x.low)
    for seg,g in x.groupby('segment_id',sort=False):
        B=g.amount.shift().rolling(21,min_periods=21).median()
        z=g.p.diff().abs().shift().rolling(63,min_periods=63).median().mul(1.4826).clip(lower=1e-8).clip(lower=math.log1p(.001))
        assert np.allclose(B,g.cp_B,rtol=1e-12,atol=1e-12,equal_nan=True)
        assert np.allclose(z,g.cp_z,rtol=1e-12,atol=1e-12,equal_nan=True)
        eg=g[g.eligible]
        diagnostics.append({'sid':sid,'segment_id':str(seg),'segment_first_date':str(g.index[0].date()),'segment_last_date':str(g.index[-1].date()),'original_observations':len(g),'first_B_date':str(g[g.cp_B.notna()].index[0].date()) if g.cp_B.notna().any() else None,'first_z_date':str(g[g.cp_z.notna()].index[0].date()) if g.cp_z.notna().any() else None,'first_eligible_cohort_date':str(eg.index[0].date()) if len(eg) else None,'unavailable_warmup_B_or_z_rows':int((~g.B_z_known).sum()),'missing_or_invalid_OHLC_amount_rows':int((~g.ohlc_complete|~g.ohlc_ordered).sum()),'eligible_cohorts':len(eg),'eligible_despite_E0_invalid':int((g.eligible&~g.e0_valid).sum()),'eligible_despite_I_invalid':int((g.eligible&(g.i_target<=0)).sum()),'source_segment_resets':int(g.index[0]!=x.index[0]),'CP_rows_outside_input_count':len(cp_extra_dates),'CP_extra_dates_outside_input':';'.join(str(d.date()) for d in cp_extra_dates),'B_strict_prior21_verified':True,'z_strict_prior63_verified':True})
    return x

for sid in sorted(definition['source_refs']):frames[sid]=build(sid)

def contributions(x,t,ad,case_id,phase):
    cur=x.loc[t];hist=x.loc[x.index<t]
    same=hist.segment_id==cur.segment_id
    h=hist[same&hist.eligible].copy()
    if h.empty:raise RuntimeError('No eligible historical cohort: unavailable, not zero')
    age=cur.position-h.position
    assert (age>0).all()
    h['age']=age;h['w']=np.exp(-age/21);h['wq']=h.w*h.q
    h['b']=np.clip((cur.p-h.h)/h.cp_z,0,1);h['d']=np.clip((h.l-cur.p)/h.cp_z,0,1)
    h['post_anchor']=h.index>ad
    h['positive']=h.wq*h.b*h.post_anchor;h['negative']=h.wq*h.d
    h['unknown_in_interval']=(h.l<=cur.p)&(cur.p<=h.h)
    h['unknown_interval_mass']=h.wq*h.unknown_in_interval
    h['unclassified_fractional_mass']=h.wq*(1-h.b-h.d)
    P=math.fsum(h.positive);N=math.fsum(h.negative);U=math.fsum(h.unknown_interval_mass)
    # Independent strict-prefix scalar implementation; original CP features are inputs, never rerun CP.
    px=x.loc[:t];pp=[];nn=[];uu=[];cohort_dates=[]
    for d,r in px.iterrows():
        if d>=t or r.segment_id!=cur.segment_id or not r.eligible:continue
        age0=int(px.loc[t,'position']-r.position);v=math.exp(-age0/21)*(r.amount/r.cp_B)
        b=max(0.,min(1.,(px.loc[t,'p']-r.h)/r.cp_z));dd=max(0.,min(1.,(r.l-px.loc[t,'p'])/r.cp_z))
        pp.append(v*b if d>ad else 0.);nn.append(v*dd);uu.append(v if r.l<=px.loc[t,'p']<=r.h else 0.);cohort_dates.append(d)
    assert cohort_dates==list(h.index)
    assert math.isclose(P,math.fsum(pp),rel_tol=1e-12,abs_tol=1e-12)
    assert math.isclose(N,math.fsum(nn),rel_tol=1e-12,abs_tol=1e-12)
    assert math.isclose(U,math.fsum(uu),rel_tol=1e-12,abs_tol=1e-12)
    prefix={'case_id':case_id,'date':str(t.date()),'phase':phase,'eligible_history_count':len(h),'history_first_date':str(h.index[0].date()),'first_raw_source_date':str(x[x.segment_id==cur.segment_id].index[0].date()),'history_E0_invalid_cohorts':int((~h.e0_valid).sum()),'history_I_invalid_cohorts':int((h.i_target<=0).sum()),'excluded_warmup_prior_rows':int((same&~hist.B_z_known).sum()),'excluded_OHLC_prior_rows':int((same&(~hist.ohlc_complete|~hist.ohlc_ordered)).sum()),'P':P,'N':N,'A':P-N,'candidate_A_ge_1':P-N>=1,'unknown_interval_mass_all':U,'unknown_interval_mass_post_anchor':math.fsum(h.loc[h.post_anchor,'unknown_interval_mass']),'unclassified_fractional_mass_all':math.fsum(h.unclassified_fractional_mass),'eligible_history_wq_total':math.fsum(h.wq),'post_anchor_wq_total':math.fsum(h.loc[h.post_anchor,'wq']),'N_age_over_12':math.fsum(h.loc[h.age>12,'negative']),'max_positive_contribution':float(h.positive.max()),'max_negative_contribution':float(h.negative.max()),'max_q':float(h.q.max()),'prefix_consistent':True,'current_bar_contribution':0.0}
    for metric in ['positive','negative','q']:
        top=h.sort_values(metric,ascending=False,kind='stable').head(3)
        for rank,(d,r) in enumerate(top.iterrows(),1):
            if metric!='q' and float(r[metric])<=0:continue
            top_rows.append(dict(case_id=case_id,date=str(t.date()),phase=phase,metric=metric,rank=rank,cohort_date=str(d.date()),**{k:float(r[k]) for k in ['open','high','low','close','raw_open','raw_high','raw_low','raw_close','amount','cp_B','cp_z','q','age','w','wq','b','d','positive','negative']},post_anchor=bool(r.post_anchor)))
        top0=top.iloc[0]
        prefix['max_'+metric+'_date']=str(top.index[0].date()) if metric=='q' or top0[metric]>0 else None
        if metric!='q':prefix['max_'+metric+'_share']=float(top0[metric])/(P if metric=='positive' else N) if (P if metric=='positive' else N)>0 else None
    if phase=='original_window':
        keep=['open','high','low','close','raw_open','raw_high','raw_low','raw_close','amount','cp_B','cp_z','q','age','w','wq','b','d','positive','negative','post_anchor','unknown_interval_mass','unclassified_fractional_mass']
        for d,r in h.iterrows():
            cohort_rows.append(dict(case_id=case_id,date=str(t.date()),cohort_date=str(d.date()),**{k:(bool(r[k]) if k=='post_anchor' else float(r[k])) for k in keep}))
    return prefix,h

for case in definition['cases']:
    sid=case['sid'];t=pd.Timestamp(case['signal_day']);ad=pd.Timestamp(case['anchor_day']);x=frames[sid];case_id=sid+'_'+case['signal_day']
    cur=x.loc[t];anchor=float(cur.cp_anchor);scale=float(cur.cp_scale);T=math.sqrt(5)*scale
    assert math.isclose(x.loc[ad,'p'],anchor,rel_tol=1e-12,abs_tol=1e-12)
    assert math.isclose(x.loc[ad,'cp_next_anchor'],anchor,rel_tol=1e-12,abs_tol=1e-12)
    assert x.loc[ad:t,'segment_id'].nunique()==1
    prior=anchor
    for day,r in x.loc[ad:t].iterrows():
        fresh=max(r.p-prior,0.) if day>ad else 0.;frontier=max(prior,r.p);D=frontier-anchor
        o=original[(original.sid==sid)&(original.case_signal_day==case['signal_day'])&(original.date==str(day.date()))].iloc[0]
        assert math.isclose(D,o.window_D_log,rel_tol=1e-11,abs_tol=1e-12)
        assert math.isclose(fresh,o.window_delta_frontier_log,rel_tol=1e-11,abs_tol=1e-12)
        a,h=contributions(x,day,ad,case_id,'original_window')
        a.update(sid=sid,original_signal_day=case['signal_day'],original_anchor_day=case['anchor_day'],preselected_label=case['preselected_label'],anchor_basis_row=day==ad,open=float(r.open),high=float(r.high),low=float(r.low),close=float(r.close),raw_open=float(r.raw_open),raw_high=float(r.raw_high),raw_low=float(r.raw_low),raw_close=float(r.raw_close),amount=float(r.amount),B=float(r.cp_B),z=float(r.cp_z),q_today=float(r.q),D=D,T=T,D_over_T=D/T,fresh=fresh,price_gate=D>=T and fresh>0,candidate_joint_confirmation=D>=T and fresh>0 and a['candidate_A_ge_1'],original_I_valid=bool(r.i_target>0),original_i_buy=bool(r.i_buy),original_receipt=bool(r.cp_receipt),original_reset_reason=str(r.cp_reset_reason))
        daily.append(a);prior=frontier
    signal_a=dict(a)
    assert bool(cur.cp_receipt)
    if sid=='600056.SH':assert a['P']==0. and a['A']<=0
    # Diagnostic only: pairs among the ten largest decayed exposures at signal, ranked by overlap/union.
    candidates=h.sort_values('wq',ascending=False).head(10)
    pairs=[]
    for j in range(len(candidates)):
        for k in range(j):
            a0=candidates.iloc[k];b0=candidates.iloc[j]
            lo=max(a0.low,b0.low);hi=min(a0.high,b0.high);union=max(a0.high,b0.high)-min(a0.low,b0.low)
            if hi>lo and union>0:
                pairs.append((float((hi-lo)/union),k,j,lo,hi))
    if pairs:
        ratio,k,j,lo,hi=max(pairs);a0=candidates.iloc[k];b0=candidates.iloc[j]
        overlap_rows.append(dict(case_id=case_id,date_a=str(candidates.index[k].date()),date_b=str(candidates.index[j].date()),native_low_a=float(a0.low),native_high_a=float(a0.high),native_low_b=float(b0.low),native_high_b=float(b0.high),intersection_low=lo,intersection_high=hi,intersection_over_union=ratio,q_a=float(a0.q),q_b=float(b0.q),wq_a=float(a0.wq),wq_b=float(b0.wq),P_a=float(a0.positive),P_b=float(b0.positive),N_a=float(a0.negative),N_b=float(b0.negative)))
    # Freeze original alpha and scale after the signal, while visibly ignoring original receipt consumption.
    receipt_ignored=1;first_A=t if signal_a['candidate_A_ge_1'] else None;first_joint=t if signal_a['candidate_joint_confirmation'] else None
    stop_day=None;stop_reason=None;postrows=[]
    for day,r in x.loc[x.index>t].iterrows():
        reason=[]
        if r.segment_id!=cur.segment_id:reason.append('source_changed')
        if r.i_target<=0:reason.append('I_invalid')
        if not r.e0_valid:reason.append('E0_invalid')
        if r.e0_down:reason.append('native_E0_down')
        if str(r.cp_reset_reason) in ['lower_anchor','E0_down_reset']:reason.append('original_CP_'+str(r.cp_reset_reason))
        if reason:stop_day=day;stop_reason=';'.join(reason);break
        fresh=max(r.p-prior,0.);frontier=max(prior,r.p);D=frontier-anchor
        a,hx=contributions(x,day,ad,case_id,'fixed_anchor_extension')
        if first_A is None and a['candidate_A_ge_1']:first_A=day
        if first_joint is None and a['candidate_A_ge_1'] and D>=T and fresh>0:first_joint=day
        a.update(sid=sid,original_signal_day=case['signal_day'],original_anchor_day=case['anchor_day'],observations_after_original_signal=int(r.position-cur.position),D=D,T=T,D_over_T=D/T,fresh_fixed_anchor=fresh,price_gate_fixed_anchor=D>=T and fresh>0,candidate_joint_confirmation_fixed_anchor=D>=T and fresh>0 and a['candidate_A_ge_1'],original_I_valid=bool(r.i_target>0),original_i_buy=bool(r.i_buy),original_receipt=bool(r.cp_receipt),original_reset_reason=str(r.cp_reset_reason),original_anchor_log=float(r.cp_anchor),fixed_original_anchor_log=anchor,original_receipts_ignored_so_far=receipt_ignored,raw_open=float(r.raw_open),raw_high=float(r.raw_high),raw_low=float(r.raw_low),raw_close=float(r.raw_close))
        extensions.append(a);postrows.append(a);receipt_ignored+=bool(r.cp_receipt);prior=frontier
    signal_a.update(first_conditional_A_confirmation=str(first_A.date()) if first_A is not None else None,first_conditional_joint_confirmation=str(first_joint.date()) if first_joint is not None else None,conditional_A_delay_observations=int(x.loc[first_A,'position']-cur.position) if first_A is not None else None,conditional_joint_delay_observations=int(x.loc[first_joint,'position']-cur.position) if first_joint is not None else None,extension_stop_date=str(stop_day.date()) if stop_day is not None else None,extension_stop_reason=stop_reason,extension_valid_rows=len(postrows),original_receipts_ignored_count=receipt_ignored,actual_new_strategy_delay='undefined; no new state machine',MOBILE_first_probe_unchanged=True)
    signal_a['first_conditional_A_native_close']=float(x.loc[first_A,'close']) if first_A is not None else None
    signal_a['first_conditional_joint_native_close']=float(x.loc[first_joint,'close']) if first_joint is not None else None
    signal_a['conditional_A_close_vs_signal_simple_return']=float(x.loc[first_A,'close']/cur.close-1) if first_A is not None else None
    signal_a['conditional_joint_close_vs_signal_simple_return']=float(x.loc[first_joint,'close']/cur.close-1) if first_joint is not None else None
    valid_confirmation_path=[signal_a]+postrows
    signal_a['max_A_until_natural_stop']=max(r['A'] for r in valid_confirmation_path)
    signal_a['max_A_date_until_natural_stop']=next(r['date'] for r in valid_confirmation_path if r['A']==signal_a['max_A_until_natural_stop'])
    signal_a['first_A_confirmation_fresh']=signal_a['fresh'] if first_A==t else next((r['fresh_fixed_anchor'] for r in postrows if r['date']==str(first_A.date())),None) if first_A is not None else None
    signal_a['first_A_confirmation_original_I_valid']=True if first_A is not None else None
    summary.append(signal_a)

assert len(daily)==23
assert digest(FD)==frozen_hash
assert all(digest(p)==h for p,h in definition['source_sha256'].items())
for name,data in [('DAILY_23_ROWS.csv',daily),('SIGNAL_SUMMARY.csv',summary),('FIXED_ANCHOR_EXTENSION.csv',extensions),('TOP_CONTRIBUTORS.csv',top_rows),('ALL_ORIGINAL_WINDOW_COHORTS.csv',cohort_rows),('SOURCE_DIAGNOSTICS.csv',diagnostics),('OVERLAPPING_INTERVAL_EXAMPLES.csv',overlap_rows)]:
    pd.DataFrame(data).to_csv(OUT/name,index=False,float_format='%.16g')
checks={'frozen_definition_sha256':frozen_hash,'frozen_definition_unchanged':True,'source_hashes_unchanged':True,'native_coordinate_verified':True,'amount_exact_verified':True,'strict_prior_B_and_z_verified':True,'all_prefix_checks_passed':True,'original_D_and_fresh_reproduced':True,'current_bar_zero_contribution':True,'both_600056_signal_P_zero_A_nonpositive':True,'original_window_rows':len(daily),'extension_rows':len(extensions),'cohort_detail_rows':len(cohort_rows),'eligibility_never_uses_ready_I_or_E0':True,'full_same_source_history_used':True,'original_inputs_written':0,'account_runs':0,'parameter_searches':0,'universe_runs':0,'label_based_parameters':0,'new_CP_state_machine_runs':0}
(OUT/'CHECKS.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'checks':checks,'summary':[{k:s.get(k) for k in ['sid','original_signal_day','P','N','A','candidate_A_ge_1','unknown_interval_mass_all','max_q','max_positive_contribution','max_negative_contribution','first_conditional_A_confirmation','conditional_A_delay_observations','first_conditional_joint_confirmation','conditional_joint_delay_observations','extension_stop_date','extension_stop_reason']} for s in summary]},ensure_ascii=False,indent=2))
