"""One new SC continuation verification; read-only complete four-cell report."""
from pathlib import Path
from decimal import Decimal as D
import collections, gzip, json, pickle, statistics, time
import composition as A
J,L,IO,Q,O,W=A.J,A.L,A.IO,A.Q,A.O,A.W
R=A.load('four_cells_reused_PVR_D1_analysis',O/'analyze_PVR_D1.py')
B=R.B;OUT=O/'four-cells';B.O=OUT;B.M.O=OUT;B.A.O=OUT
ROOT=O/'SC-D1-Q2-continuation';Z=D(0)
SPECS={'SC_normal':W/'q2-normal-continuation-20261031/runs/B_diag',
       'SC_D1':ROOT,'PVR_normal':A.P/'runs/2025_26','PVR_D1':O/'run-PVR-D1'}

def n(x):return D(str(x))
def day(x):return str(x)[:10]
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(name,x):IO.write_json(OUT/name,J.W.canon(x))

def verify_SC():
    assert read(ROOT/'DONE.json')['completed']
    meta=read(ROOT/'FROZEN_RUN_METADATA.json');freeze=meta['sources']
    assert freeze==read(ROOT/'PREEXECUTION_SOURCE_BINDING.json')['sources']
    assert all(A.sha(p)==h for p,h in freeze.items())
    with gzip.open(ROOT/'pair/B.json.gz','rt') as f:b=json.load(f)
    ds=rows(ROOT/'pair/daily.jsonl.gz');br=rows(ROOT/'pair/balances.jsonl.gz')
    assert len(ds)==len(br)==242
    parentpath=O/'SC-April1-first-session/full-input/checkpoint.pkl'
    assert A.sha(parentpath)==meta['parent_sha256']
    parent=pickle.loads(parentpath.read_bytes());old=parent['accounts']['B']
    end=pickle.loads((ROOT/'checkpoint.pkl').read_bytes())
    for key in ('daily','opportunities','funding','stage_events','balance_audit','rank_log'):
        prior=parent['runner'][key];assert Q.equal(prior,end['runner'][key][:len(prior)])
    for key in ('trades','journal','audit_log','decisions','d1_audit'):
        prior=old[key];assert Q.equal(prior,end['accounts']['B'][key][:len(prior)])
    assert len(parent['runner']['daily'])==183
    assert len(ds[183:])==59 and day(ds[183]['at'])=='2026-04-02'
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
    qbridges=collections.defaultdict(list)
    for x in br:
        for key in ('independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference',
                    'capital_occupancy_difference','maximum_stock_quantity_difference'):
            assert abs(n(x[key]))<D('.000001')
        assert all(abs(n(v))<D('.000001') for v in x['pool_occupancy_difference'].values())
        qbridges[str(J.pd.Timestamp(day(x['at'])).to_period('Q'))].append(x)
    snapshots={day(x['at']):x for x in ds};checks=[]
    oldroot=A.D1/'runs/B_diag'
    paths=[oldroot/('checkpoint-'+d+'.pkl') for d in ('2025-09-30','2025-12-31','2026-03-31')]
    paths += [ROOT/'checkpoint-2026-06-30.pkl']
    for path in paths:
        prov=read(path.with_suffix('.provenance.json'));assert prov['checkpoint_sha256']==A.sha(path)
        p=pickle.loads(path.read_bytes());a=p['accounts']['B'];d=str(p['last_completed_event'].date())
        oldquarter=path.parent==oldroot
        expectedsha=A.D1_SHA if oldquarter else A.sha(O/'composition.py')
        assert prov['engine_identity']['trading_class']['module_sha256']==expectedsha
        methods={'planning':A.E.Pair.planning if oldquarter else A.Composition.planning,
                 'opening':A.E.Pair.opening,'route':A.E.BASE.Runner.route}
        for name,fn in methods.items():assert prov['engine_identity']['functions'][name]['code_sha256']==IO._code_fingerprint(fn.__code__)
        assert a['d1_enabled'] and a['delay_events']==1 and not a['d1_account_cap'] and a['cost_multiplier']==1
        assert type(a['budget']) is A.E.BASE.NoAccountBudget
        assert a['current_nav']==n(snapshots[d]['nav'])
        assert {s:x.shares for s,x in a['positions'].items()}==snapshots[d]['positions']
        assert all(A.sha(name)==h for name,h in p['source_freeze'].items())
        checks.append(dict(day=d,path=str(path),sha256=A.sha(path),original_generation_identity=True,
            old_original_D1_quarter_reused_without_backfill=oldquarter,NAV=str(a['current_nav'])))
    a=end['accounts']['B']
    assert end['runner']['rank_mode']=='H1' and end['runner']['d1_enabled']
    assert all(i['score'] is not None for i in a['pending'])
    reused_native_sources={str(A.D1/'d1_runner.py'):A.D1_SHA,str(O/'composition.py'):A.sha(O/'composition.py')}
    result=dict(passed=True,full_window_daily_rows=242,old_prefix_rows_preserved=183,new_rows=59,
        cash_equity_pool_and_independent_shares_fees_verified=242,fills=len(b['trades']),
        new_fills=len(b['trades'])-len(old['trades']),splits=len(splits),
        new_splits=sum(day(x['at'])>'2026-04-01' for x in splits),quarter_checkpoints=checks,
        quarterly_bridge_counts={q:len(xs) for q,xs in qbridges.items()},
        inherited_270_intents_11_exits_preserved_before_new_events=True,
        no_D1_configuration_reset=True,no_old182_or_April1_replay=True,
        unchanged_native_lifecycle_tests_reused_not_rerun=20,reused_native_sources=reused_native_sources,
        sources_verified=True,new_financial_paths=1)
    save(Path('SC_CONTINUATION_VERIFICATION.json'),result)
    print('SC_CONTINUATION_FINANCIAL_VERIFIED',len(b['trades']),result['new_fills'],flush=True)
    return result

