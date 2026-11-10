"""Saved normal-vs-D1 financial and whole-pipeline evidence; no replay."""
from pathlib import Path
from decimal import Decimal as D
import bisect, collections, gzip, json, pickle, statistics, time
import composition as A
J,L,N,IO,Q,O,W=A.J,A.L,A.N,A.IO,A.Q,A.O,A.W
ROOT=O/'run-PVR-D1';NORMAL=A.P/'runs/2025_26';Z=D(0)
B=A.load('PVR_D1_saved_audited_math',A.P/'analyze_results.py')
B.O=O;B.M.O=O;B.A.O=O

def n(x):return D(str(x))
def day(x):return str(x)[:10]
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):IO.write_json(O/p,J.W.canon(x))

def real_bridge(b):
    costs=collections.defaultdict(lambda:Z);gross=collections.defaultdict(lambda:Z)
    for t in b['trades']:
        if t['side']=='buy':costs[t['layer']]+=n(t['gross_cny'])+n(t['fees_cny']);gross[t['layer']]+=n(t['gross_cny'])
    realized=unrealized=div=Z;partials=[]
    sold={p['layer'] for t in b['trades'] if t['side']=='sell' for p in t['parts']}
    for l in b['layers']:
        lid=l['id'];value=D(l['qty'])*B.A.price(l['sid'],'2026-06-30') if l['qty'] else Z
        basis=D(l['qty'])*n(b['metadata'][str(lid)]['unit_cost'])*costs[lid]/gross[lid] if l['qty'] else Z
        realized+=n(l['cash'])+basis;unrealized+=value-basis;div+=n(l['dividend'])
        if l['qty'] and lid in sold:partials.append(lid)
    residual=D(1000000)+realized+unrealized+div-n(b['ending_NAV'])
    assert abs(residual)<D('.0000001')
    return dict(realized_trading_net=realized,unrealized_net_mark_minus_allocated_buy_cost=unrealized,
        recognized_dividends=div,open_layers_with_partial_sales=partials,residual=residual,
        basis_rule='actual remaining qty * native split-adjusted unit_cost, buy fees allocated pro rata; original audited method',
        recognized_dividends_include_receivables_not_all_cash_paid=True)

