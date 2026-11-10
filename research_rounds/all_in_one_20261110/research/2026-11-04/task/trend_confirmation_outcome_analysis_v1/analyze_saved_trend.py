"""Thin projections and reporting of closed native books; zero account runs."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter, defaultdict
import argparse,csv,gzip,hashlib,importlib.util,json,os

O=Path(__file__).resolve().parent; T=O.parent; Z=D(0)
P=T/'capacity_cost_guard_analysis_v1/analyze_completed_v1.py'
spec=importlib.util.spec_from_file_location('reused_saved_reporting',P)
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
ARMS=['B','UNIFORM50','A_ONLY','A_OR_B']
n=H.n;day=H.day;read=H.read;save=H.save;sha=H.sha;expect=H.expect

def csvout(p,rr):
    if not rr:return
    with p.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)

def project(root,out,expected):
    done=read(root/'DONE.json');res=read(root/'WINDOW_RESULT.json')
    assert done['completed'] and res['passed'] and res['actual_end']==res['fixed_full_end'] and res['days']==expected
    views=out/'views';views.mkdir(parents=True,exist_ok=True);src={}
    for arm in ARMS:
        d=views/arm/'pair';d.mkdir(parents=True,exist_ok=True)
        source=root/'pair'/f'{arm}.json.gz';target=d/'B.json.gz'
        if not target.exists():os.link(source,target)
        assert sha(source)==sha(target);src[str(source)]=sha(source)
    for name in ('daily','balances'):
        source=root/'pair'/f'{name}.jsonl.gz';src[str(source)]=sha(source)
        handles={a:gzip.open(views/a/'pair'/f'{name}.jsonl.gz','wt') for a in ARMS};count=Counter()
        try:
            with gzip.open(source,'rt') as f:
                for line in f:
                    row=json.loads(line);arm=row['account'];row['account']='B';handles[arm].write(json.dumps(row,ensure_ascii=False)+'\n');count[arm]+=1
        finally:
            for h in handles.values():h.close()
        assert all(count[a]==expected for a in ARMS),(name,count)
    save(out/'VIEW_SOURCE_BINDING.json',dict(source=str(root),sha256=src,projection='book hardlink; daily/balances filter account and rename label B only; numeric values unchanged',account_events=0))
    return views

def audit_status(win):
    p=T/'independent_review/trend_confirmation_full_ledger_v1'/f'FULL_{win.upper()}_FINANCE_AND_PVR_AUDIT.json'
    if p.exists():
        r=read(p);return dict(path=str(p),sha256=sha(p),status=r.get('status'))
    p=T/'independent_review/trend_confirmation_full_ledger_v1'/f'full_{win}_finance'+Path('') if False else T/'independent_review/trend_confirmation_full_ledger_v1'/f'full_{win}_finance/AUDIT.json'
    return dict(path=str(p),exists=p.exists(),status='PENDING_FINAL_RECEIPT')

def run(win):
    expected=726 if win=='long' else 242;root=T/'trend_confirmation_native_v1'/f'full-{win}-v1';out=O/f'full_{win}_v1';out.mkdir(parents=True,exist_ok=True)
    views=project(root,out,expected);H.A.O=out;data={};summary={};periods=[];phase_reports={};phases=read(T/'capacity_cost_guard_analysis_v1/FIXED_PHASES.json')['diagnostic_phases'];semis={r['sid'] for r in read(T/'capacity_cost_guard_analysis_v1/STRICT_SEMICONDUCTOR_MEMBERS.json')['members']}
    for arm in ARMS:
        a=H.account(win,arm,views/arm,expected);data[arm]=a;dr=H.flow_daily(a)
        r=summary[arm]=dict(account_metrics=a['metrics'],whole_calendar=H.period(dr),independent_financial_audit=audit_status(win))
        r['actual_positions']=dict(mean_held_stocks=sum(sum(bool(q) for q in d['positions'].values()) for d in a['daily'])/expected,max_held_stocks=max(sum(bool(q) for q in d['positions'].values()) for d in a['daily']),unique_actual_bought_stocks=len({t['security_id'] for t in a['book']['trades'] if t['side']=='buy'}),lag_exposure_denominator=expected,lag_exposure_includes_initial_empty_close=True,scope='market-value/capital exposure; not actual equal-risk comparison')
        save(out/f'{arm}_DAILY_WEALTH.json',dr)
        for grain in ('year','quarter','month'):
            key=lambda d:d[:4] if grain=='year' else d[:7] if grain=='month' else d[:4]+'Q'+str((int(d[5:7])-1)//3+1)
            for label in sorted({key(r['day']) for r in dr}):periods.append(dict(arm=arm,grain=grain,period=label,**H.period([r for r in dr if key(r['day'])==label])))
        phase_reports[arm]={}
        for p in phases:
            v=H.interval_stocks(a,p['lo'],p['hi'],semis if p.get('sector_id')=='URFI881121' else None)
            if v:
                rr=[r for r in dr if p['lo']<=r['day']<=p['hi']]
                phase_reports[arm][p['name']]=dict(definition=p,account_own_NAV_period=H.period(rr),**v)
        if win=='long':phase_reports[arm]['post924_old_vs_new_layers']=H.after924(a)
        print('SAVED_READ',win,arm,str(r['account_metrics']['return_pct']),flush=True)
    events=H.rows(root/'pair/confirmation-size-events.jsonl.gz');ev=defaultdict(list)
    for e in events:ev[e['account']].append(e)
    for arm in ARMS:
        summary[arm]['plan_event_counts']=dict(total=len(ev[arm]),result=dict(Counter(r['result'] for r in ev[arm])),minlot_zero_by_role=dict(Counter(r['role'] for r in ev[arm] if r['result']=='confirmation_half_below_minimum')),scope='Repeated original legal plan events, not independent misses; events can have no reserve/fill.')
    B=data['B'];comparisons={};reallocation=[];fixedfile=T/'risk_constraints/no60_capital_deployment_v2'/('2022_ORIGINAL_FIXED_WINNERS_AND_CONTROLS.json' if win=='long' else '2025_26_ORIGINAL_FIXED_WINNERS_AND_CONTROLS.json');fixed=[r['sid'] for r in read(fixedfile)]
    for arm in ARMS[1:]:
        a=data[arm];new=set(a['stock'])-set(B['stock']);lost=set(B['stock'])-set(a['stock']);common=set(B['stock'])&set(a['stock']);groups={}
        for name,ids in [('common_funded',common),('candidate_new_funded',new),('lost_baseline_funded',lost)]:
            rr=[dict(sid=s,name=H.A.META[s]['name'],baseline_net=B['stock'].get(s,Z),candidate_net=a['stock'].get(s,Z),delta=a['stock'].get(s,Z)-B['stock'].get(s,Z)) for s in ids]
            groups[name]=dict(stocks=len(ids),delta=sum((r['delta'] for r in rr),Z),members=sorted(rr,key=lambda r:-r['delta']))
        expect(sum((v['delta'] for v in groups.values()),Z),n(a['book']['ending_NAV'])-n(B['book']['ending_NAV']),'stock_money_delta')
        comparisons[arm]=dict(stock_cohorts=groups,original_fixed_stock_cases=[dict(sid=s,name=H.A.META[s]['name'],baseline_net=B['stock'].get(s,Z),candidate_net=a['stock'].get(s,Z),baseline_actual_layers=[l for l in B['layers'] if l['sid']==s],candidate_actual_layers=[l for l in a['layers'] if l['sid']==s]) for s in fixed],scope='Actual endogenous complete paths, not counterfactual per-plan causal alpha.')
        for month in sorted({day(d['at'])[:7] for d in a['daily']}):
            tx=[t for t in a['book']['trades'] if t['side']=='buy' and day(t['at']).startswith(month)];bt=[t for t in B['book']['trades'] if t['side']=='buy' and day(t['at']).startswith(month)];bs={t['security_id'] for t in bt};ss={t['security_id'] for t in tx};ds=[d for d in a['daily'] if day(d['at']).startswith(month)]
            reallocation.append(dict(arm=arm,month=month,buy_fills=len(tx),baseline_buy_fills=len(bt),actual_bought_stocks=len(ss),baseline_actual_bought_stocks=len(bs),bought_this_month_without_B_this_month=len(ss-bs),bought_stocks_never_B_in_window=len(ss&new),mean_held_stocks=sum(len([q for q in d['positions'].values() if q]) for d in ds)/len(ds),actual_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in tx),Z),new_to_B_window_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in tx if t['security_id'] in new),Z)))
    save(out/'SUMMARY.json',summary);save(out/'ALL_PERIODS.json',periods);save(out/'FIXED_PHASE_WEALTH.json',phase_reports);save(out/'BASELINE_STOCK_COMPARISONS.json',comparisons);save(out/'CAPITAL_REALLOCATION_MONTHS.json',reallocation)
    csvout(out/'ALL_MONTHS.csv',[r for r in periods if r['grain']=='month']);csvout(out/'ALL_YEARS.csv',[r for r in periods if r['grain']=='year']);csvout(out/'CAPITAL_REALLOCATION_MONTHS.csv',reallocation)
    save(out/'SOURCE_BINDING.json',dict(source_run=str(root),DONE_sha256=sha(root/'DONE.json'),WINDOW_RESULT_sha256=sha(root/'WINDOW_RESULT.json'),original_reader=str(H.P),original_reader_sha256=sha(H.P),reused_helpers=str(P),reused_helpers_sha256=sha(P),analysis_sha256=sha(__file__),new_account_events=0,financial_audit=audit_status(win),derived_statistics_independent_review='PENDING',strict_math='Known 9 exact equality classification boundaries/11 multiplier differences; frozen pandas implementation, not full exact-math PASS. No actual reserves at these keys, not a counterfactual full-account proof.'))
    save(out/'COMPLETED.json',dict(passed=True,window=win,days=expected,arms=ARMS,account_events=0,derived_statistics_independent_review='PENDING'))
    return data,summary,periods,phase_reports

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['long','strong'],required=True);args=ap.parse_args();run(args.window)
