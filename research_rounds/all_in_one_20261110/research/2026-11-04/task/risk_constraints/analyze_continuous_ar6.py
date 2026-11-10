"""Read saved C10/NO_AR6 JSON only. No account class/import/run capability.

Usage: --window 2022|2025_26 --final .../FINAL.json.gz --out NEW_DIRECTORY
Optional --flow-jsonl provides exact saved daily permission/holding exports.
"""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict, Counter
from datetime import datetime
import json, gzip, argparse, hashlib, csv
import re

getcontext().prec=28
Z=D(0);INITIAL=D(1000000);EPS=D('1e-12')
ROOT=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
JAN=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-2022-month-native-baseline-20261102')
SOURCES={}

def read(p):
    p=Path(p);raw=p.read_bytes();SOURCES[str(p.resolve())]=hashlib.sha256(raw).hexdigest()
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)

def save(p,x):
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')

def exact(a,b,what):
    err=abs(a-b)
    assert err<EPS,(what,str(a),str(b),str(err))
    return err

def timekey(x):return datetime.fromisoformat(str(x))

def input_boundaries(x,cutoff):
    a=x['account'];checks=0
    for name,rows in [('events',x.get('events',[])),('fills',a['fills']),('trades',a['trades']),('action_log',x.get('action_log',[]))]:
        for row in rows:
            assert timekey(row['at'])<=cutoff,('future '+name,row['at'],str(cutoff));checks+=1
    for sid,at in a['market_asof'].items():
        assert timekey(at)<=cutoff,('future asof mark',sid,at);checks+=1
    for event in a.get('native_actions',[]):
        days=re.findall(r'\d{4}-\d{2}-\d{2}',event)
        assert days and all(day<=cutoff.date().isoformat() for day in days),('future/unknown applied action',event)
        checks+=1
    for row in a.get('native_callbacks',[]):
        if row.get('at'):
            assert timekey(row['at'])<=cutoff,('future callback',row);checks+=1
    return dict(passed=True,cutoff=cutoff.isoformat(),asof_checks=checks,
        future_intent_deadlines_and_known_payment_schedules_not_mislabelled_as_executed_events=True)

def financial_bridges(a):
    b=a['balance'];fills=a['fills'];flow=sum((D(f['gross_cny'])*(1 if f['side']=='sell' else -1) for f in fills),Z)
    fee=sum((D(f['fees_cny']) for f in fills),Z);income=sum((D(z['dividend']) for z in a['layers']),Z)
    inventory=sum((D(z['qty'])*D(a['market_marks'][z['sid']]) for z in a['layers'] if z['qty']),Z)
    reserved=sum((D(o['remaining_budget_cny'])+D(o['fee_reserved_cny']) for o in a['buys'].values()),Z)
    cash=sum((D(b[k]) for k in ('available','order_reserved','sale_receivable')),Z)
    diffs=dict(nav_journal=D(b['nav'])-(INITIAL+flow-fee+income+inventory),
        cash_journal=cash-(INITIAL+flow-fee+income-D(b['dividend_receivable'])),
        layer_cash=sum((D(z['cash']) for z in a['layers']),Z)-(flow-fee),
        native_equity=D(b['nav'])-(cash+D(b['dividend_receivable'])+inventory),
        order_reserved=D(b['order_reserved'])-reserved,fee_sum=D(b['fees_cny'])-fee,
        inventory=D(b['inventory'])-inventory)
    assert all(abs(v)<EPS for v in diffs.values()),diffs
    quantities=defaultdict(int)
    for z in a['layers']:quantities[z['sid']]+=z['qty']
    native={s:sum(v['shares'] for v in p['lots']) for s,p in a['native_inventory'].items()}
    assert {s:q for s,q in quantities.items() if q}=={s:q for s,q in native.items() if q}
    assert {s:q for s,q in quantities.items() if q}=={s:q for s,q in b['quantities'].items() if q}
    assert len({f['receipt_id'] for f in fills})==len(fills)
    tf={t['receipt_id']:t for t in a['trades']}
    assert set(tf)=={f['receipt_id'] for f in fills}
    for f in fills:
        t=tf[f['receipt_id']]
        assert all(f[k]==t[k] for k in ('security_id','side','shares','gross_cny','fees_cny','at'))
        exact(D(t['shares'])*D(t['price']),D(t['gross_cny']),'fill price')
    return dict(passed=True,seven_money_differences=diffs,share_bridge=True,fill_trade_receipts_exact=True,
        booked_dividend=income,dividend_receivable=D(b['dividend_receivable']),confirmed_dividend_cash=income-D(b['dividend_receivable']))

