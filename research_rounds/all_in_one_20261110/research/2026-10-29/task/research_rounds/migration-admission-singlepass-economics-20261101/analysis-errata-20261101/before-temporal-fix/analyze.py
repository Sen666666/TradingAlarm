"""Saved SD/SC ledgers only. No runner or future opportunity labels loaded."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,collections,hashlib,statistics,argparse,importlib.util,time
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;Z=D(0)
p=W/'c1-drawdown-capacity-20261101/analyze_saved.py'
spec=importlib.util.spec_from_file_location('SD_saved_account_math',p);A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A);A.O=O
META=A.META
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(path,x):A.save(path,x)
def day(x):return str(x)[:10]
def n(x):return D(str(x))

def contribution(es):
    return dict(layers=len(es),stocks=len({x['sid'] for x in es}),buy_cash=sum((x['cost'] for x in es),Z),
        closed_positive=sum((x['net'] for x in es if not x['qty'] and x['net']>0),Z),
        closed_negative=sum((x['net'] for x in es if not x['qty'] and x['net']<0),Z),
        open_positive=sum((x['net'] for x in es if x['qty'] and x['net']>0),Z),
        open_negative=sum((x['net'] for x in es if x['qty'] and x['net']<0),Z),
        net=sum((x['net'] for x in es),Z),
        closed_tail=sum((x['net'] for x in es if not x['qty'] and x['cost'] and x['net']/x['cost']>=D('.3')),Z),
        open_tail=sum((x['net'] for x in es if x['qty'] and x['cost'] and x['net']/x['cost']>=D('.3')),Z))

STATE={};ATTEMPT={}
def industry_state():
    if STATE:return
    for r in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json'):
        q=pd.read_parquet(r['refs']['state']);STATE[r['series']]={x['day']:x for x in q.to_dict('records')}
        for x in q.to_dict('records'):
            if x['action']=='probe':ATTEMPT[x['attempt_id']]=f"{x['E0_episode']}:{x['receipt_id']}"

def pool_and_waits(win,ref,a):
    industry_state();ds=a['daily'];dates=[day(r['at']) for r in ds];ix={d:i for i,d in enumerate(dates)}
    snaps={day(r['at']):{x['id']:x for x in r['layers']} for r in ds};first={};contexts=[];old_probe=[]
    for r in ds:
        d=day(r['at']);groups=collections.defaultdict(list)
        for x in r['layers']:
            if x['pool']=='probe':groups[x['sector']].append(x)
        old_cap=Z;eligible_cap=Z
        for sector,ls in groups.items():
            state=STATE[sector].get(d)
            if state is None:
                contexts.append(dict(day=d,sector=sector,status='industry_state_unknown'));continue
            active=state['E0_valid'] and state['attempt_id'] is not None
            current=ATTEMPT.get(state['attempt_id']) if active else None
            for x in ls:
                if x['attempt']!=current:old_cap+=D(x['qty'])*A.price(x['sid'],d)
            elig=[x for x in ls if active and state['stage_name'] in ('confirmed','expanded') and x['attempt']==current]
            if not elig:continue
            required=sum((D(x['qty'])*A.price(x['sid'],d) for x in elig),Z);eligible_cap+=required
            remaining=n(r['nav'])*D('.60')-n(r['pool_confirmed'][0])
            contexts.append(dict(day=d,sector=sector,attempt=current,layers=[x['id'] for x in elig],
                probe_value=required,remaining_confirmed_capacity=remaining,
                whole_transfer_cannot_fit=required>remaining+D('.00001'),
                snapshot_only_not_an_assertion_that_migrate_was_called=True))
            for x in elig:first.setdefault(x['id'],d)
        old_probe.append(dict(day=d,old_or_inactive_attempt_probe_capital=old_cap,current_eligible_unmigrated_probe_capital=eligible_cap))
    waits=[]
    endmeta=a['book']['metadata']
    for lid,start in first.items():
        layer=next(x for x in a['layers'] if x['layer']==lid)
        moved=next((d for d in dates[ix[start]+1:] if lid in snaps[d] and snaps[d][lid]['pool']=='confirmed'),None)
        ended=None
        for d in dates[ix[start]+1:]:
            state=STATE[layer['sector']].get(d)
            if state is not None and (not state['E0_valid'] or ATTEMPT.get(state['attempt_id'])!=layer['attempt']):
                ended=d;break
        if moved:status='observed_migrated'
        elif endmeta[str(lid)]['pool']=='confirmed':status='migrated_between_snapshots_unknown_day'
        elif ended:status='attempt_ended_before_observed_migration'
        elif layer['closed']:status='exited_without_observed_migration'
        else:status='still_probe_right_censored'
        waits.append(dict(layer=lid,sid=layer['sid'],role=layer['role'],attempt=layer['attempt'],
            first_eligible_probe_close=start,first_confirmed_close=moved,
            observations_to_migration=ix[moved]-ix[start] if moved else None,
            original_attempt_end_close=ended,
            observations_to_attempt_end=ix[ended]-ix[start] if ended else None,
            followup_observations=(ix[day(layer['closed'])]-ix[start]) if layer['closed'] else len(dates)-1-ix[start],
            status=status,closed=layer['closed'],net=layer['net']))
    lags=[x['observations_to_migration'] for x in waits if x['observations_to_migration'] is not None]
    summary=dict(unit='one actual probe layer first observed still probe while its own attempt confirmed/expanded',
        layers=len(waits),stocks=len({x['sid'] for x in waits}),statuses=dict(collections.Counter(x['status'] for x in waits)),
        observed_migration_lag_median=statistics.median(lags) if lags else None,
        observed_migration_lag_max=max(lags) if lags else None,
        old_or_inactive_probe_mean_capital=sum((x['old_or_inactive_attempt_probe_capital'] for x in old_probe),Z)/len(old_probe),
        eligible_unmigrated_probe_mean_capital=sum((x['current_eligible_unmigrated_probe_capital'] for x in old_probe),Z)/len(old_probe),
        whole_old_transfer_cannot_fit_sector_closes=sum(x.get('whole_transfer_cannot_fit',False) for x in contexts))
    save(Path('analysis')/win/ref/'MIGRATION_WAITS.json',dict(summary=summary,lots=waits,contexts=contexts,daily_old_probe=old_probe))
    summary_pool={}
    for pool in ('probe','confirmed'):
        vals=[n(r['pool_'+pool][0])/n(r['nav'])*100 for r in ds]
        risks=[n(r['pool_'+pool][1])/n(r['nav'])*100 for r in ds]
        summary_pool[pool]=dict(mean_commitment_pct=sum(vals,Z)/len(vals),peak_commitment_pct=max(vals),
                                mean_nominal_risk_pct=sum(risks,Z)/len(risks),peak_nominal_risk_pct=max(risks))
    return dict(waits=summary,pools=summary_pool)

def participation(a):
    return dict(all_stocks={x['sid'] for x in a['layers']},
        all_attempts={(x['sector'],x['attempt']) for x in a['layers']},
        stock_attempts={(x['sid'],x['sector'],x['attempt']) for x in a['layers']},
        confirmed_stocks={x['sid'] for x in a['layers'] if x['role']=='mobile' and x['pool_at_fill']=='confirmed'},
        confirmed_receipts={(x['sid'],x['signal_day'],x['receipt']) for x in a['layers'] if x['role']=='mobile' and x['pool_at_fill']=='confirmed'},
        any_mobile_receipts={(x['sid'],x['signal_day'],x['receipt']) for x in a['layers'] if x['role']=='mobile'})

def run(win):
    root=O/'runs'/win;assert read(root/'DONE.json')['completed']
    old=W/('2022-normal-reference-20261031' if win=='2022' else 'q2-normal-continuation-20261031')/'runs/B_diag'
    data={'SC':A.account(win,'SC',old),'SD':A.account(win,'SD',root)}
    sets={k:participation(a) for k,a in data.items()};changes={}
    for k in sets['SC']:
        changes[k]=dict(SC=len(sets['SC'][k]),SD=len(sets['SD'][k]),gained=sorted(sets['SD'][k]-sets['SC'][k]),lost=sorted(sets['SC'][k]-sets['SD'][k]))
    save(Path('analysis')/win/'FUNDED_CHANGES.json',changes)
    coverage=rows(W/'opportunity-quality-ranking-20261031'/win/'CANDIDATES.jsonl.gz')
    candidates={(x['sid'],x['day'],x['receipt']) for x in coverage};assert len(candidates)==len(coverage)
    universe={}
    for ref,a in data.items():
        selected=sets[ref]['confirmed_receipts'];assert selected<=candidates,(win,ref,'actual confirmed receipt outside frozen original market opportunity')
        last_day=day(a['daily'][-1]['at']);right_boundary={x for x in candidates if x[1]==last_day}
        universe[ref]=dict(confirmed_mobile_filled_receipts=len(selected),all_qualified_market_receipts=len(candidates),
            filled_fraction_pct=D(len(selected))*100/len(candidates),stocks=len({x[0] for x in selected}),
            last_close_authorizations_next_open_outside_window=len(right_boundary),
            filled_fraction_excluding_common_right_boundary_pct=D(len(selected))*100/(len(candidates)-len(right_boundary)),
            ACT_paused_qualified_receipts=sum(not a['byday'][x['day']]['on'] for x in coverage),
            market_candidates_do_not_remove_account_ACT_pauses=True,
            no_future_return_labels_used=True)
    save(Path('analysis')/win/'OPPORTUNITY_COVERAGE.json',universe)
    metrics={}
    for ref,a in data.items():
        pools=pool_and_waits(win,ref,a);group={}
        for role in ('core','mobile'):
            for pool in ('probe','confirmed'):group[role+'_'+pool]=contribution([x for x in a['layers'] if x['role']==role and x['pool_at_fill']==pool])
        admissions=[x for x in rows((old if ref=='SC' else root)/'pair/funding.jsonl.gz') if x['result']=='reserved']
        actual_ids={j['budget_order'] for j in a['book']['journal'] if j['kind']=='real_buy_fill'}
        reserved_orders=[j for j in a['book']['journal'] if j['kind']=='real_reserve']
        zero_fill=[j for j in reserved_orders if j['budget_order'] not in actual_ids]
        exit_requests=[x for x in a['book']['audit'] if x['kind']=='pilot_layer_exit']
        fees=sum((n(t['fees_cny']) for t in a['book']['trades']),Z)
        assert fees==n(a['daily'][-1]['fees_cny'])
        metrics[ref]=dict(**a['metrics'],contributions=contribution(a['layers']),roles_at_fill=group,
            admissions=len(admissions),actual_filled_orders=len(actual_ids),zero_fill_reservations=len(zero_fill),
            actual_funded_stocks=len(sets[ref]['all_stocks']),funded_attempts=len(sets[ref]['all_attempts']),
            exit_layer_requests=len(exit_requests),pending_stock_exits=len(a['book']['exits']),
            opportunity_coverage=universe[ref],**pools)
    stock_changes=[]
    allstocks=sets['SC']['all_stocks']|sets['SD']['all_stocks']
    for sid in allstocks:
        left=data['SC']['stock'].get(sid,Z);right=data['SD']['stock'].get(sid,Z)
        lc=sum((x['cost'] for x in data['SC']['layers'] if x['sid']==sid),Z);rc=sum((x['cost'] for x in data['SD']['layers'] if x['sid']==sid),Z)
        stock_changes.append(dict(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],SC_net=left,SD_net=right,
            delta=right-left,SC_buy_cash=lc,SD_buy_cash=rc,
            category='new_funded_stock' if sid not in sets['SC']['all_stocks'] else 'lost_funded_stock' if sid not in sets['SD']['all_stocks'] else 'common_funded_stock'))
    delta=sum((x['delta'] for x in stock_changes),Z)
    assert abs(delta-(n(data['SD']['book']['ending_NAV'])-n(data['SC']['book']['ending_NAV'])))<D('.00000001')
    bridge={k:sum((x['delta'] for x in stock_changes if x['category']==k),Z) for k in ('new_funded_stock','lost_funded_stock','common_funded_stock')}
    save(Path('analysis')/win/'STOCK_DELTA_BRIDGE.json',dict(bridge=bridge,delta_NAV=delta,residual=Z,
         positive_delta=sorted(stock_changes,key=lambda x:-x['delta'])[:10],negative_delta=sorted(stock_changes,key=lambda x:x['delta'])[:10],all_stocks=sorted(stock_changes,key=lambda x:-x['SD_net'])))
    top=sorted(data['SC']['stock'],key=data['SC']['stock'].get,reverse=True)[:10]
    save(Path('analysis')/win/'ORIGINAL_TOP10_WINNERS.json',[x for s in top for x in stock_changes if x['sid']==s])
    for ref,a in data.items():
        ordered=sorted(a['stock'],key=a['stock'].get,reverse=True)
        ids=list(dict.fromkeys(ordered[:10]+ordered[-3:]))
        save(Path('analysis')/win/ref/'TOP_AND_FAILED_PATHS.json',[dict(sid=sid,name=META[sid]['name'],net=a['stock'][sid],
            layers=[x for x in a['layers'] if x['sid']==sid],trades=[t for t in a['book']['trades'] if t['security_id']==sid]) for sid in ids])
    route=rows(root/'pair/SD-route.jsonl.gz');used=[x for x in route if x['new_permission_used']]
    usedids={(x['sid'],x['signal_day'],x['receipt']) for x in used}
    usedlayers=[x for x in data['SD']['layers'] if (x['sid'],x['signal_day'],x['receipt']) in usedids]
    new_permission=dict(admissions=len(used),filled_canonical_receipts=len({(x['sid'],x['signal_day'],x['receipt']) for x in usedlayers}),
        native_fill_contribution=contribution(usedlayers),by_original_migration_failure=dict(collections.Counter(x['before_migration']['reason'] for x in used)),
        labels_are_actual_local_permission_use_not_total_policy_causal_PnL=True)
    save(Path('analysis')/win/'NEW_PERMISSION.json',dict(summary=new_permission,reservations=used,layers=usedlayers))
    resource=[x for x in route if x['result']!='reserved' and any(k in x['result'] for k in ('probe_risk','pool_capital'))]
    sc_resource=[x for x in rows(old/'pair/funding.jsonl.gz') if x['result']!='reserved' and any(k in x['result'] for k in ('probe_risk','pool_capital'))]
    save(Path('analysis')/win/'RESOURCE_BLOCKS.json',dict(unit='unique opening-stock-role route attempt',count=len(resource),
        stocks=len({x['sid'] for x in resource}),reasons=dict(collections.Counter(x['result'] for x in resource)),
        SD_by_role=dict(collections.Counter(x['role'] for x in resource)),
        SC_count=len(sc_resource),SC_stocks=len({x['sid'] for x in sc_resource}),SC_by_role=dict(collections.Counter(x['role'] for x in sc_resource)),
        SD_fresh_mobile_resource_blocked_receipts=len({(x['sid'],x['signal_day'],x['receipt']) for x in resource if x['role']=='mobile'}),
        migration_failed_in_same_candidate=sum(x['before_migration'] is not None and x['before_migration']['reason'] in ('same_attempt_probe_pending','whole_old_transfer_cannot_fit') for x in resource),
        exclusive_old_probe_causal_blocks='unknown: raw route reasons may coexist; no relaxed-budget replay performed',examples=resource[:12]))
    cases=[]
    if win=='2025_26':
        for sector,lo,hi in [('URFI881267','2025-07-01','2025-09-30'),('URFI881276','2025-10-01','2025-12-31'),('URFI881107','2026-01-01','2026-03-31')]:
            for ref,a in data.items():
                qs=[r for r in a['daily'] if lo<=day(r['at'])<=hi]
                weights=[(day(r['at']),sum((v for sid,v in a['values'][day(r['at'])].items() if META[sid]['sector_id']==sector),Z)/n(r['nav'])*100) for r in qs]
                buys=[t for t in a['book']['trades'] if t['side']=='buy' and lo<=day(t['at'])<=hi and META[t['security_id']]['sector_id']==sector]
                cases.append(dict(reference=ref,sector=sector,industry=next(x['industry'] for x in META.values() if x['sector_id']==sector),window=[lo,hi],
                    first_actual_buy=buys[0] if buys else None,buy_cash=sum((n(x['gross_cny'])+n(x['fees_cny']) for x in buys),Z),
                    actual_peak_weight=max(weights,key=lambda x:x[1]),daily_weights=weights,
                    signal_period_layers=contribution([x for x in a['layers'] if x['sector']==sector and lo<=x['signal_day']<=hi])))
        save(Path('analysis')/win/'THREE_FIXED_CASES.json',cases)
    # No future return label selects which participants are compared.
    result=dict(window=win,SC=metrics['SC'],SD=metrics['SD'],new_permission=new_permission,funded_changes={k:dict(SC=v['SC'],SD=v['SD'],gained=len(v['gained']),lost=len(v['lost'])) for k,v in changes.items()},stock_delta_bridge=bridge)
    save(Path('analysis')/win/'COMPARISON.json',result)
    save(Path('analysis')/win/'COMPLETION.json',dict(passed=True,daily_rows_each=242,daily_money_quantity_bridges=True,
        fees_cash_stock_layer_contribution_bridges=True,baseline_replayed=False,new_account_runs=0,
        SC_book_sha256=hashlib.sha256((old/'pair/B.json.gz').read_bytes()).hexdigest(),SD_book_sha256=hashlib.sha256((root/'pair/B.json.gz').read_bytes()).hexdigest()))
    print('ANALYSIS_RESULT',win,'SCreturn',metrics['SC']['return_pct'],'SDreturn',metrics['SD']['return_pct'],
          'SCdd',metrics['SC']['global_DD']['percent'],'SDdd',metrics['SD']['global_DD']['percent'],
          'newpermission',new_permission['admissions'],new_permission['filled_canonical_receipts'],flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--window',choices=['2022','2025_26'],required=True);args=parser.parse_args()
    try:run(args.window)
    except BaseException as e:save('failure/ANALYSIS_ERROR.json',dict(window=args.window,type=type(e).__name__,reason=str(e)));raise
