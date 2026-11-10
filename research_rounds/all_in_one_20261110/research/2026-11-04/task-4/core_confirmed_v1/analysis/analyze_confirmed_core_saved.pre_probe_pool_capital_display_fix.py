"""Prepared read-only OFF/ON book comparison. Root executes after ON DONE.

No account, RiskBook, strategy Runner, fill or indicator is constructed here.
The previously audited native saved financial reader remains authoritative.
"""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
from decimal import Decimal as D, InvalidOperation
from bisect import bisect_left
import argparse, gzip, hashlib, importlib.util, json, sys, time

sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
WORK=O.parent.parent
OLD=WORK/'new_price_trend_v1'
BASE_READER=OLD/'analyze_saved_accounts.py'
PRICE_READER=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/c1-drawdown-capacity-20261101/analyze_saved.py')
META_SOURCE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
STOCK_MANIFEST=PRICE_READER.parent.parent/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
ROOTS={(w,'OFF'):OLD/'funding/runs'/(w+'_OFF')for w in ('long','strong')}
ROOTS.update({(w,'ON'):O.parent/'funding/runs'/(w+'_ON')for w in ('long','strong')})
WINDOWS={'long':(726,'2022-01-01','2022-01-04','2024-12-31'),
         'strong':(242,'2025-07-01','2025-07-01','2026-06-30')}
Z=D(0);EPS=D('.000001');SRC={};F=None;FACTS={}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):
    p=Path(p).resolve();SRC[str(p)]=sha(p);return p