def main():
    start=time.monotonic();verification=verify_SC()
    data={ref:B.A.account('2025_26',ref,path) for ref,path in SPECS.items()}
    metrics={};sets={};actions={};paths={}
    for ref,a in data.items():
        b=a['book'];sets[ref]=B.M.participation(a)
        actions[ref]=B.entry_actions(a);exits=B.exit_chain(a);pool=B.M.pool_and_waits('2025_26',ref,a)
        reservations=[x for x in b['journal'] if x['kind']=='real_reserve']
        filled={x['budget_order'] for x in b['journal'] if x['kind']=='real_buy_fill'}
        pending=[dict(day=day(d['at']),ratio=(n(d['pool_probe'][0])+n(d['pool_confirmed'][0])-n(d['inventory']))/n(d['nav'])*100)
                 for d in a['daily']]
        conc=B.concentration(a)
        metrics[ref]=dict(**a['metrics'],**pool,contributions=B.M.contribution(a['layers']),
            actual_realized_unrealized_dividends=R.real_bridge(b),
            admissions=len(reservations),actual_filled_orders=len(filled),
            zero_fill_reservations=sum(x['budget_order'] not in filled for x in reservations),
            terminal_active_buys=len(b['orders']),terminal_sell_obligations=len(b['exits']),
            funded_stocks=len(sets[ref]['all_stocks']),funded_attempts=len(sets[ref]['all_attempts']),
            confirmed_filled_canonical_receipts=len(sets[ref]['confirmed_receipts']),
            mean_pending_buy_principal_pct=sum((x['ratio'] for x in pending),Z)/len(pending),
            peak_pending_buy_principal=max(pending,key=lambda x:x['ratio']),
            entry_actions={kind:B.M.contribution([l for l in a['layers'] if l['layer'] in
                {x['layer'] for x in actions[ref] if x['action']==kind}]) for kind in
                ('first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat')},
            role_pool_at_fill={role+'_'+pool:B.M.contribution([l for l in a['layers']
                if l['role']==role and l['pool_at_fill']==pool]) for role in ('core','mobile') for pool in ('probe','confirmed')},
            layer_exit_requests=len(exits),layers_with_actual_exit_fill=sum(x['first_actual_sell'] is not None for x in exits),
            exit_request_to_first_actual_sell_observations=dict(collections.Counter(str(x['market_observations_to_first_sell']) for x in exits)),
            concentration={k:v for k,v in conc.items() if k!='daily'})
        ranked=sorted(a['stock'],key=a['stock'].get,reverse=True)
        chosen=list(dict.fromkeys(ranked[:10]+ranked[-3:]+['300308.SZ','300502.SZ','601869.SH','301511.SZ']))
        paths[ref]=[B.path(a,s,actions[ref],exits) for s in chosen]
        save(Path('analysis/2025_26')/ref/'TOP10_WORST3_FIXED_STOCK_PATHS.json',paths[ref])
        save(Path('analysis/2025_26')/ref/'ENTRY_ACTIONS.json',actions[ref])
        save(Path('analysis/2025_26')/ref/'EXIT_REQUESTS_AND_ACTUAL_FILLS.json',exits)
        save(Path('analysis/2025_26')/ref/'PENDING_PRINCIPAL_DAILY.json',pending)
    comparisons={}
    for left,right in [('SC_normal','SC_D1'),('PVR_normal','PVR_D1'),('SC_normal','PVR_normal'),('SC_D1','PVR_D1')]:
        change={key:dict(left=len(sets[left][key]),right=len(sets[right][key]),
            gained=sorted(sets[right][key]-sets[left][key]),lost=sorted(sets[left][key]-sets[right][key])) for key in sets[left]}
        first={ref:{sid:min(x['opened'] for x in data[ref]['layers'] if x['sid']==sid) for sid in sets[ref]['all_stocks']} for ref in (left,right)}
        f=[]
        for sid in sorted(set(first[left])|set(first[right])):
            la,ra=first[left].get(sid),first[right].get(sid)
            f.append(dict(sid=sid,left=la,right=ra,change='new_funded' if la is None else 'lost_funded' if ra is None else
                'earlier' if ra<la else 'later' if ra>la else 'same'))
        delta=[]
        for sid in sets[left]['all_stocks']|sets[right]['all_stocks']:
            lv=data[left]['stock'].get(sid,Z);rv=data[right]['stock'].get(sid,Z)
            delta.append(dict(sid=sid,name=B.META[sid]['name'],industry=B.META[sid]['industry'],left=lv,right=rv,delta=rv-lv))
        navdelta=n(data[right]['book']['ending_NAV'])-n(data[left]['book']['ending_NAV'])
        assert abs(sum((x['delta'] for x in delta),Z)-navdelta)<D('.00000001')
        key=left+'__'+right
        comparisons[key]=dict(left=left,right=right,delta_NAV=navdelta,
            actual_funded_changes={k:dict(left=v['left'],right=v['right'],gained=len(v['gained']),lost=len(v['lost'])) for k,v in change.items()},
            first_actual_entry_changes=dict(collections.Counter(x['change'] for x in f)))
        save(Path('COMPARISONS')/(key+'.json'),dict(**comparisons[key],funded_sets=change,
            first_actual_entry=f,stock_delta=sorted(delta,key=lambda x:-x['delta']),
            interpretation='observed complete policy paths; stock wealth attribution is not a one-order counterfactual'))
    fixed=[('URFI881267','2025-07-01','2025-09-30'),('URFI881276','2025-10-01','2025-12-31'),
           ('URFI881107','2026-01-01','2026-03-31'),('URFI881121','2026-01-01','2026-06-30')]
    for name in ('电子化学品','元件','通信设备'):
        sector=next(v['sector_id'] for v in B.META.values() if v['industry']==name)
        fixed.append((sector,'2025-07-01','2026-06-30'))
    sectors=[]
    for sector,lo,hi in fixed:
        for ref,a in data.items():
            ds=[r for r in a['daily'] if lo<=day(r['at'])<=hi]
            weights=[dict(day=day(r['at']),weight_pct=sum((v for sid,v in a['values'][day(r['at'])].items()
                if B.META[sid]['sector_id']==sector),Z)/n(r['nav'])*100) for r in ds]
            buys=[t for t in a['book']['trades'] if t['side']=='buy' and lo<=day(t['at'])<=hi
                and B.META[t['security_id']]['sector_id']==sector]
            sectors.append(dict(reference=ref,sector=sector,industry=next(v['industry'] for v in B.META.values() if v['sector_id']==sector),
                window=[lo,hi],first_actual_buy=buys[0]['at'] if buys else None,
                active_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in buys),Z),
                peak_weight=max(weights,key=lambda x:x['weight_pct']),daily_weights=weights,
                full_window_sector_contribution=B.M.contribution([l for l in a['layers'] if l['sector']==sector]),
                window_new_signal_cohort_contribution_to_June30=B.M.contribution([l for l in a['layers'] if l['sector']==sector and lo<=l['signal_day']<=hi])))
    save(Path('FIXED_MAINLINE_SECTOR_PATHS.json'),sectors)
    rank_normal=metrics['PVR_normal']['return_pct']-metrics['SC_normal']['return_pct']
    rank_d1=metrics['PVR_D1']['return_pct']-metrics['SC_D1']['return_pct']
    summary=dict(scope='complete same Jul2025-Jun2026 four-cell research comparison; originals not rerun',
        cells=metrics,comparisons=comparisons,
        ranking_return_difference_pp_normal=rank_normal,ranking_return_difference_pp_D1=rank_d1,
        observed_factor_interaction_pp=rank_d1-rank_normal,
        interaction_not_a_new_variant_or_independent_samples=True,
        SC_continuation_verification=verification,
        new_financial_paths_this_authorization=1,no_other_paths=True,
        limitations=['current snapshot non-PIT','same consumed research window','daily H/L/volume execution proxy',
            'open-layer category differs from unrealized PnL','unpaid dividends remain AR',
            'no instantaneous constraint-relaxation or counterfactual-return experiment'],
        analysis_seconds=time.monotonic()-start)
    save(Path('FOUR_CELL_COMPARISON.json'),summary)
    print('FOUR_CELLS_ANALYZED',[(ref,str(m['return_pct']),str(m['global_DD']['percent'])) for ref,m in metrics.items()],flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as ex:
        save(Path('failure/ANALYSIS_ERROR.json'),dict(type=type(ex).__name__,reason=str(ex),financial_replays=0));raise
