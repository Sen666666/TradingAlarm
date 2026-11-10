"""Thin saved-book reporting; no strategy, account, execution or CA engine."""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal as D
import argparse, csv, gzip, hashlib, importlib.util, inspect, json, time

O=Path(__file__).resolve().parent; T=O.parent; Z=D(0)
P=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/c1-drawdown-capacity-20261101/analyze_saved.py')
spec=importlib.util.spec_from_file_location('original_saved_book_analysis_capacity',P)
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
ORIGINAL=inspect.getsource(A.account)
DERIVED=ORIGINAL.replace('def account(win,ref,root):','def account(win,ref,root,expected_days):').replace('len(ds)==len(checks)==242','len(ds)==len(checks)==expected_days')
assert DERIVED!=ORIGINAL and DERIVED.replace('def account(win,ref,root,expected_days):','def account(win,ref,root):').replace('len(ds)==len(checks)==expected_days','len(ds)==len(checks)==242')==ORIGINAL
env=dict(A.__dict__);exec(compile(DERIVED,str(O/'generic_saved_reader.py.txt'),'exec'),env);account=env['account']

def n(x):return D(str(x))
def day(x):return str(x)[:10]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,z):Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n')
def rows(p):
    with gzip.open(p,'rt') as h:return [json.loads(x) for x in h]
def expect(x,y,label):assert abs(x-y)<D('.000001'),(label,x,y,x-y)

def flow_daily(a):
    flows=defaultdict(lambda:defaultdict(lambda:Z));prevNAV=D(1000000);prevInv=Z;prevOn=True;prevExposure=Z;out=[]
    for t in a['book']['trades']:
        v=flows[day(t['at'])];fee=n(t['fees_cny']);gross=n(t['gross_cny']);v['fees']+=fee
        if t['side']=='buy':v['buy_cash']+=gross+fee;v['buy_gross']+=gross;v['buy_fills']+=1
        else:v['sell_net']+=gross-fee;v['sell_gross']+=gross;v['sell_fills']+=1
    for t in a['book']['audit']:
        if t['kind']=='dividend_accrual':v=t['receivable'];flows[day(v['ex_at'])]['dividend_accrued']+=n(v['net_local'])
    for r in a['daily']:
        d=day(r['at']);v=flows[d];nav=n(r['nav']);inv=n(r['inventory']);wealth=inv-prevInv+v['sell_net']-v['buy_cash']+v['dividend_accrued']
        expect(wealth,nav-prevNAV,('daily_cash_inventory_AR',d))
        out.append(dict(day=d,NAV_begin=prevNAV,NAV_end=nav,inventory_begin=prevInv,inventory_end=inv,wealth_change=wealth,
            actual_buy_cash=v['buy_cash'],actual_buy_gross=v['buy_gross'],actual_sell_net=v['sell_net'],actual_sell_gross=v['sell_gross'],actual_fees=v['fees'],recognized_dividend=v['dividend_accrued'],buy_fills=int(v['buy_fills']),sell_fills=int(v['sell_fills']),
            lag_exposure_pct=prevExposure,exposure_pct=inv/nav*100,cash_pct=n(r['available'])/nav*100,nominal_mark_floor_risk_pct=(n(r['pool_probe'][1])+n(r['pool_confirmed'][1]))/nav*100,ACT_at_OPEN=prevOn,ACT_after_CLOSE=r['on']))
        prevNAV,prevInv,prevOn,prevExposure=nav,inv,r['on'],inv/nav*100
    return out

def period(rr):
    keys=['wealth_change','actual_buy_cash','actual_buy_gross','actual_sell_net','actual_sell_gross','actual_fees','recognized_dividend','buy_fills','sell_fills']
    v={k:sum((r[k] for r in rr),Z) for k in keys};start=rr[0]['NAV_begin'];end=rr[-1]['NAV_end'];expect(v['wealth_change'],end-start,'periodcashbridge')
    return dict(start=rr[0]['day'],end=rr[-1]['day'],days=len(rr),initial_own_NAV=start,end_NAV=end,return_pct=(end/start-1)*100,DD=A.dd([('period_start',start)]+[(r['day'],r['NAV_end']) for r in rr]),
        mean_lag_exposure_pct=sum((r['lag_exposure_pct'] for r in rr),Z)/len(rr),mean_close_exposure_pct=sum((r['exposure_pct'] for r in rr),Z)/len(rr),mean_cash_pct=sum((r['cash_pct'] for r in rr),Z)/len(rr),mean_close_nominal_risk_pct=sum((r['nominal_mark_floor_risk_pct'] for r in rr),Z)/len(rr),paused_OPEN_days=sum(not r['ACT_at_OPEN'] for r in rr),**v)

