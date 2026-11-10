"""Independent stored-value/calendar audit; imports pure providers only.

No rolling/ETF calculation, Account, native strategy, financial replay or new
economic fixture.  The expected clock comes from the original venue rulebook,
independent of both providers and their physically truncated observation rows.
"""
from pathlib import Path
from collections import Counter
import bisect,gzip,hashlib,json,math,pickle,sys
import pandas as pd

O=Path(__file__).resolve().parent;W=O.parent;T=W/'market_gross_admission_native_v1'
RULES=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    SRC[str(Path(p).resolve())]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
    SRC[str(Path(p).resolve())]=sha(p)
    with gzip.open(p,'rt')as f:return[json.loads(s)for s in f]
def normalized(v):
    v=dict(v)
    if v.get('available_at')is not None:v['available_at']=pd.Timestamp(v['available_at']).isoformat()
    return v

def main():
    frozen=read(T/'PROVIDER_V2_FREEZE.json')
    for path,h in frozen['source_sha256'].items():assert sha(path)==h
    sys.path.insert(0,str(T))
    from market_info import MarketInfo as V1
    from market_info_v2 import MarketInfo as V2
    assert 'gross_adapter'not in sys.modules and 'capacity_adapter'not in sys.modules
    grant=read(W/'MARKET_GROSS_ADMISSION_SMALL_AUTHORIZATION.json');rules=read(RULES)
    assert grant['authorized']and not grant['full_economic_run_authorized']
    for p,h in grant['bindings'].items():assert sha(W/p)==h
    windows={'long':dict(run='small-long-v1',history=W/'benchmark_2022_2023/continuation2024/inputs/510300_history.csv',first='2021-12-30',end='2024-12-31'),
             'strong':dict(run='small-strong-v1',history=W/'capacity_cost_guard_analysis_v1/benchmark_B_2025_26/inputs/510300_history.csv',first='2025-06-27',end='2026-06-30')}
    output={};negative=None
    for name,spec in windows.items():
        history=spec['history'];history_sha=sha(history);SRC[str(history.resolve())]=history_sha
        f=pd.read_csv(history,index_col='date',parse_dates=True)
        assert f.index.is_unique and f.index.is_monotonic_increasing
        obs=[dict(day=str(t.date()),available_at=pd.Timestamp(str(t.date())+'T15:10:00+08:00'),X=float(r.signal_close),MA63=float(r.ma63))for t,r in f.iterrows()]
        clocks=[r['available_at']for r in obs]
        expected=[pd.Timestamp(x)for x in rules['decision_cutoffs']if spec['first']<=x[:10]<=spec['end']]
        v1=V1(history);v2=V2(history,expected);restarted=pickle.loads(pickle.dumps(v2));prefixes={};checks=Counter();cases=[]
        def expected_at(at):
            at=pd.Timestamp(at);j=bisect.bisect_right(expected,at)-1
            assert j>=0 and at.date()<=expected[-1].date()
            latest=expected[j];i=bisect.bisect_right(clocks,at)-1
            assert i>=1 and clocks[i]==latest,('missing actual-source expected close',name,at,latest)
            r=obs[i];prior=obs[i-1]['MA63'];known=all(math.isfinite(x)and x>0 for x in(r['X'],r['MA63'],prior))
            state='UNKNOWN'if not known else'DOWN'if r['X']<r['MA63']and r['MA63']<prior else'NOT_DOWN'
            return dict(r,previous_MA63=prior,state=state,source=str(history.resolve()),source_sha256=history_sha)
        def verify(at,recorded=None):
            correct=normalized(expected_at(at));a=normalized(v1.state(at));b=normalized(v2.state(at));p=normalized(restarted.state(at))
            assert correct==a==b==p,('provider/CSV/calendar mismatch',name,str(at))
            if recorded is not None:assert correct==normalized(recorded),('recorded actual info mismatch',name,str(at))
            cut=correct['day']
            if cut not in prefixes:
                prefixes[cut]=v2.prefix(cut)
                assert all(r['day']<=cut for r in prefixes[cut].observations)
            assert normalized(prefixes[cut].state(at))==correct,('physical completed-info prefix differs',name,str(at))
            checks[correct['state']]+=1
        started=read(T/spec['run']/'STARTED.json')
        for p,h in started['sources'].items():assert sha(p)==h
        for case,start,end,n,gold in started['cases']:
            dest=T/spec['run']/case;result=read(dest/'SMALL_RESULT.json');assert result['passed']and result['source_post_exact']and result['closes_each']==n
            opens=[pd.Timestamp(x)for x in rules['calendars']['A']if start<=x[:10]<=end]
            closes=[pd.Timestamp(x)for x in rules['decision_cutoffs']if start<=x[:10]<=end]
            assert len(opens)==len(closes)==n
            planned=sorted(opens+closes);recorded=read(dest/'MARKET_INFO_CLOCK_CHECKS.json')['rows']
            assert [pd.Timestamp(r['at'])for r in recorded]==planned,('omitted/non-native planned clock',case)
            for r in recorded:verify(r['at'],{k:v for k,v in r.items()if k!='at'})
            events=rows(dest/'pair/gross-admission-events.jsonl.gz')
            for r in events:
                assert pd.Timestamp(r['at'])in planned
                verify(r['at'],r['info'])
            cases.append(dict(case=case,scheduled_native_OPEN_CLOSE_checks=len(planned),all_actual_callback_checks=len(events),
                DOWN_positive_reserves=sum(r['kind']=='reserve_pre'and r['q']>0 and r['info']['state']=='DOWN'for r in events),
                no_native_replay=True,full_calendar_not_survivor_event_selection=True))
        if name=='long':
            a=v1.prefix('2022-01-07');b=v2.prefix('2022-01-07')
            assert a.state('2022-01-10T15:10:00+08:00')['state']!='UNKNOWN'
            assert a.state('2022-01-11T09:30:00+08:00')['state']!='UNKNOWN'
            assert b.state('2022-01-10T09:30:00+08:00')['day']=='2022-01-07'
            assert b.state('2022-01-10T09:30:00+08:00')['state']!='UNKNOWN'
            assert b.state('2022-01-10T15:10:00+08:00')['state']=='UNKNOWN'
            assert b.state('2022-01-11T09:30:00+08:00')['state']=='UNKNOWN'
            assert b.state('2027-01-05T15:10:00+08:00')['state']=='UNKNOWN'
            negative=dict(v1_stale_prefix_negative_FAIL_preserved=True,v2_Jan10_OPEN_uses_Jan7=True,
                v2_missing_Jan10_CLOSE_UNKNOWN=True,v2_Jan11_OPEN_missing_prior_CLOSE_UNKNOWN=True,v2_outside_expected_domain_UNKNOWN=True)
        output[name]=dict(cases=cases,state_counts=dict(checks),expected_clock_source=str(RULES),expected_full_window_first=expected[0].isoformat(),expected_full_window_last=expected[-1].isoformat(),native_historical_restart_claimed=False)
    for p,h in frozen['source_sha256'].items():assert sha(p)==h
    result=dict(status='PASS_V2_PROVIDER_SOURCE_CALENDAR_AND_ACTUAL_SCOPE_EQUIVALENCE_WITH_V1_NEGATIVE_FAIL_PRESERVED',passed=True,
        windows=output,negative_boundaries=negative,provider_pickle_roundtrip_only=True,native_historical_financial_restart=False,
        actual_small_provider_version='V1: market_info.py',v2_native_small_rerun=False,v2_domain_repair_changes_actual_consumed_info=False,
        no_MA_TR_recomputation=True,no_benchmark_trading_on_used=True,source_date_identity_and_state_comparison_exact=True,
        actual_account_instantiations=0,financial_replays=0,source_SHA256=SRC,checker_SHA256=sha(__file__),full_native_GO=False,
        limits=['Three authorized small calendars/callbacks only; no full native/economic authorization.',
            'V2 has zero-account provider domain evidence; the existing small accounts actually used frozen V1.',
            'New prospective full entry must freeze V2 and its independent expected-close calendar, score binding, source paths before native events.'])
    path=O/'PROVIDER_CLOCK_INDEPENDENT_REVIEW.json';assert not path.exists();path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,path=str(path),SHA256=sha(path),windows=output),indent=2))

if __name__=='__main__':main()
