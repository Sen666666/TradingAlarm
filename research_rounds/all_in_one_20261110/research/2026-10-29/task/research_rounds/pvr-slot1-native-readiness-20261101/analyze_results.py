"""Saved SC/PVR_SLOT1 books only. Reuse audited money and temporal-wait math."""
from pathlib import Path
from decimal import Decimal as D
import importlib.util, json, gzip, collections, argparse, statistics, hashlib
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;Z=D(0)
p=W/'migration-admission-singlepass-economics-20261101/analyze.py'
spec=importlib.util.spec_from_file_location('slot1_saved_audited_math',p)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
M.O=O;M.A.O=O;A=M.A;META=M.META
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):A.save(p,x)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def concentration(a):
    series=[]
    for d,r in a['byday'].items():
        vv=a['values'][d];sector=collections.defaultdict(lambda:Z)
        for sid,v in vv.items():sector[META[sid]['sector_id']]+=v
        total=sum(vv.values(),Z);nav=n(r['nav'])
        series.append(dict(day=d,held_stocks=len(vv),held_industries=len(sector),
          largest_stock_pct=max(vv.values(),default=Z)/nav*100,
          top3_industry_pct=sum(sorted(sector.values(),reverse=True)[:3],Z)/nav*100,
          largest_industry_pct=max(sector.values(),default=Z)/nav*100,
          invested_stock_HHI=sum(((v/total)**2 for v in vv.values()),Z) if total else None,
          invested_industry_HHI=sum(((v/total)**2 for v in sector.values()),Z) if total else None))
    return dict(daily=series,mean_held_stocks=statistics.mean(x['held_stocks'] for x in series),
      mean_held_industries=statistics.mean(x['held_industries'] for x in series),
      peak_stock_pct=max(x['largest_stock_pct'] for x in series),
      mean_top3_industry_pct=sum((x['top3_industry_pct'] for x in series),Z)/len(series))

def entry_actions(a):
    q=collections.defaultdict(int);ever=set();actions=[];events=[]
    for i,t in enumerate(a['book']['trades']):events.append((str(t['at']),1,i,'trade',t))
    for i,x in enumerate(a['book']['audit']):
        if x['kind']=='split':events.append((str(x['at']),0,i,'split',x))
    for at,_,_,kind,t in sorted(events,key=lambda x:x[:3]):
        sid=t.get('security_id',t.get('sid'))
        if kind=='split':q[sid]=int(D(q[sid])*n(t['ratio']));continue
        if t['side']=='sell':q[sid]-=t['shares'];assert q[sid]>=0;continue
        k='add_to_existing_stock' if q[sid] else 'fresh_reentry_after_actual_flat' if sid in ever else 'first_actual_participation'
        l=next(x for x in a['layers'] if x['layer']==t['layer'])
        actions.append(dict(layer=l['layer'],sid=sid,at=at,role=l['role'],pool=l['pool_at_fill'],
          action=k,quantity_before=q[sid],quantity=t['shares'],gross=n(t['gross_cny']),fees=n(t['fees_cny']),receipt=l['receipt']))
        q[sid]+=t['shares'];ever.add(sid)
    return actions

def exit_chain(a):
    ds=list(a['byday']);ix={d:i for i,d in enumerate(ds)};first={}
    for x in a['book']['audit']:
        if x['kind']=='pilot_layer_exit':
            for lid in x['layers']:first.setdefault(lid,x)
    out=[]
    for lid,r in first.items():
        sells=[t for t in a['book']['trades'] if t['side']=='sell' and any(p['layer']==lid for p in t['parts'])]
        l=next(x for x in a['layers'] if x['layer']==lid)
        out.append(dict(layer=lid,sid=l['sid'],request_at=r['at'],reason=r['reason'],
          first_actual_sell=sells[0]['at'] if sells else None,fully_closed_at=l['closed'],
          market_observations_to_first_sell=ix[day(sells[0]['at'])]-ix[day(r['at'])] if sells else None,
          still_pending_at_end=bool(l['qty']),net=l['net']))
    return out

def path(a,sid,actions,exits):
    ls=[x for x in a['layers'] if x['sid']==sid]
    weights=[dict(day=d,value=a['values'][d].get(sid,Z),weight_pct=a['values'][d].get(sid,Z)/n(r['nav'])*100)
             for d,r in a['byday'].items()]
    buys=[x for x in a['book']['trades'] if x['side']=='buy' and x['security_id']==sid]
    return dict(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],
      contribution=M.contribution(ls),first_actual_buy=buys[0]['at'] if buys else None,
      peak_weight=max(weights,key=lambda x:x['weight_pct']),actions=[x for x in actions if x['sid']==sid],
      exit_requests_and_fills=[x for x in exits if x['sid']==sid],layers=ls,weights=weights)