def verify():
    assert read(ROOT/'DONE.json')['completed']
    frozen=read(ROOT/'FROZEN_RUN_METADATA.json')['sources']
    assert all(A.sha(p)==h for p,h in frozen.items())
    with gzip.open(ROOT/'pair/B.json.gz','rt') as f:b=json.load(f)
    ds=rows(ROOT/'pair/daily.jsonl.gz');br=rows(ROOT/'pair/balances.jsonl.gz')
    assert len(ds)==len(br)==242
    events=[];splits=[x for x in b['audit'] if x['kind']=='split']
    for i,t in enumerate(b['trades']):events.append((str(t['at']),1,i,'trade',t))
    for i,x in enumerate(splits):events.append((str(x['at']),0,i,'split',x))
    events.sort(key=lambda x:x[:3]);qty=collections.defaultdict(int);fee=Z;k=0
    for d in ds:
        while k<len(events) and events[k][0]<=d['at']:
            _,_,_,kind,x=events[k];k+=1
            if kind=='split':qty[x['sid']]=int(D(qty[x['sid']])*n(x['ratio']))
            else:qty[x['security_id']]+=(1 if x['side']=='buy' else -1)*x['shares'];fee+=n(x['fees_cny'])
        assert {s:q for s,q in qty.items() if q}=={s:q for s,q in d['positions'].items() if q}
        assert fee==n(d['fees_cny'])
    for x in br:
        for key in ('independent_NAV_difference','budget_NAV_difference','spendable_difference',
                    'reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference'):
            assert abs(n(x[key]))<D('.000001')
        assert all(abs(n(v))<D('.000001') for v in x['pool_occupancy_difference'].values())
    N.configure_scores();ranked=NA=0
    for d in b['decisions']:
        keys,log=N.priority_plan([dict(i,rank=i['original_H1_rank']) for i in d['intents']],N.SCORES.at,day(d['at']))
        assert all(keys[i['sid']]==i['priority_rank']==i['rank'] for i in d['intents'])
        ranked+=len(log);NA+=sum(not x['PVR_ready'] for x in log)
    snapshot={day(d['at']):d for d in ds};quarters=[]
    for path in sorted(ROOT.glob('checkpoint-*.pkl')):
        prov=read(path.with_suffix('.provenance.json'))
        assert prov['checkpoint_sha256']==A.sha(path)
        identity=prov['engine_identity']
        assert identity['trading_class']['module_sha256']==A.sha(O/'composition.py')
        for name,fn in [('planning',A.Composition.planning),('opening',A.E.Pair.opening),('route',A.E.BASE.Runner.route)]:
            assert identity['functions'][name]['code_sha256']==IO._code_fingerprint(fn.__code__)
        p=pickle.loads(path.read_bytes());a=p['accounts']['B'];d=str(p['last_completed_event'].date())
        assert p['source_freeze']==frozen and p['runner']['rank_mode']=='PVR_SLOT1' and p['runner']['d1_enabled']
        assert a['d1_enabled'] and a['delay_events']==1 and a['cost_multiplier']==1 and not a['d1_account_cap']
        assert type(a['budget']) is A.E.BASE.NoAccountBudget and not hasattr(a['budget'],'grants') and not hasattr(a['budget'],'c1')
        assert a['current_nav']==n(snapshot[d]['nav'])
        assert {s:x.shares for s,x in a['positions'].items()}==snapshot[d]['positions']
        assert all(i['rank']==i['priority_rank'] for i in a['pending'])
        quarters.append(dict(day=d,checkpoint_sha256=A.sha(path),identity_exact=True,NAV=str(a['current_nav'])))
    assert len(quarters)==4
    final=pickle.loads((ROOT/'checkpoint.pkl').read_bytes());a=final['accounts']['B']
    cal=[x.date() for x in a['d1_calendar']]
    waits=0
    for order in a['d1_orders'].values():
        if order['first_wait'] is None:continue
        waits+=1;j=bisect.bisect_right(cal,order['first_wait'].date())
        assert order['retry_at'].date()==cal[j] and order['expiry_day']==cal[j]
    reserve=[x for x in b['journal'] if x['kind']=='real_reserve' and x['role']=='mobile']
    ids=[x['receipt'] for x in reserve];assert len(ids)==len(set(ids)), 'canonical receipt reserved twice'
    cache=0
    for manifest in (L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json'):
        for record in read(manifest):
            for path,h in record['output_sha256'].items():assert A.sha(path)==h;cache+=1
    result=dict(passed=True,daily_cash_equity_pool_bridges=242,independent_share_and_fee_rebuild_days=242,
        fills=len(b['trades']),splits=len(splits),quarter_checkpoints=quarters,
        decision_priority_recomputed_days=242,unique_stock_day_slots=ranked,NA_fixed_slots=NA,
        canonical_mobile_reservations_consumed_once=len(ids),D1_buy_wait_next_market_day_checks=waits,
        source_and_cache_hashes_verified=cache,full_prefix_history_byte_digests_exact=read(ROOT/'EXECUTION_STATUS.json')['old_prefix_all_history_exact'],
        technical_prefix_reexecuted=False,new_financial_paths=1,SC_April2_or_later_events=0)
    save(Path('run-PVR-D1')/'VERIFICATION.json',result)
    print('PVR_D1_FINANCIAL_VERIFIED',len(b['trades']),cache,flush=True)

def first_entry_compare(data):
    first={ref:{sid:min((x['opened'] for x in a['layers'] if x['sid']==sid)) for sid in {x['sid'] for x in a['layers']}}
           for ref,a in data.items()}
    out=[]
    for sid in sorted(set(first['normal'])|set(first['D1'])):
        aa,bb=first['normal'].get(sid),first['D1'].get(sid)
        out.append(dict(sid=sid,name=B.META[sid]['name'],normal_first_fill=aa,D1_first_fill=bb,
            change='new_funded' if aa is None else 'lost_funded' if bb is None else
              'later' if bb>aa else 'earlier' if bb<aa else 'same',
            unit='first real stock fill; timing difference also includes subsequent resource/ACT/role path feedback'))
    return out

def run():
    started=time.monotonic();verify()
    data={ref:B.A.account('2025_26',ref,root) for ref,root in [('normal',NORMAL),('D1',ROOT)]}
    sets={ref:B.M.participation(a) for ref,a in data.items()};changes={}
    for key in sets['normal']:
        changes[key]=dict(normal=len(sets['normal'][key]),D1=len(sets['D1'][key]),
            gained=sorted(sets['D1'][key]-sets['normal'][key]),lost=sorted(sets['normal'][key]-sets['D1'][key]))
    save(Path('analysis/2025_26')/'FUNDED_CHANGES.json',changes)
    first=first_entry_compare(data);save(Path('analysis/2025_26')/'FIRST_ACTUAL_ENTRY_COMPARISON.json',first)
    metrics={};paths={};allactions={}
    for ref,a in data.items():
        root=NORMAL if ref=='normal' else ROOT;b=a['book'];actions=B.entry_actions(a);exits=B.exit_chain(a);allactions[ref]=actions
        pools=B.M.pool_and_waits('2025_26',ref,a);conc=B.concentration(a)
        reserved=[x for x in b['journal'] if x['kind']=='real_reserve']
        filled={x['budget_order'] for x in b['journal'] if x['kind']=='real_buy_fill'}
        metrics[ref]=dict(**a['metrics'],contributions=B.M.contribution(a['layers']),
            actual_realized_unrealized_dividends=real_bridge(b),**pools,
            admissions=len(reserved),actual_filled_orders=len(filled),
            zero_fill_reservations=sum(x['budget_order'] not in filled for x in reserved),
            funded_stocks=len(sets[ref]['all_stocks']),funded_attempts=len(sets[ref]['all_attempts']),
            entry_actions={kind:B.M.contribution([l for l in a['layers'] if l['layer'] in
                {x['layer'] for x in actions if x['action']==kind}]) for kind in
                ('first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat')},
            role_pool_at_fill={role+'_'+pool:B.M.contribution([x for x in a['layers']
                if x['role']==role and x['pool_at_fill']==pool]) for role in ('core','mobile') for pool in ('probe','confirmed')},
            exit_request_layers=len(exits),exit_layers_with_first_actual_sell=sum(x['first_actual_sell'] is not None for x in exits),
            exit_request_to_first_actual_sell_observations=dict(collections.Counter(str(x['market_observations_to_first_sell']) for x in exits)),
            terminal_stock_exit_obligations=len(b['exits']),terminal_active_buy_orders=len(b['orders']),
            concentration={k:v for k,v in conc.items() if k!='daily'})
        save(Path('analysis/2025_26')/ref/'ENTRY_ACTIONS.json',actions)
        save(Path('analysis/2025_26')/ref/'EXIT_REQUESTS_AND_ACTUAL_SELLS.json',exits)
        save(Path('analysis/2025_26')/ref/'CONCENTRATION.json',conc)
        ranked=sorted(a['stock'],key=a['stock'].get,reverse=True)
        chosen=list(dict.fromkeys(ranked[:10]+ranked[-3:]+['601869.SH','301511.SZ','300308.SZ','300502.SZ']))
        paths[ref]=[B.path(a,sid,actions,exits) for sid in chosen]
        save(Path('analysis/2025_26')/ref/'TOP10_WORST3_FIXED_STOCK_PATHS.json',paths[ref])
        fund=rows(root/'pair/funding.jsonl.gz')
        metrics[ref]['raw_opening_rejection_records']=dict(collections.Counter(x['result'] for x in fund
            if '09:30:00' in x['at'] and x['result']!='reserved'))
    delayed=read(ROOT/'pair/B-D1_AUDIT.json');ev=delayed['events']
    delay=dict(event_counts=dict(collections.Counter(x['kind'] for x in ev)),
        buy_distinct_first_wait_orders=len({x['order'] for x in ev if x['kind']=='D1_actual_wait' and x['side']=='buy'}),
        sell_distinct_first_wait_obligations=len({x['order'] for x in ev if x['kind']=='D1_actual_wait' and x['side']=='sell'}),
        raw_cancellation_reasons=dict(collections.Counter(x.get('reason') for x in ev if x['kind']=='D1_retry_cancel')),
        initial_admission_vs_fill_separate=True,
        waiting_buy_orders_preserve_original_receipt_and_do_not_require_new_CP1=True,
        observations_are_market_sessions_not_natural_days=True)
    save(Path('analysis/2025_26')/'D1_LIFECYCLE_SUMMARY.json',delay)
    delta=[]
    for sid in sets['normal']['all_stocks']|sets['D1']['all_stocks']:
        ls={ref:[l for l in a['layers'] if l['sid']==sid] for ref,a in data.items()}
        delta.append(dict(sid=sid,name=B.META[sid]['name'],industry=B.META[sid]['industry'],
            normal=B.M.contribution(ls['normal']),D1=B.M.contribution(ls['D1']),
            delta=sum((x['net'] for x in ls['D1']),Z)-sum((x['net'] for x in ls['normal']),Z),
            category='new_funded_stock' if not ls['normal'] else 'lost_funded_stock' if not ls['D1'] else 'common_funded_stock'))
    navdelta=n(data['D1']['book']['ending_NAV'])-n(data['normal']['book']['ending_NAV'])
    assert abs(sum((x['delta'] for x in delta),Z)-navdelta)<D('.00000001')
    save(Path('analysis/2025_26')/'STOCK_CONTRIBUTION_DELTA_BRIDGE.json',dict(delta_NAV=navdelta,
        category_totals={key:sum((x['delta'] for x in delta if x['category']==key),Z)
            for key in ('new_funded_stock','lost_funded_stock','common_funded_stock')},
        stocks=sorted(delta,key=lambda x:-x['delta']),accounting_attribution_not_unilateral_counterfactual_causality=True))
    cases=[]
    for sector,lo,hi in [('URFI881267','2025-07-01','2025-09-30'),('URFI881276','2025-10-01','2025-12-31'),
                         ('URFI881107','2026-01-01','2026-03-31'),('URFI881121','2026-01-01','2026-06-30')]:
        for ref,a in data.items():
            ds=[r for r in a['daily'] if lo<=day(r['at'])<=hi]
            weights=[dict(day=day(r['at']),weight_pct=sum((v for s,v in a['values'][day(r['at'])].items()
                if B.META[s]['sector_id']==sector),Z)/n(r['nav'])*100) for r in ds]
            buys=[t for t in a['book']['trades'] if t['side']=='buy' and lo<=day(t['at'])<=hi
                and B.META[t['security_id']]['sector_id']==sector]
            cases.append(dict(reference=ref,sector=sector,window=[lo,hi],
                first_actual_buy=buys[0]['at'] if buys else None,
                active_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in buys),Z),
                peak_weight=max(weights,key=lambda x:x['weight_pct']),daily_weights=weights))
    save(Path('analysis/2025_26')/'FIXED_SECTOR_PATHS.json',cases)
    summary=dict(normal=metrics['normal'],D1=metrics['D1'],delta_NAV=navdelta,
        first_participation_changes=dict(collections.Counter(x['change'] for x in first)),
        funded_changes={k:dict(normal=v['normal'],D1=v['D1'],gained=len(v['gained']),lost=len(v['lost'])) for k,v in changes.items()},
        D1_lifecycle=delay,new_economic_paths=1,baseline_replayed=False,
        scope='research daily execution proxy; consumed window, no live/OOS certification',
        analysis_seconds=time.monotonic()-started)
    save(Path('analysis/2025_26')/'COMPARISON.json',summary)
    print('PVR_D1_SAVED_ANALYSIS',metrics['normal']['return_pct'],metrics['D1']['return_pct'],
        metrics['normal']['global_DD'],metrics['D1']['global_DD'],flush=True)

if __name__=='__main__':
    try:run()
    except BaseException as ex:
        save(Path('analysis')/'ERROR.json',dict(type=type(ex).__name__,reason=str(ex),economic_replays=0));raise