def read(p):return json.loads(bind(p).read_text())
def load(p,lines=False):
    with gzip.open(bind(p),'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def maybe_num(x):
    try:v=D(str(x))
    except (InvalidOperation,ValueError,TypeError):return None
    return v if v.is_finite()else None
def num(x):
    v=maybe_num(x);assert v is not None,('nonfinite numeric saved field',str(x));return v
def eq(a,b,tag):assert abs(a-b)<EPS,(tag,str(a),str(b),str(a-b))
def stamp(x):return datetime.fromisoformat(str(x)).isoformat()

def load_reader():
    global F
    spec=importlib.util.spec_from_file_location('confirmed_core_unchanged_saved_finance',BASE_READER)
    F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
    F.OUT=O
    assert F.A.price is F.MARK.price,'Native stale/CA mark reader must remain installed'
    bind(BASE_READER);bind(OLD/'native_mark_reader.py');bind(F.PRICE_READER)
    assert Path(F.PRICE_READER)==PRICE_READER
    assert read(META_SOURCE)==F.A.META
    assert {r['symbol']:r for r in read(STOCK_MANIFEST)}==F.A.SM
    # Record the actual locally imported source closure without creating any
    # account or source-wide market. Native price data are bound on first use.
    for module in tuple(sys.modules.values()):
        p=getattr(module,'__file__',None)
        if p and str(p).endswith('.py')and str(p).startswith(('/Users/bytedance/Documents/Codex/','/Users/bytedance/Documents/ChatGPT/money/')):bind(p)
    return F

def factor(sid,day):
    if sid not in FACTS:
        import pandas as pd
        row=F.A.SM[sid];p=bind(row['refs']['facts'])
        assert SRC[str(p)]==row['output_sha256'][str(p)]
        FACTS[sid]=pd.read_parquet(p,columns=['factor'])
    import pandas as pd
    f=FACTS[sid];i=f.index.searchsorted(pd.Timestamp(day),side='right')-1
    if i<0:return None
    v=f.factor.iloc[i]
    n=maybe_num(v)
    return n if pd.notna(v)and n is not None and n>0 else None

def specs(days):
    periods={'all':list(days)}
    for year in sorted({d[:4]for d in days}):periods[year]=[d for d in days if d.startswith(year)]
    for name,lo,hi in [('after_924','2024-09-24','2024-12-31'),
                       ('rally_924_six_close','2024-09-24','2024-10-08'),
                       ('post_924_Oct9_yearend','2024-10-09','2024-12-31'),
                       ('2025H2','2025-07-01','2025-12-31'),('2026H1','2026-01-01','2026-06-30')]:
        a=[d for d in days if lo<=d<=hi]
        if a:periods[name]=a
    return periods

def event_key(layer,journal):
    role=journal['role'];epoch=tuple(layer.get('epoch')or())
    receipt=journal.get('CP1_id')if role=='mobile'else None
    return json.dumps([layer['sid'],stamp(layer['signal_at']),role,epoch,receipt],ensure_ascii=False,separators=(',',':'))

def aggregate_event(rows):
    out={}
    for r in rows:
        k=r['event_key']
        if k not in out:out[k]=dict(event_key=k,sid=r['sid'],signal_at=r['signal_at'],signal_day=r['signal_at'][:10],
            role=r['role'],epoch=r['epoch'],receipt=r['receipt'],layers=[],cost=Z,net=Z,entry_shares=0,
            entry_pools=[],confirmed_core_layers=[])
        z=out[k];z['layers'].append(r['layer']);z['cost']+=r['cost'];z['net']+=r['net'];z['entry_shares']+=r['entry_shares']
        z['entry_pools'].append(r['entry_pool'])
        if r['is_direct_confirmed_CORE']:z['confirmed_core_layers'].append(r['layer'])
    return out

def book_extension(name,root,financial):
    """Additional period/risk/actual-layer diagnostics over one completed book."""
    b=load(root/'pair/B.json.gz');ds=load(root/'pair/daily.jsonl.gz',True)
    byday={r['at'][:10]:r for r in ds};days=list(byday);period_days=specs(days)
    primary_daily=read(O/(name+'_DAILY.json'));fr={r['day']:r for r in primary_daily}
    final_layers={int(l['id']):l for l in b['layers']}
    actual_fills={int(j['layer']):j for j in b['journal']if j['kind']=='real_buy_fill'}
    financial_layers={int(l['layer']):l for l in financial['layers']}
    buys={int(t['layer']):t for t in b['trades']if t['side']=='buy'}
    assert len(buys)==sum(t['side']=='buy'for t in b['trades']),'Repeated buys into one layer need explicit native mapping; do not silently overwrite'
    assert set(actual_fills)==set(final_layers)==set(financial_layers)==set(buys)
    meta=F.A.META;assert len(F.A.SM)==1709
    industries={meta[s]['sector_id']:meta[s]['industry']for s in F.A.SM};assert len(industries)==90
    semis={s for s in F.A.SM if meta[s]['industry']=='半导体'};assert len(semis)==126
    riskrows=[];industry_riskrows=[];stockvalues={};industry_values={};positions={}
    before_on=True
    for r in ds:
        day=r['at'][:10];nav=num(r['nav']);heldrisk=Z;unknown=0;crossed=0;crossedvalue=Z
        poolrisk=defaultdict(lambda:dict(capital=Z,risk=Z,unknown=0))
        secrisk=defaultdict(lambda:dict(capital=Z,risk=Z,unknown=0,probe_risk=Z,confirmed_risk=Z))
        values={s:D(q)*F.A.price(s,day)for s,q in r['positions'].items()if q}
        eq(sum(values.values(),Z),num(r['inventory']),(name,day,'inventory extension'))
        for l in r['layers']:
            sid=l['sid'];q=D(l['qty']);f=factor(sid,day)
            line=maybe_num(l.get('last_core_line')if l['kind']=='core'else l.get('floor'))
            mark=F.A.price(sid,day);pool=l['pool'];sec=meta[sid]['sector_id']
            assert pool in ('probe','confirmed')
            poolrisk[pool]['capital']+=q*mark;secrisk[sec]['capital']+=q*mark
            if f is None or line is None:
                unknown+=1;poolrisk[pool]['unknown']+=1;secrisk[sec]['unknown']+=1;continue
            rawline=line/f;lr=q*max(Z,mark-rawline)
            heldrisk+=lr;poolrisk[pool]['risk']+=lr;secrisk[sec]['risk']+=lr;secrisk[sec][pool+'_risk']+=lr
            if mark<=rawline:crossed+=1;crossedvalue+=q*mark
        max_industry=max((z['risk']/nav*100 for z in secrisk.values()if not z['unknown']),default=Z)
        for sec,z in secrisk.items():
            industry_riskrows.append(dict(day=day,sector=sec,industry=industries[sec],NAV=nav,
                held_inventory=z['capital'],held_nominal_risk_known_subtotal=z['risk'],unknown_line_layers=z['unknown'],
                held_nominal_risk_pct=z['risk']/nav*100 if not z['unknown']else None,
                held_probe_risk=z['probe_risk'],held_confirmed_risk=z['confirmed_risk'],
                industry_1pct_CLOSE_reference_exceeded=z['risk']/nav>D('.01')if not z['unknown']else None,
                reference_scope='CLOSE held positions/current marks+lines only; excludes pending obligations. Reference exceedance is not an entry-contract failure.'))
        probe=r['pool_probe'];confirmed=r['pool_confirmed']
        bp=num(probe[1]);bc=num(confirmed[1]);total=bp+bc
        cashlike=sum((num(r[k])for k in ('available','order_reserved','settlement_locked','sale_receivable','dividend_receivable')),Z)-num(r['payable'])
        eq(cashlike+num(r['inventory']),nav,(name,day,'explicit cash-equivalent bridge'))
        riskrows.append(dict(day=day,NAV=nav,held_nominal_mark_to_line_risk=heldrisk,
            held_nominal_risk_pct=heldrisk/nav*100 if not unknown else None,unknown_line_layers=unknown,
            at_or_below_line_layers=crossed,at_or_below_line_inventory=crossedvalue,
            held_probe_risk_known_subtotal=poolrisk['probe']['risk'],held_confirmed_risk_known_subtotal=poolrisk['confirmed']['risk'],
            held_probe_risk_pct=poolrisk['probe']['risk']/nav*100 if not poolrisk['probe']['unknown']else None,
            held_confirmed_risk_pct=poolrisk['confirmed']['risk']/nav*100 if not poolrisk['confirmed']['unknown']else None,
            held_probe_capital_pct=poolrisk['probe']['capital']/nav*100,
            probe_0p5pct_CLOSE_reference_exceeded=poolrisk['probe']['risk']/nav>D('.005')if not poolrisk['probe']['unknown']else None,
            probe_2pct_capital_CLOSE_reference_exceeded=poolrisk['probe']['capital']/nav>D('.02'),
            maximum_known_held_industry_risk_pct=max_industry,
            industry_1pct_CLOSE_reference_exceedances=sum(z['risk']/nav>D('.01')for z in secrisk.values()if not z['unknown']),
            budget_probe_risk=bp,budget_confirmed_risk=bc,budget_total_risk=total,
            budget_probe_risk_pct=bp/nav*100,budget_confirmed_risk_pct=bc/nav*100,budget_total_risk_pct=total/nav*100,
            budget_minus_held_risk=total-heldrisk if not unknown else None,
            probe_capital=num(probe[0]),confirmed_capital=num(confirmed[0]),
            available=num(r['available']),available_pct=num(r['available'])/nav*100,
            order_reserved=num(r['order_reserved']),sale_receivable=num(r['sale_receivable']),
            dividend_receivable=num(r['dividend_receivable']),cash_equivalent=cashlike,cash_equivalent_pct=cashlike/nav*100,
            settlement_locked=num(r['settlement_locked']),payable=num(r['payable']),
            ACT_on=bool(r['on']),ACT_pause_transition=before_on and not r['on'],ACT_recovery_transition=not before_on and r['on']))
        before_on=bool(r['on']);stockvalues[day]=values;positions[day]=dict(r['positions'])
        sec=defaultdict(lambda:Z)
        for sid,v in values.items():sec[meta[sid]['sector_id']]+=v
        industry_values[day]=sec
    rr={r['day']:r for r in riskrows}
    layer_rows=[]
    for lid,l in final_layers.items():
        j=actual_fills[lid];fl=financial_layers[lid]
        layer_rows.append(dict(layer=lid,sid=l['sid'],signal_at=stamp(l['signal_at']),opened=stamp(l['opened']),
            closed=stamp(l['closed'])if l['closed']else None,role=j['role'],epoch=l.get('epoch'),receipt=j.get('CP1_id'),
            budget_order=j.get('budget_order',b.get('metadata',{}).get(str(lid),{}).get('budget_order')),
            entry_pool=j.get('pool'),is_direct_confirmed_CORE=j['role']=='core'and j.get('pool')=='confirmed',
            entry_shares=int(buys[lid]['shares']),cost=num(fl['cost']),net=num(fl['net']),event_key=event_key(l,j)))
    if name.endswith('_OFF'):assert not any(r['is_direct_confirmed_CORE']for r in layer_rows),'Original CORE entry must not be inferred from later migration'
    boundary_days={period_days[p][0]for p in period_days}|{period_days[p][-1]for p in period_days}
    previous={days[i]:(days[i-1]if i else None)for i in range(len(days))}
    boundary_days|={previous[d]for d in list(boundary_days)if previous[d]is not None}
    boundary_layers={d:{int(l['id']):l for l in byday[d]['layers']}for d in boundary_days}
    wealth_cache={}
    def layer_wealth(day):
        if day is None:return {lid:Z for lid in final_layers}
        if day in wealth_cache:return wealth_cache[day]
        out={}
        for lid,l in final_layers.items():
            if l['opened'][:10]>day:out[lid]=Z;continue
            v=boundary_layers[day].get(lid)
            if v is None:
                assert l['closed']and l['closed'][:10]<=day,(name,day,lid,'missing not-yet-closed layer')
                v=l
            q=D(v['qty']);out[lid]=num(v['cash'])+num(v['dividend'])+(q*F.A.price(v['sid'],day)if q else Z)
        eq(sum(out.values(),Z)+D(1000000),num(byday[day]['nav']),(name,day,'layer boundary NAV'))
        wealth_cache[day]=out;return out
    periods={};sector_periods=[];stock_periods=[];role_periods=[]
    layerinfo={r['layer']:r for r in layer_rows};layers_by_sid=defaultdict(list)
    for r in layer_rows:layers_by_sid[r['sid']].append(r)
    for period,pdays in period_days.items():
        rows=[fr[d]for d in pdays];a=F.period(rows);r=[rr[d]for d in pdays]
        def mean(field):return sum((num(x[field])for x in r),Z)/len(r)
        a.update(mean_available_pct=mean('available_pct'),mean_cash_equivalent_pct=mean('cash_equivalent_pct'),
            mean_budget_total_risk_pct=mean('budget_total_risk_pct'),peak_budget_total_risk_pct=max(x['budget_total_risk_pct']for x in r),
            mean_probe_risk_pct=mean('budget_probe_risk_pct'),peak_probe_risk_pct=max(x['budget_probe_risk_pct']for x in r),
            mean_confirmed_risk_pct=mean('budget_confirmed_risk_pct'),peak_confirmed_risk_pct=max(x['budget_confirmed_risk_pct']for x in r),
            held_risk_unknown_CLOSEs=sum(x['unknown_line_layers']>0 for x in r),
            mean_held_nominal_risk_pct=mean('held_nominal_risk_pct')if all(x['held_nominal_risk_pct']is not None for x in r)else None,
            mean_held_probe_risk_pct=mean('held_probe_risk_pct')if all(x['held_probe_risk_pct']is not None for x in r)else None,
            peak_held_probe_risk_pct=max(x['held_probe_risk_pct']for x in r)if all(x['held_probe_risk_pct']is not None for x in r)else None,
            probe_0p5pct_CLOSE_reference_exceedance_days=sum(x['probe_0p5pct_CLOSE_reference_exceeded']is True for x in r),
            industry_1pct_CLOSE_reference_exceedance_days=sum(x['industry_1pct_CLOSE_reference_exceedances']>0 for x in r),
            peak_known_held_industry_risk_pct=max(x['maximum_known_held_industry_risk_pct']for x in r),
            ACT_pause_dates=[x['day']for x in r if x['ACT_pause_transition']],ACT_recovery_dates=[x['day']for x in r if x['ACT_recovery_transition']],
            mean_order_reserved=mean('order_reserved'),mean_sale_receivable=mean('sale_receivable'),mean_dividend_receivable=mean('dividend_receivable'))
        periods[period]=a;begin=previous[pdays[0]];end=pdays[-1]
        wa,wb=layer_wealth(begin),layer_wealth(end);stockdelta=defaultdict(lambda:Z);roledelta=defaultdict(lambda:Z)
        for lid in final_layers:
            change=wb[lid]-wa[lid];info=layerinfo[lid];stockdelta[info['sid']]+=change
            cohort='direct_confirmed_CORE'if info['is_direct_confirmed_CORE']else'other_CORE'if info['role']=='core'else'MOBILE'
            roledelta[cohort]+=change
        eq(sum(stockdelta.values(),Z),a['wealth_change'],(name,period,'stock period wealth'))
        eq(sum(roledelta.values(),Z),a['wealth_change'],(name,period,'role period wealth'))
        for cohort in ('direct_confirmed_CORE','other_CORE','MOBILE'):
            role_periods.append(dict(period=period,cohort=cohort,wealth_change=roledelta[cohort]))
        for sid in sorted(F.A.SM):
            held=[d for d in pdays if stockvalues[d].get(sid,Z)>0]
            fill=[x for x in layers_by_sid[sid]if pdays[0]<=x['opened'][:10]<=end]
            stock_periods.append(dict(period=period,sid=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],
                wealth_change=stockdelta[sid],mean_NAV_weight_pct=sum((stockvalues[d].get(sid,Z)/num(byday[d]['nav'])*100 for d in pdays),Z)/len(pdays),
                held_CLOSEs=len(held),buy_fills=len(fill),buy_cash=sum((x['cost']for x in fill),Z),
                beginning_inventory=stockvalues[begin].get(sid,Z)if begin else Z,ending_inventory=stockvalues[end].get(sid,Z)))
        for sector,industry in sorted(industries.items()):
            members={s for s in F.A.SM if meta[s]['sector_id']==sector}
            sector_periods.append(dict(period=period,sector=sector,industry=industry,
                wealth_change=sum((stockdelta[s]for s in members),Z),
                mean_NAV_weight_pct=sum((industry_values[d].get(sector,Z)/num(byday[d]['nav'])*100 for d in pdays),Z)/len(pdays)))
    save(name+'_PERIODS.json',periods);save(name+'_RISK_CASH_DAILY.json',riskrows)
    save(name+'_HELD_INDUSTRY_RISK_DAILY.json',industry_riskrows)
    save(name+'_ALL90_INDUSTRY_PERIODS.json',sector_periods);save(name+'_ALL1709_STOCK_PERIODS.json',stock_periods)
    save(name+'_ROLE_PERIOD_WEALTH.json',role_periods);save(name+'_ACTUAL_FILLED_EVENTS.json',list(aggregate_event(layer_rows).values()))
    save(name+'_ENTRY_LAYER_IDENTITIES.json',layer_rows)
    trace_confirmed(name,root,b,ds,layer_rows)
    return dict(periods=periods,industry=sector_periods,stock_periods=stock_periods,role_periods=role_periods,
                events=aggregate_event(layer_rows),layers=layer_rows,positions=positions,stockvalues=stockvalues)