def interval_stocks(a,lo,hi,ids=None):
    dates=list(a['byday']);inside=[d for d in dates if lo<=d<=hi]
    if not inside:return None
    lo,hi=inside[0],inside[-1];pos=dates.index(lo);before=dates[pos-1] if pos else None
    ids=set(ids) if ids is not None else set(a['stock']);money=defaultdict(lambda:Z)
    for sid in ids:money[sid]+=a['values'][hi].get(sid,Z)-(a['values'][before].get(sid,Z) if before else Z)
    bg=sg=fee=div=Z;buys=[];sells=[]
    for t in a['book']['trades']:
        sid=t['security_id']
        if sid not in ids or not lo<=day(t['at'])<=hi:continue
        g=n(t['gross_cny']);f=n(t['fees_cny']);fee+=f
        if t['side']=='buy':money[sid]-=g+f;bg+=g;buys.append(t)
        else:money[sid]+=g-f;sg+=g;sells.append(t)
    for t in a['book']['audit']:
        if t['kind']=='dividend_accrual':
            r=t['receivable'];sid=r['security_id']
            if sid in ids and lo<=day(r['ex_at'])<=hi:money[sid]+=n(r['net_local']);div+=n(r['net_local'])
    iv0=sum((a['values'][before].get(s,Z) for s in ids),Z) if before else Z;iv1=sum((a['values'][hi].get(s,Z) for s in ids),Z)
    wealth=iv1-iv0+sg-bg-fee+div;expect(sum(money.values(),Z),wealth,'stock_interval')
    weights=[sum((a['values'][d].get(s,Z) for s in ids),Z)/n(a['byday'][d]['nav'])*100 for d in inside]
    return dict(start=lo,end=hi,previous_close=before,interval_wealth=wealth,inventory_begin=iv0,inventory_end=iv1,actual_buy_gross=bg,actual_buy_cash=bg+sum((n(t['fees_cny']) for t in buys),Z),actual_sell_gross=sg,all_trade_fees=fee,recognized_dividend=div,buy_fills=len(buys),sell_fills=len(sells),first_actual_buy=buys[0]['at'] if buys else None,mean_close_weight_pct=sum(weights,Z)/len(weights),peak_close_weight_pct=max(weights),stock_wealth=sorted([dict(sid=s,name=A.META[s]['name'],wealth=v) for s,v in money.items()],key=lambda x:-x['wealth']))

def guard_summary(root,arm):
    p=root/'pair'/f'{arm}-cost-guard.jsonl.gz'
    if not p.exists():return None
    events=rows(p);rs=[r for r in events if r['kind']=='route'];dedup={}
    for r in rs:
        key=(str(r['at']),r['sid'],r['role'],str(r['decision_at']),str(r['budget_order_hint']));prior=max((v['pre_guard_legal_quantity'] for v in r['routes']),default=0)
        dedup[key]=dict(at=r['at'],sid=r['sid'],role=r['role'],decision_at=r['decision_at'],budget_order_hint=r['budget_order_hint'],pre_guard_individually_legal_quantity=prior,selected_quantity=r['selected_quantity'],reasons=r['routes'])
    rr=list(dedup.values());positive=[r for r in rr if r['pre_guard_individually_legal_quantity']>0]
    ds=[r for r in rows(root/'pair/cost-capacity-daily.jsonl.gz') if r['account']==arm]
    out=dict(native_route_events=len(rs),unique_routed_stock_role_decision_keys=len(rr),positive_pre_guard_legal=len(positive),guard_zero=sum(r['selected_quantity']==0 for r in positive),guard_shrunk_positive=sum(0<r['selected_quantity']<r['pre_guard_individually_legal_quantity'] for r in positive),fill_cost_cap_cancel=sum(r['kind']=='fill_cost_cap_cancel' for r in events),event_kinds=dict(Counter(r['kind'] for r in events)),
        daily_observations=len(ds),mean_unprotected_cost_pct_NAV=sum(((n(r['used_cost'])+n(r['pending_cost']))/n(r['NAV'])*100 for r in ds),Z)/len(ds),mean_protected_cost_pct_NAV=sum((n(r['protected_cost'])/n(r['NAV'])*100 for r in ds),Z)/len(ds),mean_actual_held_fee_inclusive_cost=sum((n(r['used_cost'])+n(r['protected_cost']) for r in ds),Z)/len(ds),passive_close_over_cap=sum(n(r['used_cost'])+n(r['pending_cost'])>n(r['guard_NAV'])*n(events[0]['alpha']) for r in ds),
        semantics='Pre-guard quantities are independently legal at this arm actual prefix, not quantities funded by No60 or simultaneously executable opportunities; passive close excess is not a new-admission invariant violation.')
    return out,rr,ds