def accounting(x):
    """Replay actual sale parts and integer actual splits to allocate original basis.

    Current native guard rejects fractional held-share conversion before action.
    Any unexpected nontrade share disappearance fails explicitly instead of
    relabelling it as a sale or pushing it into unrealized PnL.
    """
    a=x['account'];bridge=financial_bridges(a);terminal={z['id']:z for z in a['layers']}
    replay={};holding=defaultdict(int);ever=set();campaigns=[];active={};sale_rows=[]
    timeline=[]
    for ix,t in enumerate(a['trades']):timeline.append((timekey(t['at']),1,ix,'trade',t))
    for ix,c in enumerate(a.get('native_callbacks',[])):
        if c.get('kind')=='native_split':
            day=c['event'].split(':')[-1]
            timeline.append((timekey(day+'T00:00:00+08:00'),0,ix,'split',c))
        elif 'fraction' in c.get('kind','') or 'writeoff' in c.get('kind',''):
            raise ValueError('Explicit nontrade basis allocation required: '+str(c))
    for at,_,ix,kind,t in sorted(timeline,key=lambda z:z[:3]):
        sid=t.get('security_id',t.get('sid'))
        if kind=='split':
            ratio=D(t['ratio'])
            for lid,r in replay.items():
                if r['sid']!=sid or not r['qty']:continue
                q=D(r['qty'])*ratio
                assert q==int(q),'fractional share conversion unsupported in saved native policy'
                r['qty']=int(q)
            total=D(holding[sid])*ratio;assert total==int(total);holding[sid]=int(total)
            continue
        if t['side']=='buy':
            lid=t['layer'];assert lid not in replay
            label='add' if holding[sid] else 'reentry' if sid in ever else 'first'
            if not holding[sid]:
                cid=len(campaigns)+1;active[sid]=cid
                campaigns.append(dict(campaign=cid,sid=sid,opened=t['at'],closed=None,layers=[]))
            cid=active[sid];campaigns[cid-1]['layers'].append(lid)
            basis=D(t['gross_cny'])+D(t['fees_cny'])
            replay[lid]=dict(layer=lid,sid=sid,campaign=cid,qty=t['shares'],basis=basis,original_basis=basis,
                buy_gross=D(t['gross_cny']),buy_fee=D(t['fees_cny']),opened=t['at'],signal_at=t['signal_at'],
                entry_class=label,buy_receipt=t['receipt_id'],sales=[],realized=Z,basis_sold=Z)
            holding[sid]+=t['shares'];ever.add(sid)
        else:
            assert sum(p['shares'] for p in t['parts'])==t['shares']
            exact(sum((D(p['fee_cny']) for p in t['parts']),Z),D(t['fees_cny']),'sell fee parts')
            exact(sum((D(p['net_cash']) for p in t['parts']),Z),D(t['gross_cny'])-D(t['fees_cny']),'sell cash parts')
            for part in t['parts']:
                r=replay[part['layer']];q=part['shares'];assert 0<q<=r['qty']
                basis=r['basis'] if q==r['qty'] else r['basis']*D(q)/r['qty']
                r['basis']-=basis;r['basis_sold']+=basis;r['qty']-=q
                pnl=D(part['net_cash'])-basis;r['realized']+=pnl
                row=dict(**part,sid=sid,at=t['at'],receipt=t['receipt_id'],buy_basis=basis,realized_trade_PNL=pnl,
                    gross=D(part['net_cash'])+D(part['fee_cny']))
                r['sales'].append(row);sale_rows.append(row)
            holding[sid]-=t['shares'];assert holding[sid]>=0
            if not holding[sid]:campaigns[active.pop(sid)-1]['closed']=t['at']
    records=[]
    all_unpaid=(bridge['confirmed_dividend_cash']==0)
    for lid,z in terminal.items():
        r=replay[lid];assert r['qty']==z['qty'],('share replay',lid,r['qty'],z['qty'])
        m=a['capital_meta'][str(lid)];mark=D(a['market_marks'][z['sid']]) if z['qty'] else Z
        unreal=D(z['qty'])*mark-r['basis'];div=D(z['dividend']);contribution=r['realized']+unreal+div
        exact(contribution,D(z['cash'])+div+D(z['qty'])*mark,'layer money')
        duties=[dict(id=k,**v) for k,v in a.get('exit_duties',{}).items() if v['layer']==lid]
        first=min(duties,key=lambda d:d['requested_at']) if duties else None
        records.append(dict(layer=lid,sid=z['sid'],campaign=r['campaign'],opened=r['opened'],signal_at=r['signal_at'],
            closed=z['closed'],remaining_qty=z['qty'],buy_gross=r['buy_gross'],buy_fee=r['buy_fee'],buy_cost=r['original_basis'],
            remaining_cost=r['basis'],realized_trade_PNL=r['realized'],unrealized_net_buy_cost=unreal,
            booked_dividend_income=div,known_unpaid_dividend=(div if all_unpaid else None),total_contribution=contribution,
            role=m['role'],pool=m['pool'],purpose=m['purpose'],sector=m['sector'],source_context=m['source_context'],
            entry_class=r['entry_class'],actual_sell_parts=r['sales'],exit_duties=duties,
            same_buy_day_exit_requested=bool(first and first['requested_at'][:10]==r['opened'][:10])))
    real=sum((r['realized_trade_PNL'] for r in records),Z);unreal=sum((r['unrealized_net_buy_cost'] for r in records),Z)
    income=sum((r['booked_dividend_income'] for r in records),Z)
    exact(real+unreal+income,D(a['balance']['nav'])-INITIAL,'account PnL')
    bylayer={r['layer']:r for r in records}
    for c in campaigns:
        rr=[bylayer[k] for k in c['layers']]
        for k in ('buy_cost','buy_gross','realized_trade_PNL','unrealized_net_buy_cost','booked_dividend_income','total_contribution'):
            c[k]=sum((r[k] for r in rr),Z)
        c['remaining_qty']=sum(r['remaining_qty'] for r in rr)
        c['position_closed']=c['remaining_qty']==0
        c['claim_status']='known_unpaid_claim' if all_unpaid and c['booked_dividend_income'] else 'no_dividend_claim' if not c['booked_dividend_income'] else 'claim_allocation_unknown'
        c['fully_closed_cash']=c['position_closed'] and c['claim_status']=='no_dividend_claim'
        c['net_return_on_buy_cost']=c['total_contribution']/c['buy_cost']
        c['cash_closed_tail30']=c['fully_closed_cash'] and c['net_return_on_buy_cost']>=D('.3')
    closed=[r for r in records if r['remaining_qty']==0];op=[r for r in records if r['remaining_qty']]
    pnl=dict(strict_actual_trade_realized=real,nontrade_basis_writeoff=Z,realized_including_nontrade=real,
        unrealized_mark_minus_remaining_buy_cost=unreal,booked_dividend=income,
        unpaid_dividend_AR=bridge['dividend_receivable'],confirmed_dividend_cash=bridge['confirmed_dividend_cash'],
        total_wealth_PNL=real+unreal+income,closed_position_layer_positive=sum((max(Z,r['total_contribution']) for r in closed),Z),
        closed_position_layer_negative=sum((min(Z,r['total_contribution']) for r in closed),Z),
        open_position_layer_contribution=sum((r['total_contribution'] for r in op),Z),
        open_position_realized_partials=sum((r['realized_trade_PNL'] for r in op),Z),
        open_position_dividend=sum((r['booked_dividend_income'] for r in op),Z))
    return records,sale_rows,campaigns,pnl,bridge