def trace_confirmed(name,root,b,ds,layer_rows):
    """Journal entry pool identifies adoption; migration does not create an entry."""
    grantpath=root/'pair/core-confirmed.jsonl.gz';proofpath=root/'pair/core-proof.jsonl.gz'
    grants=load(grantpath,True)if grantpath.exists()else[]
    proofs=load(proofpath,True)if proofpath.exists()else[]
    reserved={r['budget_order']:r for r in grants if r.get('result')=='reserved'and r.get('budget_order')}
    attempts=Counter(r.get('result','UNKNOWN')for r in grants)
    save(name+'_CORE_CONFIRMED_ATTEMPT_STREAM.json',dict(stream_present=grantpath.exists(),rows=grants,
        proof_stream_present=proofpath.exists(),proof_rows=proofs,results=dict(attempts),
        scope='Raw mechanism evidence retained. Actual adoption requires native real_buy_fill core+confirmed.'))
    final={int(l['id']):l for l in b['layers']};traces=[]
    for info in layer_rows:
        if not info['is_direct_confirmed_CORE']:continue
        lid=info['layer'];sid=info['sid'];l=final[lid];timeline=[]
        for r in ds:
            day=r['at'][:10];v=next((z for z in r['layers']if int(z['id'])==lid),None)
            if v is None:continue
            mark=F.A.price(sid,day);f=factor(sid,day);line=maybe_num(v.get('last_core_line'))
            rawline=line/f if line is not None and f is not None else None
            timeline.append(dict(day=day,qty=v['qty'],raw_mark=mark,current_I_line_adjusted=line,
                current_I_line_raw=rawline,actual_pool_that_CLOSE=v['pool'],NAV=r['nav'],
                inventory=D(v['qty'])*mark,weight_pct=D(v['qty'])*mark/num(r['nav'])*100,
                nominal_mark_to_line_risk=D(v['qty'])*max(Z,mark-rawline)if rawline is not None else None,
                cumulative_layer_cash=v['cash'],cumulative_recognized_dividend=v['dividend'],ACT_on=r['on']))
        exits=[r for r in b['audit']if r['kind']=='pilot_layer_exit'and lid in r.get('layers',())]
        sells=[]
        for t in b['trades']:
            if t['side']!='sell':continue
            for part in t.get('parts',()):
                if int(part['layer'])==lid:
                    sells.append(dict(at=t['at'],stock_total_shares=t['shares'],stock_total_fee=t['fees_cny'],
                                      layer_part=part,fee_scope='Whole stock fee is context only; part.net_cash already allocates it once.'))
        flat=next((r['at'][:10]for r in ds if l['closed']and stamp(r['at'])>=stamp(l['closed'])and not r['positions'].get(sid,0)),None)
        later=next((t for t in b['trades']if t['side']=='buy'and t['security_id']==sid and flat and t['at'][:10]>flat),None)
        linked=reserved.get(info['budget_order'])
        cp_matches=bool(linked and info['receipt']and linked.get('receipt_id')==info['receipt'])
        traces.append(dict(**info,lifecycle_net=info['net'],mechanism_record=linked,CP_receipt_matches=cp_matches,
            mechanism_link_status='exact_budget_order'if linked else'NO_EXACT_ATTEMPT_LINK',
            actual_holding_timeline=timeline,original_exit_proposals=exits,actual_sell_allocations=sells,
            first_later_stock_flat_CLOSE=flat,next_actual_buy_after_flat_CLOSE=later,
            reentry_scope='CLOSE-confirmed flat followed by actual later buy; not a synthetic restored order.'))
    save(name+'_DIRECT_CONFIRMED_CORE_TRAJECTORIES.json',traces)
    save(name+'_MECHANISM_ADOPTION_SUMMARY.json',dict(attempt_stream_present=grantpath.exists(),attempt_results=dict(attempts),
        direct_confirmed_core_layers=len(traces),actual_buy_cash=sum((r['cost']for r in traces),Z),
        lifecycle_net=sum((r['net']for r in traces),Z),unlinked_actual_layers=[r['layer']for r in traces if r['mechanism_record']is None],
        nonmatching_CP_actual_layers=[r['layer']for r in traces if not r['CP_receipt_matches']],
        attribution='Cohort descriptive only. Its profit is not the ON-OFF portfolio increment.'))

