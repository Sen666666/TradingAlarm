"""Diagnostic facts from saved inputs/results; no FSM import or account run."""
from pathlib import Path
import ast
import hashlib
import json
import math

import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;B=O.parent;OUT=O/'facts-v1'
F=B/'v2-frozen';I=B/'input-preparation/prepared-v2';H=B/'historical-shadow/run-v1';E=B/'industry-coverage/run-v1'
R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
SOURCES={};A=math.sqrt(5)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def remember(p):SOURCES[str(p)]=sha(p);return Path(p)
def read(p):return json.loads(remember(p).read_text())
def parquet(p):return pd.read_parquet(remember(p))
def snap(p):return {str(f.relative_to(p)):sha(f) for f in p.rglob('*') if f.is_file()}
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,pd.Timestamp):return str(x.date())
    if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
    if hasattr(x,'item'):return clean(x.item())
    return x
def save(name,x):(OUT/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    OUT.mkdir(exist_ok=False)
    protected={str(p):snap(p) for p in [F,I,H,E]}
    assert sha(F/'signal_core.py')=='962275bd41b5c7bbc062a1191780a6b6a9c616f8d3097ea669b602eabbc9ac59'
    assert sha(F/'CONTRACT.md')=='c3914aed1896563253961ea40d6065614a115cef21e13a93e1e74ad71779c54a'
    remember(F/'CONTRACT.md');source=remember(F/'signal_core.py').read_text();tree=ast.parse(source)
    funcs={n.name:dict(first_line=n.lineno,last_line=n.end_lineno,source='\n'.join(source.splitlines()[n.lineno-1:n.end_lineno]))
           for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['_new_segment','original_break','step']}
    save('CORE_READONLY_EXCERPTS.json',funcs)
    calendar=sorted(str(x)[:10] for x in read(R/'pvr-act-comparison-20261027/execution-rules-v2.json')['calendars']['A'])
    def next_open(day):return next((x for x in calendar if x>day),None)
    cases=[
        ('old924','OLD407/global','2024-09-27',I/'OLD407/market.parquet',H/'OLD407_global_daily.parquet','2024-09-24','2024-10-14'),
        ('June2022','NATIVE1709/global','2022-06-17',I/'NATIVE1709/market.parquet',H/'NATIVE1709_global_daily.parquet','2022-06-01','2022-06-30'),
        ('January2023','NATIVE1709/global','2023-01-19',I/'NATIVE1709/market.parquet',H/'NATIVE1709_global_daily.parquet','2023-01-03','2023-01-31'),
        ('semiconductorApril2026','NATIVE1709/URFI881121','2026-04-27',I/'NATIVE1709/industry_URFI881121.parquet',H/'NATIVE1709_semiconductor_daily.parquet','2026-04-01','2026-05-08'),
        ('negative_IT_June2023','NATIVE1709/URFI881271','2023-06-19',E/'inputs/NATIVE1709/industry_URFI881271.parquet',E/'daily/NATIVE1709_URFI881271.parquet','2023-06-01','2023-06-30'),
        ('negative_software_June2023','NATIVE1709/URFI881272','2023-06-19',E/'inputs/NATIVE1709/industry_URFI881272.parquet',E/'daily/NATIVE1709_URFI881272.parquet','2023-06-01','2023-06-30'),
    ]
    summaries=[];paths=[];checks=[]
    for case,domain,t0,ip,dp,begin,end in cases:
        inp=parquet(ip);daily=parquet(dp);daily.index=pd.to_datetime(daily.index)
        p=inp.price_input;breadth=inp.breadth;pos=p.index.get_loc(pd.Timestamp(t0));row=daily.loc[t0]
        assert 'break_started' in row.events and row.permit_next_open and row.original_break
        previous=p.iloc[pos-1];c=p.iloc[pos]
        rr=np.log(p).diff();prior=rr.iloc[:pos].dropna().tail(63)
        assert len(prior)==63
        s0=max(1.4826*float(prior.abs().median()),math.log(1.001))
        assert math.isclose(s0,float(row.prior_scale),rel_tol=0,abs_tol=1e-14)
        assert math.isclose(s0,float(row.frozen_segment_scale),rel_tol=0,abs_tol=1e-14)
        assert row.anchor==c and row.frontier==c and row.credit==0
        high=p.shift().rolling(63,min_periods=63).max();old_high=high.iloc[pos-1];h=high.iloc[pos]
        if 'prior_high63_as_run' in inp:
            np.testing.assert_allclose(high.loc[begin:end],inp.loc[begin:end,'prior_high63_as_run'],rtol=0,atol=1e-14,equal_nan=True)
        fixed=[]
        for horizon in [5,21,63]:
            base=p.iloc[pos-horizon]
            displacement=math.log(c/base)
            fixed.append(dict(observations=horizon,base_day=p.index[pos-horizon],base_close=base,
                              simple_price_change_pct=(c/base-1)*100,log_displacement=displacement,
                              displacement_over_start_scale=displacement/s0,over_sqrt5=displacement/(A*s0)))
        def breadth_lag(k):return breadth.iloc[pos-k]
        bstats={}
        for n in [5,21]:
            v=breadth.iloc[pos-n+1:pos+1]
            bstats[str(n)]=dict(known=int(v.notna().sum()),positive_over60=int(v.gt(.6).sum()),observations=n)
        streak=0
        for val in breadth.iloc[:pos+1].iloc[::-1]:
            if pd.isna(val) or val<=.6:break
            streak+=1
        advance=None;first_failure=None
        for day,r in daily.loc[t0:].iloc[1:].iterrows():
            if any(str(e).startswith('price_failure_') for e in r.events):
                first_failure=str(day.date());break
            if 'price_advance' in r.events:
                advance=(day,r);break
        latency=dict(first_trial_earliest_open=next_open(t0),first_advance_in_context=None,
                     expansion_earliest_open=None,failed_before_advance=first_failure)
        if advance is not None:
            day,r=advance;d=str(day.date());endpos=p.index.get_loc(day)
            latency.update(first_advance_in_context=d,expansion_earliest_open=next_open(d),
                           observations_start_to_advance=endpos-pos,calendar_days_start_to_advance=(day-pd.Timestamp(t0)).days,
                           calendar_days_start_to_expansion=(pd.Timestamp(next_open(d))-pd.Timestamp(t0)).days,
                           price_change_start_close_to_advance_close_pct=(r.close/c-1)*100,
                           log_progress_start_to_advance_over_s0=math.log(r.close/c)/s0,
                           initial_sqrt5_threshold_price_change_pct=math.expm1(A*s0)*100,
                           progress_over_sqrt5_threshold=math.log(r.close/c)/(A*s0),
                           breadth_at_advance=r.breadth,permit_at_advance=bool(r.permit_next_open),
                           post_reset_credit=r.credit,new_segment_scale_after_advance=r.frozen_segment_scale)
        summary=dict(case=case,domain=domain,start=t0,start_close=c,start_breadth=breadth.iloc[pos],
                     previous_close=previous,scale_start=s0,start_day_log_change_over_s0=math.log(c/previous)/s0,
                     start_day_log_change_over_sqrt5_threshold=math.log(c/previous)/(A*s0),
                     previous63_high=h,previous_day_previous63_high=old_high,
                     rolling_high_change_pct=(h/old_high-1)*100,rolling_high_aged_down=bool(h<old_high),
                     price_over_current63_high_pct=(c/h-1)*100,price_over_current63_high_log_units=math.log(c/h)/s0,
                     price_over_yesterday63_high_pct=(c/old_high-1)*100,
                     high63_dates=[str(t.date()) for t,v in p.iloc[pos-63:pos].items() if v==h],
                     previous_day_high63_dates=[str(t.date()) for t,v in p.iloc[pos-64:pos-1].items() if v==old_high],
                     fixed_endpoint_progress=fixed,breadth_previous=breadth_lag(1),breadth_lag5=breadth_lag(5),breadth_lag21=breadth_lag(21),
                     breadth_windows=bstats,consecutive_known_positive_breadth=streak,
                     start_post_credit=row.credit,start_anchor=row.anchor,start_frontier=row.frontier,
                     start_reference_line=row.next_line,latency=latency,
                     display_window=[begin,end],price_open_unknown='composite has no original market open; source close ratios are not trade execution returns' if '/global' in domain else 'no orders or account execution evaluated')
        summaries.append(summary)
        for day in inp.loc[begin:end].index:
            idx=p.index.get_loc(day);d=str(day.date());r=daily.loc[day]
            sc=float(r.prior_scale) if pd.notna(r.prior_scale) else None
            prevp=p.iloc[idx-1] if idx else np.nan
            # Fixed startup s0 is known only at t0; pre-start rows expose their
            # own causal scale separately. Neither field is a new F1 rule.
            rec=dict(case=case,domain=domain,day=d,relative_observation=idx-pos,close=p.loc[day],breadth=breadth.loc[day],
                     day_price_change_pct=(p.loc[day]/prevp-1)*100 if pd.notna(prevp) else None,
                     own_causal_scale=sc,startup_scale_for_retrospective_common_units=s0,
                     one_day_log_change_over_own_causal_scale=math.log(p.loc[day]/prevp)/sc if sc and pd.notna(prevp) else None,
                     log_price_relative_to_start_over_s0=math.log(p.loc[day]/c)/s0,
                     prior63_high=high.loc[day],price_over_prior63_high_pct=(p.loc[day]/high.loc[day]-1)*100,
                     distance_prior63_high_over_own_scale=math.log(p.loc[day]/high.loc[day])/sc if sc else None,
                     F1_status=r.effective_status,permit_next_open=bool(r.permit_next_open),events=list(r.events),
                     frozen_segment_scale_after_close=r.frozen_segment_scale,anchor_after_close=r.anchor,
                     frontier_after_close=r.frontier,credit_after_close=r.credit,next_line=r.next_line)
            for key in ['ready_m','positive_m','signed_m_stocks_ready','breadth_industries_ready']:
                if key in inp:rec[key]=inp.loc[day,key]
            paths.append(rec)
        checks.append(dict(case=case,scale_from_prior63_matches_saved=True,BREAK_true=True,credit_reset_zero=True,
                           fixed_lookbacks=[5,21,63],no_future_peak_used=True))
    save('STARTUP_FACTS.json',summaries);save('DAILY_PATHS.json',paths)
    df=pd.DataFrame(paths);df['events']=df.events.map(json.dumps);df.to_csv(OUT/'DAILY_PATHS.csv',index=False,float_format='%.17g')
    flat=[]
    for s in summaries:
        r={k:v for k,v in s.items() if not isinstance(v,(list,dict))}
        for d in s['fixed_endpoint_progress']:
            r['pre'+str(d['observations'])+'_price_pct']=d['simple_price_change_pct']
            r['pre'+str(d['observations'])+'_over_s0']=d['displacement_over_start_scale']
        r.update({'latency_'+k:v for k,v in s['latency'].items()})
        flat.append(r)
    pd.DataFrame(flat).to_csv(OUT/'STARTUP_FACTS.csv',index=False,float_format='%.17g')
    assert all(before==snap(Path(p)) for p,before in protected.items())
    assert all(sha(p)==h for p,h in SOURCES.items())
    save('VERIFICATION.json',dict(passed=True,cases=6,primary_cases=4,fixed_preexisting_negative_examples=2,
                                  checks=checks,original_F1_inputs_outputs_core_unchanged=True,
                                  new_FSM_sequences=0,new_capital_simulations=0,new_account_runs=0,
                                  thresholds_selected=0,price_diagnostics_not_financial_returns=True,
                                  unknowns=['composite opening price / execution effect','independent true-trend labels','separation/generalization from six seen cases']))
    save('SOURCE_SHA256.json',SOURCES)
    save('ARTIFACT_SHA256.json',{p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
    print(json.dumps(clean([{k:s[k] for k in ['case','start','start_breadth','scale_start','start_day_log_change_over_s0','fixed_endpoint_progress','price_over_current63_high_pct','rolling_high_change_pct','consecutive_known_positive_breadth','latency']} for s in summaries]),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