def curve_stats(events):
    events=sorted(events,key=lambda e:timekey(e['at']));by={}
    for e in events:
        key=(str(e['at']),e['phase']);assert key not in by,'duplicate observation';by[key]=e
    def dd(ee):
        peak=INITIAL;worst=Z;where=None
        for e in ee:
            v=D(e['bridge']['nav']);peak=max(peak,v);loss=1-v/peak
            if loss>worst:worst=loss;where=e['at']
        return dict(max_DD=worst,trough_at=where)
    closes=[e for e in events if e['phase']=='CLOSE'];assert closes
    expo=[D(e['bridge']['inventory'])/D(e['bridge']['nav']) for e in closes]
    risks=[D(e['bridge']['resources']['risk'])/D(e['bridge']['nav']) for e in closes if 'resources' in e['bridge']]
    return dict(close_points=len(closes),event_points=len(events),close_DD=dd(closes),event_observation_DD=dd(events),
        mean_close_exposure=sum(expo,Z)/len(expo),peak_close_exposure=max(expo),terminal_exposure=expo[-1],
        mean_close_risk_NAV=sum(risks,Z)/len(risks) if risks else None,max_close_risk_NAV=max(risks) if risks else None,
        risk_observation_count=len(risks))

def event_bridges(x):
    """Independent prefix flow/income arithmetic over saved events, no event API."""
    a=x['account'];divs=list(a.get('native_dividends',{}).values());fills=a['fills'];checks=[]
    assert all(d['currency']=='CNY' for d in divs),'currency conversion requires explicit original FX attribution'
    exact(sum((D(d['net_local']) for d in divs),Z),sum((D(z['dividend']) for z in a['layers']),Z),'dividend event/layer attribution')
    for e in x.get('events',[]):
        at=timekey(e['at']);b=e['bridge'];ff=[f for f in fills if timekey(f['at'])<=at]
        flow=sum((D(f['gross_cny'])*(1 if f['side']=='sell' else -1) for f in ff),Z)
        fee=sum((D(f['fees_cny']) for f in ff),Z)
        income=sum((D(d['net_local']) for d in divs if timekey(d['ex_at'])<=at),Z)
        cash=sum((D(b[k]) for k in ('available','order_reserved','sale_receivable')),Z)
        differences=dict(nav=D(b['nav'])-(INITIAL+flow-fee+income+D(b['inventory'])),
            cash=cash-(INITIAL+flow-fee+income-D(b['dividend_receivable'])),fees=D(b['fees_cny'])-fee,
            equity=D(b['nav'])-(cash+D(b['dividend_receivable'])+D(b['inventory'])))
        assert all(abs(v)<EPS for v in differences.values()),(e['at'],e['phase'],differences)
        checks.append(dict(at=e['at'],phase=e['phase'],differences=differences))
    return dict(event_states=len(checks),checks=checks,independent_price_feed=False,
        inventory_mark_basis='saved authoritative original event inventory; not an independent market-price reconstruction')