def opportunity_context(root,wanted):
    """Literal original planning/funding records for actual changed filled cohorts."""
    out={k:dict(opportunity=None,funding_outcomes=[])for k in wanted}
    lookup=defaultdict(list)
    for key in wanted:
        sid,signal,role,epoch,receipt=json.loads(key);lookup[(sid,signal[:10],role)].append(key)
    op=root/'pair/opportunities.jsonl.gz'
    if op.exists():
        with gzip.open(bind(op),'rt')as h:
            for line in h:
                r=json.loads(line)
                for role in ('core','mobile'):
                    for key in lookup.get((r['sid'],r['day'],role),()):out[key]['opportunity']=r
    ds=load(root/'pair/daily.jsonl.gz',True);closes=[datetime.fromisoformat(r['at'])for r in ds]
    fp=root/'pair/funding.jsonl.gz'
    if fp.exists():
        with gzip.open(bind(fp),'rt')as h:
            for line in h:
                r=json.loads(line);at=datetime.fromisoformat(r['at'])
                if at.hour==15:signalday=at.date().isoformat()
                else:
                    i=bisect_left(closes,at)-1
                    if i<0:continue
                    signalday=closes[i].date().isoformat()
                for key in lookup.get((r['sid'],signalday,r['role']),()):out[key]['funding_outcomes'].append(r)
    return out

