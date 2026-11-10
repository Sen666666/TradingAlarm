"""Independent thin CSV/daily/old-reader audit: no accounts, imports or valuation."""
from pathlib import Path
from decimal import Decimal as D
import collections,csv,gzip,hashlib,json,time,traceback
O=Path(__file__).resolve().parent;W=O.parent;E=W/'market_gross_rule_and_outcome_explanation_v1'
Z=D(0);EPS=D('.000001');sources={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def note(p):sources[str(p.resolve())]=sha(p)
def jread(p):note(p);return json.loads(p.read_text())
def csvread(p):note(p);return list(csv.DictReader(p.open()))
def gzread(p):
    note(p)
    with gzip.open(p,'rt')as f:return json.load(f)
def daily(p):
    note(p)
    with gzip.open(p,'rt')as f:return[json.loads(x)for x in f]
def near(a,b,tag,eps=EPS):assert abs(D(str(a))-D(str(b)))<eps,(tag,a,b)
def sm(xs):return sum((D(str(x))for x in xs),Z)
def unique(rs):
    out={r['sid']:r for r in rs};assert len(out)==len(rs);return out
def run():
    begin=time.monotonic();control=jread(W/'market_gross_admission_native_v1/ARCHIVED_B_CONTROL_BINDING.json')
    claims=csvread(E/'YEAR_AND_HALF_YEAR_METRICS.csv');assert len(claims)==10
    sets={};books={};days={};annual=[];cohorts={}
    for win in ('long','strong'):
        for arm in ('D_GROSS10','ARCHIVED_B'):
            if arm=='D_GROSS10':root=W/'market_gross_admission_native_v1'/f'full-{win}-v1'/'pair';bp=root/'D_GROSS10.json.gz';rp=W/'market_gross_admission_outcome_analysis_v1'/f'full_{win}_v1'/'analysis'/win/'D_GROSS10'
            else:
                bp=next(Path(p)for p in control[win]['source_sha256']if p.endswith('/pair/B.json.gz'));root=bp.parent;rp=W/'capacity_cost_guard_analysis_v1'/f'full_{win}_v1'/'analysis'/win/'B'
            ds=daily(root/'daily.jsonl.gz');b=gzread(bp);ls=jread(rp/'LAYERS.json');old=unique(jread(rp/'STOCKS.json'))
            books[win,arm]=b;days[win,arm]=ds
            by=collections.defaultdict(list)
            for l in ls:by[l['sid']].append(l)
            assert set(by)==set(old)
            comps=unique(csvread(E/f'ALL_ACTUAL_STOCK_COMPONENTS_{win}_{arm}.csv'));assert set(comps)==set(old)
            native={x['id']:x for x in b['layers']};original={}
            for sid,ll in by.items():
                net=sm(x['net']for x in ll);cost=sm(x['cost']for x in ll);div=sm(native[x['layer']]['dividend']for x in ll);cash=sm(native[x['layer']]['cash']for x in ll);value=sm(x['value']for x in ll)
                near(net,old[sid]['net'],('old_reader_net',win,arm,sid));near(net,cash+div+value,('native_component_bridge',win,arm,sid))
                c=comps[sid];near(c['whole_window_stock_net'],net,('csv_net',sid));near(c['actual_buy_cash'],cost,('csv_cost',sid));assert int(c['actual_buy_layers'])==len(ll)
                near(c['recognized_dividend_equity_paid_plus_AR'],div,('csv_recognizeddiv',sid))
                assert c['stock_terminal_dividend_AR']==('0_ZERO_ALL_RECOGNIZED_DIVIDENDS'if div==0 else'UNKNOWN_NO_SAVED_PER_STOCK_TERMINAL_AR')
                original[sid]=dict(net=net,cost=cost)
            near(sm(x['net']for x in original.values()),D(b['ending_NAV'])-D(1000000),(win,arm,'whole_reader_bridge'));sets[win,arm]=original
            prev=D(1000000)
            for year in sorted({r['at'][:4]for r in ds}):
                rr=[r for r in ds if r['at'].startswith(year)];period=year if win=='long'else year+('H2'if year=='2025'else'H1')
                if win=='strong':assert period in ('2025H2','2026H1')
                c=next(x for x in claims if x['window']==win and x['arm']==arm and x['period']==period)
                peak=prev;pd='period_start';mdd=Z;mp=None;mt=None
                for r in rr:
                    n=D(r['nav'])
                    if n>peak:peak=n;pd=r['at'][:10]
                    dd=(peak-n)/peak*100
                    if dd>mdd:mdd=dd;mp=pd;mt=r['at'][:10]
                near(c['initial_own_period_NAV'],prev,(win,arm,period,'initial'));near(c['end_NAV'],rr[-1]['nav'],(period,'end'));near(c['period_local_CLOSE_MDD_pct'],mdd,(period,'MDD'),D('1e-18'))
                assert c['period_MDD_peak_day']==mp and c['period_MDD_trough_day']==mt
                assert int(c['CLOSE_days'])==len(rr)and c['actual_first_CLOSE']==rr[0]['at'][:10]and c['actual_last_CLOSE']==rr[-1]['at'][:10]
                near(c['return_pct'],(D(rr[-1]['nav'])/prev-1)*100,(period,'return'),D('1e-18'))
                annual.append(dict(window=win,arm=arm,period=period,days=len(rr),MDD=str(mdd),peak_day=mp,trough_day=mt));prev=D(rr[-1]['nav'])
        B=sets[win,'ARCHIVED_B'];A=sets[win,'D_GROSS10'];ws={s for s,v in B.items()if v['net']>0};new=set(A)-set(B)
        assert set(unique(csvread(E/f'FIXED_B_WINNERS_ALL_{win}.csv')))==ws
        reduced={s for s in ws if s in A and A[s]['cost']<B[s]['cost']};unbought=ws-set(A)
        assert set(unique(csvread(E/f'FIXED_B_WINNERS_D_REDUCED_{win}.csv')))==reduced
        assert set(unique(csvread(E/f'FIXED_B_WINNERS_D_UNBOUGHT_{win}.csv')))==unbought
        newrows=unique(csvread(E/f'ALL_D_NEWLY_FUNDED_{win}.csv'));assert set(newrows)==new
        newpos={s for s in new if A[s]['net']>0};assert set(unique(csvread(E/f'ALL_D_NEW_POSITIVE_BENEFICIARIES_{win}.csv')))==newpos
        for s,c in newrows.items():near(c['whole_window_stock_net'],A[s]['net'],('new_all_amount',win,s))
        dif=unique(csvread(E/f'ALL_STOCK_PATH_DIFFERENCES_{win}.csv'));assert set(dif)==set(A)|set(B)
        positive=set()
        for s,c in dif.items():
            delta=A.get(s,{}).get('net',Z)-B.get(s,{}).get('net',Z);near(c['net_difference_NOT_alpha'],delta,('delta',s))
            if delta>0:positive.add(s)
        assert set(unique(csvread(E/f'ALL_POSITIVE_PATH_DIFFERENCES_{win}.csv')))==positive
        cohorts[win]=dict(original_B_positive=len(ws),D_unbought=len(unbought),D_reduced=len(reduced),new_funded=len(new),new_positive=len(newpos),new_all_net=str(sm(A[s]['net']for s in new)),negative_and_zero_new_kept=len(new)-len(newpos))
    assert[cohorts[w]['original_B_positive']for w in ('long','strong')]==[259,232]
    assert[cohorts[w]['new_funded']for w in ('long','strong')]==[194,44]
    assert[cohorts[w]['new_positive']for w in ('long','strong')]==[54,8]
    members=jread(W/'capacity_cost_guard_analysis_v1/STRICT_SEMICONDUCTOR_MEMBERS.json')['members'];ids={r['sid']for r in members};assert len(ids)==126 and all(r['sector_id']=='URFI881121'and r['industry']=='半导体'for r in members)
    semi=csvread(E/'SEMICONDUCTOR126_H1_ALL_MEMBERS.csv');assert len(semi)==252
    phase=jread(W/'market_gross_admission_outcome_analysis_v1/full_strong_v1/FIXED_PHASE_WEALTH.json')['strict_semiconductor_2026H1'];summary=jread(E/'SEMICONDUCTOR126_H1_SUMMARY.json');semiaudit={}
    for arm,pk in [('D_GROSS10','D_actual_stock_wealth'),('ARCHIVED_B','ARCHIVED_B_phase')]:
        m=unique([r for r in semi if r['arm']==arm]);assert set(m)==ids;original={r['sid']:D(r['wealth'])for r in phase[pk]['stock_wealth']};assert set(original)==ids
        before=next(r for r in days['strong',arm]if r['at'][:10]=='2025-12-31');assert not(set(before['positions'])&ids)
        buys={t['security_id']for t in books['strong',arm]['trades']if t['side']=='buy'and'2026-01-01'<=t['at'][:10]<='2026-06-30'and t['security_id']in ids}
        assert{s for s,c in m.items()if int(c['H1_buy_fills'])>0}==buys
        for s,c in m.items():near(c['H1_period_wealth'],original[s],('semi_member',arm,s))
        near(sm(c['H1_period_wealth']for c in m.values()),phase[pk]['interval_wealth'],('semi126_sum',arm));assert len(buys)==(17 if arm=='D_GROSS10'else 18)
        assert summary[arm]['actually_bought_members']==len(buys)and summary[arm]['never_bought_members']==126-len(buys)
        semiaudit[arm]=dict(members=126,bought=len(buys),unbought=126-len(buys),wealth=str(sm(c['H1_period_wealth']for c in m.values())))
    pp=csvread(E/'SEMICONDUCTOR_D_H1_DAILY_CAPITAL_PATH.csv');nd=[r for r in days['strong','D_GROSS10']if'2026-01-01'<=r['at'][:10]<='2026-06-30'];assert len(pp)==len(nd)==116 and [r['day']for r in pp]==[r['at'][:10]for r in nd]
    trades=collections.defaultdict(list);divs=collections.defaultdict(lambda:Z)
    for t in books['strong','D_GROSS10']['trades']:
        if t['security_id']in ids:trades[t['at'][:10]].append(t)
    for e in books['strong','D_GROSS10']['audit']:
        if e['kind']=='dividend_accrual'and e['receivable']['security_id']in ids:divs[e['receivable']['ex_at'][:10]]+=D(e['receivable']['net_local'])
    prev=Z
    for p,n in zip(pp,nd):
        day=p['day'];tx=trades[day];bc=sm(D(t['gross_cny'])+D(t['fees_cny'])for t in tx if t['side']=='buy');sn=sm(D(t['gross_cny'])-D(t['fees_cny'])for t in tx if t['side']=='sell');inv=D(p['strict_semi_inventory'])
        near(p['own_NAV'],n['nav'],('dailyNAV',day));assert int(p['held_member_count'])==len({s for s,q in n['positions'].items()if s in ids and q})
        for field,val in [('actual_buy_cash',bc),('actual_sell_net',sn),('actual_fees',sm(t['fees_cny']for t in tx)),('recognized_dividend',divs[day]),('interval_wealth_increment',inv-prev+sn-bc+divs[day]),('strict_semi_weight_pct_NAV',inv/D(n['nav'])*100)]:near(p[field],val,(field,day))
        prev=inv
    near(sm(r['interval_wealth_increment']for r in pp),semiaudit['D_GROSS10']['wealth'],'116_daily_telescope');near(prev,phase['D_actual_stock_wealth']['inventory_end'],'D_ending_inventory')
    binding=jread(E/'SOURCE_BINDING.json')
    for p,h in binding['source_sha256'].items():assert sha(Path(p))==h
    for p,h in sources.items():assert sha(Path(p))==h
    return dict(passed=True,status='PASS_INDEPENDENT_THIN_DERIVED_TABLE_REVIEW',elapsed_seconds=time.monotonic()-begin,annual_halfyear_NAV_MDD_independently_recomputed=annual,complete_cohort_sets_and_original_reader_money=cohorts,semiconductor_all252_members_and_original_H1_wealth=semiaudit,D_semiconductor_116_days_flows_NAV_weight_and_telescope_exact=True,perstock_AR_unknown_preserved=True,no_new_account_prices_valuation_basis_or_native_import=True,scope_limits=['Daily semiconductor intermediate marked inventory is reused from the explanation existing-reader output, not independently repriced. Its flows, NAV, counts, weights, telescope, terminal inventory and original126-member H1 sums are checked.','Original finance/PVR/atomic and source-mark accuracy are reused; no new accounting engine or basis.','Posthoc winner/difference groups are descriptive; not signals, causal alpha or avoided losses.','Current126 membership snapshot is not PIT/OOS; electronics chemicals are excluded.'],source_SHA256=sources,reviewer_source_SHA256=sha(Path(__file__)))
try:
    r=run();(O/'AUDIT.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n');print('PASS',O/'AUDIT.json',sha(O/'AUDIT.json'))
except BaseException as e:
    r=dict(passed=False,error=repr(e),traceback=traceback.format_exc(),source_SHA256=sources);(O/'FAILED.json').write_text(json.dumps(r,indent=2)+'\n');raise