def stock_aggregate(records):
    d=defaultdict(lambda:dict(buy_cost=Z,realized=Z,unrealized=Z,dividend=Z,contribution=Z,layers=0,qty=0))
    for r in records:
        v=d[r['sid']];v['layers']+=1;v['qty']+=r['remaining_qty']
        for a,b in [('buy_cost','buy_cost'),('realized','realized_trade_PNL'),('unrealized','unrealized_net_buy_cost'),('dividend','booked_dividend_income'),('contribution','total_contribution')]:v[a]+=r[b]
    return {k:dict(v) for k,v in d.items()}

def grouped(records,keys):
    groups=defaultdict(list)
    for r in records:groups[tuple(r[k] for k in keys)].append(r)
    result=[]
    for values,rr in sorted(groups.items()):
        z=dict(zip(keys,values));z.update(layers=len(rr),stocks=len({r['sid'] for r in rr}),
            closed_position_layers=sum(not r['remaining_qty'] for r in rr),open_position_layers=sum(bool(r['remaining_qty']) for r in rr))
        for k in ('buy_cost','buy_gross','realized_trade_PNL','unrealized_net_buy_cost','booked_dividend_income','total_contribution'):
            z[k]=sum((r[k] for r in rr),Z)
        z['closed_layer_negative']=sum((min(Z,r['total_contribution']) for r in rr if not r['remaining_qty']),Z)
        result.append(z)
    return result