def compare(window,records):
    a,b=records['OFF'],records['ON'];old,new=a['financial'],b['financial'];ae,be=a['extension'],b['extension']
    delta=[];oldstocks={r['sid']:r for r in old['stocks']};newstocks={r['sid']:r for r in new['stocks']}
    for sid in sorted(set(oldstocks)|set(newstocks)):
        x,y=oldstocks.get(sid),newstocks.get(sid)
        delta.append(dict(sid=sid,name=F.A.META[sid]['name'],industry=F.A.META[sid]['industry'],OFF=x,ON=y,
                          net_delta=(num(y['net'])if y else Z)-(num(x['net'])if x else Z)))
    ending=num(be['periods']['all']['end_NAV'])-num(ae['periods']['all']['end_NAV'])
    eq(sum((r['net_delta']for r in delta),Z),ending,(window,'all stock deltas equals NAV difference'))
    events=[]
    for key in sorted(set(ae['events'])|set(be['events'])):
        x,y=ae['events'].get(key),be['events'].get(key)
        changed=not(x and y)or any(x[f]!=y[f]for f in ('cost','net','entry_shares','entry_pools'))
        events.append(dict(event_key=key,status='common_actual_fill'if x and y else'OFF_only_actual_fill'if x else'ON_only_actual_fill',
            actual_path_changed=changed,OFF=x,ON=y,net_delta=(num(y['net'])if y else Z)-(num(x['net'])if x else Z)))
    eq(sum((r['net_delta']for r in events),Z),ending,(window,'all filled event deltas equals NAV difference'))
    changed={r['event_key']for r in events if r['actual_path_changed']}
    contexts=opportunity_context(ROOTS[window,'ON'],changed)
    oldcontexts=opportunity_context(ROOTS[window,'OFF'],changed)
    on_signal_core=defaultdict(list)
    for r in be['layers']:
        if r['is_direct_confirmed_CORE']:on_signal_core[(r['sid'],r['signal_at'])].append(r)
    mobile=[]
    for r in events:
        x=r['OFF']
        if x and x['role']=='mobile'and r['actual_path_changed']:
            mobile.append(dict(**r,same_signal_ON_confirmed_CORE=on_signal_core.get((x['sid'],x['signal_at']),[]),
                ON_observed_context=contexts.get(r['event_key']),OFF_observed_context=oldcontexts.get(r['event_key']),
                interpretation='Actual changed role/quantity/holding path, not isolated deletion profit or proof of a unique gate.'))
    stock_period_delta=[]
    ap={(r['period'],r['sid']):r for r in ae['stock_periods']};bp={(r['period'],r['sid']):r for r in be['stock_periods']}
    for key in sorted(ap):
        x,y=ap[key],bp[key]
        stock_period_delta.append(dict(period=key[0],sid=key[1],industry=x['industry'],
            OFF=x,ON=y,wealth_delta=num(y['wealth_change'])-num(x['wealth_change'])))
    for period in ae['periods']:
        expected=num(be['periods'][period]['wealth_change'])-num(ae['periods'][period]['wealth_change'])
        eq(sum((r['wealth_delta']for r in stock_period_delta if r['period']==period),Z),expected,(window,period,'period stock delta bridge'))
    winners=[]
    for x in sorted(old['stocks'],key=lambda r:-num(r['net']))[:10]:
        sid=x['sid'];y=newstocks.get(sid)
        old_days=[d for d,q in ae['positions'].items()if q.get(sid,0)]
        overlap=[d for d in old_days if be['positions'][d].get(sid,0)]
        old_w=sum((ae['stockvalues'][d].get(sid,Z)/num(a['daily_NAV'][d])*100 for d in old_days),Z)
        new_w=sum((be['stockvalues'][d].get(sid,Z)/num(b['daily_NAV'][d])*100 for d in old_days),Z)
        winners.append(dict(original_winner=x,ON=y,original_holding_CLOSEs=len(old_days),ON_overlap_holding_CLOSEs=len(overlap),
            overlap_fraction=D(len(overlap))/len(old_days)if old_days else None,
            sum_original_holding_window_weights_pct=old_w,sum_ON_weights_on_same_original_days_pct=new_w,
            capital_participation_ratio=new_w/old_w if old_w else None,
            scope='Fixed original top10 evaluation cohort; weights normalized by each path own NAV.'))
    save(window+'_STOCK_DELTAS.json',sorted(delta,key=lambda r:-r['net_delta']))
    save(window+'_ALL_FILLED_EVENT_DELTAS.json',events)
    save(window+'_ORIGINAL_MOBILE_PATH_CHANGES.json',mobile)
    save(window+'_CHANGED_EVENT_ON_CONTEXT.json',contexts)
    save(window+'_CHANGED_EVENT_OFF_CONTEXT.json',oldcontexts)
    save(window+'_ALL_PERIOD_STOCK_WEALTH_DELTAS.json',stock_period_delta)
    save(window+'_ORIGINAL_TOP10_WINNER_RETENTION.json',winners)
    return dict(OFF=ae['periods'],ON=be['periods'],terminal_NAV_delta=ending,
        stock_delta_bridge_exact=True,filled_event_delta_bridge_exact=True,
        common_actual_fill_events=sum(r['status']=='common_actual_fill'for r in events),
        old_only_actual_fill_events=sum(r['status']=='OFF_only_actual_fill'for r in events),
        new_only_actual_fill_events=sum(r['status']=='ON_only_actual_fill'for r in events))