def after924(a):
    bound='2024-10-08'
    if bound not in a['byday']:return None
    active={x['id']:x for x in a['byday'][bound]['layers']};groups=defaultdict(lambda:dict(layers=0,wealth=Z));end=n(a['book']['ending_NAV'])
    for l in a['layers']:
        lid=l['layer'];before=Z
        if day(l['opened'])<=bound:
            if lid in active:x=active[lid];before=n(x['cash'])+n(x['dividend'])+D(x['qty'])*A.price(l['sid'],bound)
            else:before=l['net']
        k='new_fill_after_boundary' if day(l['opened'])>bound else 'actually_held_at_boundary' if lid in active else 'already_closed_at_boundary'
        groups[k]['layers']+=1;groups[k]['wealth']+=l['net']-before
    expect(sum((v['wealth'] for v in groups.values()),Z),end-n(a['byday'][bound]['nav']),'924_old_new_wealth')
    return dict(boundary=bound,end=day(a['daily'][-1]['at']),actual_NAV_change=end-n(a['byday'][bound]['nav']),groups=dict(groups),entry_cohort_vs_period_wealth_distinguished=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['long','strong'],required=True);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--expected-days',type=int);args=ap.parse_args()
    expected=args.expected_days or (726 if args.window=='long' else 242);root=args.root.resolve();out=args.out.resolve();assert (root/'ARM_VIEW_INDEX.json').exists(),'wait for atomic per-arm publication gate'
    assert read(root/'DONE.json')['completed'];assert not(out/'COMPLETED.json').exists();out.mkdir(parents=True,exist_ok=True);A.O=out
    (out/'generic_saved_reader.py.txt').write_text(DERIVED)
    arms=['B','G10','G20','G40','NR20'];data={};summary={};periods=[];phase_reports={};phases=read(O/'FIXED_PHASES.json')['diagnostic_phases'];semis={r['sid'] for r in read(O/'STRICT_SEMICONDUCTOR_MEMBERS.json')['members']}
    for arm in arms:
        base=root/'arms'/arm;index=read(root/'ARM_VIEW_INDEX.json')[arm];assert sha(base/'pair/B.json.gz')==index['source_book_sha256']
        a=account(args.window,arm,base,expected);data[arm]=a;dr=flow_daily(a);summary[arm]=dict(account_metrics=a['metrics'],whole_calendar=period(dr),source_book_sha256=index['source_book_sha256'],independent_financial_audit='PENDING')
        save(out/f'{arm}_DAILY_WEALTH.json',dr)
        for grain in ('year','quarter','month'):
            key=lambda d:d[:4] if grain=='year' else d[:7] if grain=='month' else d[:4]+'Q'+str((int(d[5:7])-1)//3+1)
            for label in sorted({key(r['day']) for r in dr}):periods.append(dict(arm=arm,grain=grain,period=label,**period([r for r in dr if key(r['day'])==label])))
        phase_reports[arm]={}
        for p in phases:
            value=interval_stocks(a,p['lo'],p['hi'],semis if p.get('sector_id')=='URFI881121' else None)
            if value:phase_reports[arm][p['name']]=dict(definition=p,**value)
        if args.window=='long':phase_reports[arm]['post924_old_vs_new_layers']=after924(a)
        guard=guard_summary(root,arm)
        if guard:summary[arm]['guard']=guard[0];save(out/f'{arm}_ROUTED_KEYS.json',guard[1]);save(out/f'{arm}_CAPACITY_DAILY.json',guard[2])
        opp=base/'pair/opportunities.jsonl.gz'
        if opp.exists():
            oo=rows(opp)
            summary[arm]['saved_role_candidate_population']=dict(role_candidate_stockdays=len(oo),fresh_CP1_mobile_Q_stockdays=sum(bool(r.get('CP1_id')) and r.get('mobile_Q') is True for r in oo),planned_roles=dict(Counter(role for r in oo for role in r['roles'])),barrier_stockdays=dict(Counter(reason for r in oo for reason in r['barriers'])),scope='Producer retains rows with nonempty roles only; stock-day counts and overlapping barriers are not independent opportunities or all-universe unknown counts.')
        print('ANALYZED_SAVED',args.window,arm,summary[arm]['whole_calendar']['return_pct'],flush=True)
    baseline=data['B'];comparisons={};tailbook='2022_2024' if args.window=='long' else 'strong';original_tails=read(O/'../risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members'][tailbook]
    fixedfile=O/'../risk_constraints/no60_capital_deployment_v2'/('2022_ORIGINAL_FIXED_WINNERS_AND_CONTROLS.json' if args.window=='long' else '2025_26_ORIGINAL_FIXED_WINNERS_AND_CONTROLS.json');fixed_sids=[r['sid'] for r in read(fixedfile)]
    for arm in arms[1:]:
        a=data[arm];oldset=set(baseline['stock']);newset=set(a['stock']);groups={}
        for kind,ids in [('common_funded',oldset&newset),('candidate_new_funded',newset-oldset),('lost_baseline_funded',oldset-newset)]:
            rows0=[dict(sid=s,name=A.META[s]['name'],industry=A.META[s]['industry'],baseline_net=baseline['stock'].get(s,Z),candidate_net=a['stock'].get(s,Z),delta=a['stock'].get(s,Z)-baseline['stock'].get(s,Z)) for s in ids]
            groups[kind]=dict(stocks=len(ids),delta=sum((r['delta'] for r in rows0),Z),members=sorted(rows0,key=lambda r:-r['delta']))
        delta=n(a['book']['ending_NAV'])-n(baseline['book']['ending_NAV']);expect(sum((v['delta'] for v in groups.values()),Z),delta,'stock_cohort_delta')
        comparisons[arm]=dict(terminal_NAV_delta=delta,stock_cohorts=groups,original_fixed_stock_cases=[dict(sid=s,name=A.META[s]['name'],baseline_net=baseline['stock'].get(s,Z),candidate_net=a['stock'].get(s,Z),baseline_actual_layers=[l for l in baseline['layers'] if l['sid']==s],candidate_actual_layers=[l for l in a['layers'] if l['sid']==s]) for s in fixed_sids])
        oldgroups={}
        for label,ids in [('baseline_positive_stock', {s for s,v in baseline['stock'].items() if v>0}),('baseline_nonpositive_stock',{s for s,v in baseline['stock'].items() if v<=0})]:
            oldgroups[label]=dict(stocks=len(ids),baseline_net=sum((baseline['stock'][s] for s in ids),Z),candidate_net=sum((a['stock'].get(s,Z) for s in ids),Z),actually_funded_by_candidate=len(ids&newset),all_members=sorted(ids),scope='Posthoc complete baseline-stock outcome group, never a real-time signal; net can include terminal mark and accrued dividend.')
        comparisons[arm]['whole_baseline_stock_outcome_groups']=oldgroups
        def tailkey(budget,receipt):return (budget.split('|',1)[1] if budget and '|'in budget else budget,receipt)
        mapping=defaultdict(list)
        for l in a['layers']:
            m=a['book']['metadata'][str(l['layer'])];mapping[tailkey(m.get('budget_order'),l.get('receipt'))].append(l)
        comparisons[arm]['fixed_original_tail_order_matches']=[dict(original=r,matched_candidate_layers=mapping.get(tailkey(r.get('budget_order'),r.get('receipt')),[])) for r in original_tails]
        comparisons[arm]['fixed_tail_semantics']='Original PVR frozen list retained; account-name prefix only normalized; partial layers grouped, no sid-only forced match; cutoff contributions not counterfactual lost profit.'
    save(out/'SUMMARY.json',summary);save(out/'ALL_PERIODS.json',periods);save(out/'FIXED_PHASE_WEALTH.json',phase_reports);save(out/'BASELINE_STOCK_COMPARISONS.json',comparisons)
    save(out/'SOURCE_BINDING.json',dict(reader_source=str(P),reader_sha256=sha(P),derived_reader_only_parameterizes_expected_day_count=True,analysis_sha256=sha(__file__),published_index_sha256=sha(root/'ARM_VIEW_INDEX.json'),source_run=str(root),new_account_events=0,period_bridge='actual trade cash + native raw inventory + recognized dividend; no reconstructed CA quantity or basis model; strict real/unreal not redefined',remaining_basis='guard observer actual stored basis only; no control basis invented'))
    save(out/'COMPLETED.json',dict(passed=True,window=args.window,days=expected,arms=arms,account_events=0,independent_financial_review='PENDING'))

if __name__=='__main__':main()