def run(win):
    root=O/'runs'/win;assert read(root/'DONE.json')['completed']
    old=W/('2022-normal-reference-20261031' if win=='2022' else 'q2-normal-continuation-20261031')/'runs/B_diag'
    prior=read(W/'migration-admission-singlepass-economics-20261101/analysis'/win/'COMPLETION.json')
    assert sha(old/'pair/B.json.gz')==prior['SC_book_sha256']
    data={'SC':A.account(win,'SC',old),'PVR_SLOT1':A.account(win,'PVR_SLOT1',root)}
    sets={k:M.participation(a) for k,a in data.items()};changes={}
    for k in sets['SC']:
        changes[k]=dict(SC=len(sets['SC'][k]),PVR_SLOT1=len(sets['PVR_SLOT1'][k]),
          gained=sorted(sets['PVR_SLOT1'][k]-sets['SC'][k]),lost=sorted(sets['SC'][k]-sets['PVR_SLOT1'][k]))
    save(Path('analysis')/win/'FUNDED_CHANGES.json',changes)
    candidates=rows(W/'opportunity-quality-ranking-20261031'/win/'CANDIDATES.jsonl.gz')
    mother={(x['sid'],x['day'],x['receipt']) for x in candidates};assert len(mother)==len(candidates)
    metrics={};allpaths={}
    for ref,a in data.items():
        rr=old if ref=='SC' else root;fund=rows(rr/'pair/funding.jsonl.gz')
        selected=sets[ref]['confirmed_receipts'];assert selected<=mother
        jr=a['book']['journal'];reserved=[x for x in jr if x['kind']=='real_reserve'];filled={x['budget_order'] for x in jr if x['kind']=='real_buy_fill'}
        actions=entry_actions(a);exits=exit_chain(a);conc=concentration(a);pool=M.pool_and_waits(win,ref,a)
        save(Path('analysis')/win/ref/'ENTRY_ACTIONS.json',actions);save(Path('analysis')/win/ref/'EXITS.json',exits)
        save(Path('analysis')/win/ref/'CONCENTRATION.json',conc)
        action_groups={kind:M.contribution([l for l in a['layers'] if l['layer'] in {x['layer'] for x in actions if x['action']==kind}])
                       for kind in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']}
        reasons=collections.Counter(x['result'] for x in fund if '09:30:00' in x['at'] and x['result']!='reserved')
        resource={str((day(x['at']),x['sid'],x['role'])) for x in fund if '09:30:00' in x['at'] and any(v in x['result'] for v in ['probe_risk','pool_capital'])}
        metrics[ref]=dict(**a['metrics'],contributions=M.contribution(a['layers']),**pool,
          admissions=len(reserved),actual_filled_orders=len(filled),zero_fill_reservations=sum(x['budget_order'] not in filled for x in reserved),
          funded_stocks=len(sets[ref]['all_stocks']),funded_attempts=len(sets[ref]['all_attempts']),
          confirmed_filled_receipts=len(selected),market_qualified_mother=len(mother),
          ACT_paused_qualified_receipts=sum(not a['byday'][x['day']]['on'] for x in candidates),
          source_right_boundary_receipts=sum(x['day']==day(a['daily'][-1]['at']) for x in candidates),
          filled_qualified_pct=D(len(selected))*100/len(mother),entry_action_groups=action_groups,
          role_pool_at_fill={role+'_'+pool:M.contribution([x for x in a['layers'] if x['role']==role and x['pool_at_fill']==pool]) for role in ['core','mobile'] for pool in ['probe','confirmed']},
          actual_layer_exit_requests=len(exits),actual_first_sell_layers=sum(x['first_actual_sell'] is not None for x in exits),
          pending_stock_exits=len(a['book']['exits']),opening_raw_reasons=dict(reasons),
          probe_or_pool_blocked_open_stock_roles=len(resource),
          exclusive_stale_probe_causal_blocks='unknown; original raw reasons coexist, no relaxed-state replay',
          concentration={k:v for k,v in conc.items() if k!='daily'})
        ranked=sorted(a['stock'],key=a['stock'].get,reverse=True)
        fixed=['601869.SH','301511.SZ','300308.SZ','300502.SZ']
        chosen=list(dict.fromkeys(ranked[:10]+ranked[-3:]+fixed))
        allpaths[ref]=[path(a,s,actions,exits) for s in chosen]
        save(Path('analysis')/win/ref/'TOP10_WORST3_AND_FIXED_PATHS.json',allpaths[ref])
        attempt=collections.defaultdict(list)
        for l in a['layers']:attempt[l['sector'],l['attempt']].append(l)
        save(Path('analysis')/win/ref/'INDUSTRY_ATTEMPT_CONTRIBUTIONS.json',
             [dict(sector=k[0],attempt=k[1],**M.contribution(v)) for k,v in attempt.items()])
    delta=[]
    for sid in sets['SC']['all_stocks']|sets['PVR_SLOT1']['all_stocks']:
        ss={ref:[l for l in a['layers'] if l['sid']==sid] for ref,a in data.items()}
        delta.append(dict(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],
          SC=M.contribution(ss['SC']),PVR_SLOT1=M.contribution(ss['PVR_SLOT1']),
          delta=sum((x['net'] for x in ss['PVR_SLOT1']),Z)-sum((x['net'] for x in ss['SC']),Z),
          category='new_funded_stock' if not ss['SC'] else 'lost_funded_stock' if not ss['PVR_SLOT1'] else 'common_funded_stock'))
    navdelta=n(data['PVR_SLOT1']['book']['ending_NAV'])-n(data['SC']['book']['ending_NAV'])
    assert abs(sum((x['delta'] for x in delta),Z)-navdelta)<D('.00000001')
    bridge={k:sum((x['delta'] for x in delta if x['category']==k),Z) for k in ['new_funded_stock','lost_funded_stock','common_funded_stock']}
    save(Path('analysis')/win/'STOCK_DELTA_BRIDGE.json',dict(delta_NAV=navdelta,parts=bridge,residual=Z,
       all_stocks=sorted(delta,key=lambda x:-x['delta'])))
    baseline_top=sorted(data['SC']['stock'],key=data['SC']['stock'].get,reverse=True)[:10]
    save(Path('analysis')/win/'BASELINE_TOP10.json',[next(x for x in delta if x['sid']==s) for s in baseline_top])
    first={}
    for name in ['funding','trades']:
        aa=rows(old/'pair/funding.jsonl.gz') if name=='funding' else data['SC']['book']['trades']
        bb=rows(root/'pair/funding.jsonl.gz') if name=='funding' else data['PVR_SLOT1']['book']['trades']
        i=next((i for i,(x,y) in enumerate(zip(aa,bb)) if x!=y),min(len(aa),len(bb)))
        first[name]=dict(index=i,SC=aa[i] if i<len(aa) else None,PVR_SLOT1=bb[i] if i<len(bb) else None,
                         accounting_difference_not_full_counterfactual_causality=True)
    save(Path('analysis')/win/'FIRST_DIVERGENCE.json',first)
    if win=='2025_26':
        cases=[]
        for sector,lo,hi in [('URFI881267','2025-07-01','2025-09-30'),('URFI881276','2025-10-01','2025-12-31'),('URFI881107','2026-01-01','2026-03-31')]:
            for ref,a in data.items():
                ds=[r for r in a['daily'] if lo<=day(r['at'])<=hi]
                weights=[(day(r['at']),sum((v for s,v in a['values'][day(r['at'])].items() if META[s]['sector_id']==sector),Z)/n(r['nav'])*100) for r in ds]
                buys=[t for t in a['book']['trades'] if t['side']=='buy' and lo<=day(t['at'])<=hi and META[t['security_id']]['sector_id']==sector]
                ls=[l for l in a['layers'] if l['sector']==sector and lo<=l['signal_day']<=hi]
                cases.append(dict(reference=ref,sector=sector,industry=next(v['industry'] for v in META.values() if v['sector_id']==sector),
                    window=[lo,hi],first_actual_buy=buys[0]['at'] if buys else None,
                    active_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in buys),Z),
                    peak_weight=max(weights,key=lambda x:x[1]),daily_weights=weights,signal_cohort_contribution=M.contribution(ls)))
        save(Path('analysis')/win/'THREE_FIXED_STRONG_CASES.json',cases)
    result=dict(window=win,SC=metrics['SC'],PVR_SLOT1=metrics['PVR_SLOT1'],delta_NAV=navdelta,stock_delta_bridge=bridge,
      funded_changes={k:dict(SC=v['SC'],PVR_SLOT1=v['PVR_SLOT1'],gained=len(v['gained']),lost=len(v['lost'])) for k,v in changes.items()})
    save(Path('analysis')/win/'COMPARISON.json',result)
    save(Path('analysis')/win/'COMPLETION.json',dict(passed=True,new_account_runs=0,
       SC_book_sha256=sha(old/'pair/B.json.gz'),PVR_SLOT1_book_sha256=sha(root/'pair/B.json.gz'),
       temporal_wait_math_sha256=sha(p),audited_cashflow_math_sha256=sha(W/'c1-drawdown-capacity-20261101/analyze_saved.py'),
       analysis_sha256=sha(Path(__file__)),layer_stock_cashflow_contribution_and_inventory_bridges=True))
    print('SAVED_ANALYSIS',win,'SC/PVR return',str(metrics['SC']['return_pct']),str(metrics['PVR_SLOT1']['return_pct']),
          'DD',str(metrics['SC']['global_DD']['percent']),str(metrics['PVR_SLOT1']['global_DD']['percent']),flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--window',choices=['2022','2025_26'],required=True);args=parser.parse_args()
    try:run(args.window)
    except BaseException as e:save('failure/ANALYSIS_ERROR.json',dict(window=args.window,type=type(e).__name__,reason=str(e)));raise