def semiconductor(records):
    all126={s for s in F.A.SM if F.A.META[s]['industry']=='半导体'};assert len(all126)==126
    rows=[];summary={}
    for mode in ('OFF','ON'):
        ext=records['strong'][mode]['extension'];p=ext['periods']['2026H1']
        a=[r for r in ext['stock_periods']if r['period']=='2026H1'and r['sid']in all126];assert len(a)==126
        for r in a:rows.append(dict(mode=mode,**r,contribution_pct_own_H1_start_NAV=num(r['wealth_change'])/num(p['begin_NAV'])*100))
        sector=next(r for r in ext['industry']if r['period']=='2026H1'and r['industry']=='半导体')
        eq(sum((num(r['wealth_change'])for r in a),Z),sector['wealth_change'],(mode,'all126 H1 contribution'))
        eq(sum((num(r['mean_NAV_weight_pct'])for r in a),Z),sector['mean_NAV_weight_pct'],(mode,'all126 H1 exposure'))
        summary[mode]=dict(stocks=126,actually_held_stocks=sum(r['held_CLOSEs']>0 for r in a),
            actual_buy_fills=sum(r['buy_fills']for r in a),new_buy_stocks=sum(r['buy_fills']>0 for r in a),
            buy_cash=sum((num(r['buy_cash'])for r in a),Z),wealth_change=sector['wealth_change'],
            mean_NAV_weight_pct=sector['mean_NAV_weight_pct'],own_H1_start_NAV=p['begin_NAV'],
            beginning_inventory=sum((num(r['beginning_inventory'])for r in a),Z),
            ending_inventory=sum((num(r['ending_inventory'])for r in a),Z))
    save('SEMICONDUCTOR_ALL126_H1_PARTICIPATION.json',rows);save('SEMICONDUCTOR_H1_COMPARISON.json',summary)