def summarize(x,events):
    ll,ss,cc,pnl,bridge=accounting(x);a=x['account'];b=a['balance'];st=stock_aggregate(ll)
    cutoff=max(timekey(e['at']) for e in events)
    boundary=input_boundaries(x,cutoff)
    exits=defaultdict(lambda:dict(parts=0,gross=Z,net=Z,fees=Z,realized=Z,stocks=set(),receipts=set()))
    for s in ss:
        v=exits[s['reason']];v['parts']+=1;v['gross']+=s['gross'];v['net']+=D(s['net_cash']);v['fees']+=D(s['fee_cny']);v['realized']+=s['realized_trade_PNL'];v['stocks'].add(s['sid']);v['receipts'].add(s['receipt'])
    exits={k:dict(v,stocks=sorted(v['stocks']),receipts=sorted(v['receipts'])) for k,v in exits.items()}
    buys=[f for f in a['fills'] if f['side']=='buy'];sells=[f for f in a['fills'] if f['side']=='sell']
    byreason=Counter();raw=[]
    for m in x.get('mapping',[]):
        for z in m['stocks']:
            if z.get('stock_Q') is True and z.get('preliminary') and z.get('CP1_id'):
                raw.append(dict(day=m['at'][:10],sid=z['sid'],receipt=z['CP1_id']))
    keys={(r['sid'],r['signal_at'][:10]) for r in ll}
    for r in raw:r['actual_any_role_layer_same_stock_signal_day']=(r['sid'],r['day']) in keys
    res=dict(terminal_NAV=D(b['nav']),return_from_original_1m=D(b['nav'])/INITIAL-1,pnl=pnl,
        **curve_stats(events),fees=D(b['fees_cny']),actual_buy_gross=sum((D(f['gross_cny']) for f in buys),Z),
        actual_sell_gross=sum((D(f['gross_cny']) for f in sells),Z),buy_fills=len(buys),sell_fills=len(sells),
        actual_funded_stocks=len(st),layers=len(ll),campaigns=len(cc),cash_closed_campaigns=sum(c['fully_closed_cash'] for c in cc),
        cash_closed_tail30_campaigns=sum(c['cash_closed_tail30'] for c in cc),
        position_closed_with_unpaid_claim_campaigns=sum(c['position_closed'] and c['claim_status']=='known_unpaid_claim' for c in cc),
        active_stock_campaigns=sum(not c['position_closed'] for c in cc),
        ACT=a['policy']['act'],ACT_incidents=a['policy'].get('incidents',[]),
        cumulative_losses_record_only=a['policy'].get('losses',{}),active_native_buys=len(a['buys']),active_native_exits=len(a['exits']),
        pending_intents=len(x.get('pending',[])) if 'pending' in x else None,
        entry_classes=dict(Counter(r['entry_class'] for r in ll)),same_buy_day_exit_requests=sum(r['same_buy_day_exit_requested'] for r in ll),
        exit_reasons=exits,raw_stock_Q_fresh_CP1_events=(len(raw) if 'mapping' in x else None),
        raw_events_actually_funded_same_signal=(sum(r['actual_any_role_layer_same_stock_signal_day'] for r in raw) if 'mapping' in x else None),
        raw_opportunity_mapping_available=('mapping' in x),
        role_pool_entry_groups=grouped(ll,['role','pool','entry_class']),sector_groups=grouped(ll,['sector']),
        closed_campaign_tail_net=sum((c['total_contribution'] for c in cc if c['cash_closed_tail30']),Z),
        closed_campaign_ordinary_net=sum((c['total_contribution'] for c in cc if c['fully_closed_cash'] and not c['cash_closed_tail30']),Z),
        campaign_classification='only position flat and no unpaid/unknown dividend claim is cash-closed; >=30% net/buy-cost tail; others separately retained',
        participation_scope='raw stockQ + preliminary + fresh CP1; not all-resource or ACT-unlocked executability',
        financial_bridges=bridge,event_financial_bridges=event_bridges(x),input_boundary_checks=boundary,
        old_account_only_prefix_note=('authoritative old NAV curve supplied separately; full event cash prefixes not present in this account-only export' if 'events' not in x else None))
    return res,ll,ss,cc,st,raw