def prepare():
    begin=time.monotonic();planned={}
    for key,root in ROOTS.items():
        w,mode=key;planned[w+'_'+mode]=dict(root=str(root),DONE_present=(root/'DONE.json').exists(),
            required=[str(root/p)for p in ('DONE.json','pair/B.json.gz','pair/daily.jsonl.gz','pair/balances.jsonl.gz')],
            optional_mechanism_streams=[str(root/'pair/core-confirmed.jsonl.gz'),str(root/'pair/core-proof.jsonl.gz')])
    sources={str(p.resolve()):sha(p)for p in [Path(__file__),O/'METHODS.txt',BASE_READER,OLD/'native_mark_reader.py',PRICE_READER,META_SOURCE,STOCK_MANIFEST]}
    save('PREPARATION.json',dict(status='PREPARED_ONLY_WAIT_ROOT_ON_COMPLETION',inputs=planned,source_sha256=sources,
        new_accounts=0,new_RiskBooks=0,new_market_preparations=0,saved_financial_analysis_executed=False,
        execute_command='PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<existing_pyarrow_reader> python3 core_confirmed_v1/analysis/analyze_confirmed_core_saved.py --execute',
        seconds=time.monotonic()-begin))
    print('PREPARED_ONLY')

def execute():
    start=time.monotonic()
    # Check completion before importing the original financial reader or reading prices.
    for (w,mode),root in ROOTS.items():
        assert read(root/'DONE.json')['completed'],(w,mode,'not completed')
        for file in ('pair/B.json.gz','pair/daily.jsonl.gz','pair/balances.jsonl.gz'):assert(root/file).is_file()
        if mode=='ON':
            for stream in ('core-confirmed','core-proof'):assert(root/'pair'/(stream+'.jsonl.gz')).is_file(),(w,stream,'expected ON mechanism evidence missing')
    load_reader();bind(__file__);bind(O/'METHODS.txt');data=defaultdict(dict)
    for window,(count,initial,first,last)in WINDOWS.items():
        for mode in ('OFF','ON'):
            name=window+'_'+mode;root=ROOTS[window,mode]
            financial=F.analyze(name,root,count,initial)
            daily=read(O/(name+'_DAILY.json'));assert daily[0]['day']==first and daily[-1]['day']==last
            extension=book_extension(name,root,financial)
            data[window][mode]=dict(financial=financial,extension=extension,daily_NAV={r['day']:r['end_NAV']for r in daily})
            save('ANALYSIS_PROGRESS.json',dict(last_completed_book=name,seconds=time.monotonic()-start,new_accounts=0))
    comparisons={window:compare(window,data[window])for window in WINDOWS}
    semiconductor(data);save('ACCOUNT_COMPARISONS.json',comparisons)
    SRC.update(F.SRC);SRC.update(F.MARK.sources)
    save('NATIVE_DERIVED_EX_MARK_REFERENCES.json',F.MARK.derived_marks);save('SOURCE_SHA256.json',SRC)
    save('SCOPE.json',dict(seconds=time.monotonic()-start,new_accounts=0,new_RiskBooks=0,new_market_preparations=0,
        financial_reader_reused=str(BASE_READER),native_mark_reader_reused=str(OLD/'native_mark_reader.py'),
        mechanism='Original probe q0 with only probe_risk/sector_capital, simultaneous original I/CP and mature industry; typed confirmed CORE actual entries.',
        risk='New confirmed CORE bypasses probe0.5%/2% restrictions. Industry1%, originalI.25% entry sizing and cash10% are not a guarantee of unchanged total risk.',
        attribution='All actual stock and filled-event deltas conserve ON-OFF terminal NAV; period contributions use own path starting NAV and include carry positions.',
        limitations='Current survivor/industry sample and daily execution proxies; no new signal or future-outcome selection; no PIT/OOS/live claim.'))
    print(json.dumps(comparisons,ensure_ascii=False,indent=2,default=str))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true')
    a=p.parse_args();assert a.prepare!=a.execute,'Choose prepare or explicit root-authorized saved analysis execution'
    if a.prepare:prepare()
    else:execute()