def baseline(window):
    if window=='2022':
        x=read(ROOT/'g-s-C-R0-continuous-january-v1-20261102/baseline_readonly/C10-NATIVE_ACCOUNT.json')
        curve=read(JAN/'analysis/2022-C10-NAV.json')
        events=[dict(at=e['at'],phase=e['phase'],bridge=dict(nav=e['NAV'],inventory=e['inventory'])) for e in curve]
        old=read(JAN/'analysis/2022-C10-SUMMARY.json')
        exact(D(x['account']['balance']['nav']),D(old['final_NAV']),'baseline published NAV')
        return x,events,old
    x=read(ROOT/'g-s-C-August-continuation-v1-20261102/runs/C10/2025-08-29-CLOSE.json')
    return x,x['events'],None

def flow_analysis(x,flows,layers,window):
    close=[f for f in flows if f['phase']=='CLOSE'];calendar=[f['day'] for f in close]
    assert len(calendar)==len(set(calendar))
    assert [(timekey(f['at']),f['phase']) for f in flows]==[(timekey(f['at']),f['phase']) for f in x['events']],'FLOW/final event prefix mismatch'
    for fk,ak in [('new_fills','fills'),('new_trades','trades')]:
        combined=[z for f in flows for z in f[fk]]
        assert combined==x['account'][ak],('FLOW/final exact actual financial payload mismatch',fk)
    metadata=read(ROOT/'g-s-C-month-continuation-20261102/inputs'/window/'metadata.json')
    daily=[];risk_by_role=defaultdict(lambda:Z);permit=[];scopes=[]
    mapped={m['at'][:10]:m['stocks'] for m in x.get('mapping',[])}
    for f in close:
        rv=f['resources'];b=f['bridge'];nav=D(b['nav']);rows=rv['rows'];held=defaultdict(lambda:Z)
        for sid,q in rv['held_quantities'].items():held[rv['sector_by_sid'][sid]]+=D(q)*D(rv['prices'][sid])
        exact(sum(held.values(),Z),D(b['inventory']),'daily actual holding inventory')
        exact(sum((D(r['risk']) for r in rows),Z),D(b['resources']['risk']),'flow risk rows')
        exact(sum((D(r['capital']) for r in rows),Z),D(b['resources']['capital']),'flow capital rows')
        for r in rows:risk_by_role[r['role']+'|'+r['pool']]+=D(r['risk'])
        pp=rv['permissions'];ss=rv['scopes'];scopes.append((f['day'],ss))
        for z in mapped.get(f['day'],[]):
            if z.get('stock_Q') is not True or not z.get('preliminary') or not z.get('CP1_id'):continue
            sector=metadata[z['sid']]['sector']
            use='S' if pp.get(sector,{}).get('S') else 'G' if pp.get('G',{}).get('G') else 'T' if pp.get(sector,{}).get('T') else None
            scope='G' if use=='G' else sector
            permit.append(dict(day=f['day'],sid=z['sid'],receipt=z['CP1_id'],sector=sector,use=use,
                scope=scope,context=ss.get(scope,{}).get('context'),qualified=use is not None))
        q={s:n for p in f['projection'] for s,n in p['Q'].items() if n};d={s:n for p in f['projection'] for s,n in p['D'].items() if n}
        daily.append(dict(day=f['day'],NAV=nav,inventory=b['inventory'],cash_available=b['available'],
            actual_exposure=D(b['inventory'])/nav,nominal_risk=b['resources']['risk'],nominal_risk_NAV=D(b['resources']['risk'])/nav,
            risk_capital_rows=rv['totals'],pending_order_count=len(rv['pending_orders']),exit_order_count=len(rv['exit_orders']),
            ACT=rv['ACT'],incident=rv['incident'],permissions=pp,
            held_industry_weights={s:v/nav for s,v in held.items()},planned_Q=q,planned_D=d,
            planned_Q_distinct=len(q),planned_D_distinct=len(d)))
    return dict(daily=daily,risk_yuan_observation_sum_by_role_pool=dict(risk_by_role),
        planned_buy_stock_days=sum(z['planned_Q_distinct'] for z in daily),planned_donor_stock_days=sum(z['planned_D_distinct'] for z in daily),
        exact_permission_observations=permit,
        participation_sector_mapping_status='original frozen current-roster sector metadata; survivorship/current classification development bias retained',
        planned_amounts_are_not_fills=True,FLOW_final_event_fill_trade_identity_exact=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2025_26'],required=True);p.add_argument('--final',type=Path,required=True)
    p.add_argument('--flow-jsonl',type=Path);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    x=read(args.final);end='2022-01-28' if args.window=='2022' else '2025-08-29'
    assert timekey(x['last_completed'])==timekey(end+'T15:10:00+08:00'),'Exact final original CLOSE cutoff required'
    new=summarize(x,x['events']);oldx,oldevents,published=baseline(args.window);old=summarize(oldx,oldevents)
    nr,nl,ns,nc,nst,nraw=new;orr,ol,os,oc,ost,oraw=old
    expected=19 if args.window=='2022' else 44
    assert nr['close_points']==orr['close_points']==expected
    keys=set(nst)|set(ost);deltas=[]
    for s in keys:
        n=nst.get(s,{});o=ost.get(s,{})
        deltas.append(dict(sid=s,old=o,new=n,wealth_difference=n.get('contribution',Z)-o.get('contribution',Z)))
    exact(sum((d['wealth_difference'] for d in deltas),Z),nr['terminal_NAV']-orr['terminal_NAV'],'all stock wealth difference')
    deltas.sort(key=lambda z:z['wealth_difference'],reverse=True)
    comparison=dict(window=args.window,original=orr,NO_AR6=nr,NAV_difference=nr['terminal_NAV']-orr['terminal_NAV'],
        return_pp_difference=(nr['return_from_original_1m']-orr['return_from_original_1m'])*100,
        pnl_difference={k:nr['pnl'][k]-orr['pnl'][k] for k in nr['pnl']},
        new_funded_stocks=sorted(set(nst)-set(ost)),lost_original_funded_stocks=sorted(set(ost)-set(nst)),
        no_individual_trade_causal_claim=True,no_hindsight_input=True,financial_events_by_analysis=0)
    for name,data in [('COMPARISON',comparison),('NO_AR6_LAYERS',nl),('NO_AR6_SALES',ns),('NO_AR6_CAMPAIGNS',nc),
        ('ORIGINAL_LAYERS',ol),('ORIGINAL_CAMPAIGNS',oc),('STOCK_DIFFERENCES',deltas),('NO_AR6_RAW_OPPORTUNITIES',nraw),('ORIGINAL_RAW_OPPORTUNITIES',oraw)]:save(args.out/(name+'.json'),data)
    if args.flow_jsonl:
        raw=args.flow_jsonl.read_bytes();SOURCES[str(args.flow_jsonl.resolve())]=hashlib.sha256(raw).hexdigest()
        flows=[json.loads(line) for line in raw.splitlines() if line]
        flow_result=flow_analysis(x,flows,nl,args.window)
        save(args.out/'SAVED_FLOW_ANALYSIS.json',flow_result)
    save(args.out/'SOURCE_MANIFEST.json',dict(sources=SOURCES,analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        zero_account_imports=True,zero_financial_events=True,baseline_no_R0=True,legacy_published_summary=published))
    print(json.dumps(dict(window=args.window,NO_AR6_NAV=nr['terminal_NAV'],original_NAV=orr['terminal_NAV'],delta=comparison['NAV_difference'],
        close_points=expected,source_files=len(SOURCES)),default=str),flush=True)

if __name__=='__main__':main()
