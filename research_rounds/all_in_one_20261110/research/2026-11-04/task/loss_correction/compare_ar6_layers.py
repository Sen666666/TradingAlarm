"""Pure saved-JSON analysis. Never imports a runner or advances an event.

Reads both full observable JSONs (.gz accepted), with explicit completed cutoffs.
Layer IDs and campaign ordinals are policy-local; alignment uses signals/stocks.
"""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict
from datetime import datetime
import argparse,json,gzip,hashlib
getcontext().prec=80
Z=D(0);EPS=D('1e-12')

def read(p):
    p=Path(p);raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw),hashlib.sha256(raw).hexdigest()
def stamp(x):return datetime.fromisoformat(x).isoformat()
def dump(p,x):
    with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def near(a,b,label):
    if abs(a-b)>EPS:raise ValueError((label,str(a),str(b)))
def group(ll,keys):
    gg=defaultdict(list)
    for z in ll:gg[tuple(z[k] for k in keys)].append(z)
    out=[]
    for k,rr in sorted(gg.items()):
        cc=[z for z in rr if z['quantity_closed']];op=[z for z in rr if not z['quantity_closed']]
        cost=sum((D(z['buy_cost']) for z in rr),Z);contrib=sum((D(z['total_contribution']) for z in rr),Z)
        out.append(dict(**dict(zip(keys,k)),layers=len(rr),quantity_closed=not op,buy_cost=cost,buy_gross=sum((D(z['buy_gross']) for z in rr),Z),realized_trade_PNL=sum((D(z['realized_trade_PNL']) for z in rr),Z),unrealized=sum((D(z['unrealized_net_buy_cost']) for z in rr),Z),booked_dividend_income=sum((D(z['booked_dividend_income']) for z in rr),Z),total_contribution=contrib,closed_layer_positive=sum((max(Z,D(z['total_contribution'])) for z in cc),Z),closed_layer_negative=sum((min(Z,D(z['total_contribution'])) for z in cc),Z),open_layer_contribution=sum((D(z['total_contribution']) for z in op),Z),return_on_actual_buy_cost=contrib/cost if cost else None,first_buy=min(z['opened'] for z in rr),last_close=max((z['closed'] for z in rr if z['closed']),default=None) if not op else None,layer_ids=[z['layer'] for z in rr]))
    return out

def extract(x,cutoff,*,allow_account_only=False):
    a=x['account'];b=a['balance'];trades=a['trades'];buying={};sales=defaultdict(list);lastsale={}
    cursor=x.get('last_completed',x.get('last_completed_event'))
    if cursor is None and not allow_account_only:raise ValueError('missing runner cutoff; explicit externally-bound account-only reference flag required')
    if cursor is not None and str(cursor)[:10]!=cutoff:raise ValueError('saved state cutoff mismatch: future/stale marks cannot be used')
    if cursor is not None and datetime.fromisoformat(str(cursor)).hour!=15:raise ValueError('completed CLOSE state required')
    if any(str(t)[:10]>cutoff for t in a['market_asof'].values()):raise ValueError('future mark source after cutoff')
    # Stop rather than mislabel fractional-share cost writeoff as executed sales.
    # Only no-held-split references have been reviewed for this bounded extractor.
    # Native dispatch also logs splits of UNHELD stocks: the original action log
    # must explicitly prove old_shares==0 at that action before ignoring one.
    def unsafe_events(v,path):
        bad=[]
        if isinstance(v,dict):
            for k,z in v.items():
                if k in ('kind','classification','type') and isinstance(z,str) and ('fraction' in z.lower() or 'writeoff' in z.lower()):bad.append(dict(path=path,label=z))
                elif k=='kind' and z=='native_split':
                    proofs=[p for p in x.get('action_log',[]) if p.get('source',{}).get('sid')==v.get('sid') and str(v.get('event','')).endswith(p.get('source',{}).get('effective_date','UNKNOWN')) and D(p.get('ratio','1'))==D(v['ratio'])]
                    if not proofs or any(D(p.get('old_shares','-1'))!=0 for p in proofs):bad.append(dict(path=path,label='held_or_unproven_native_split',sid=v.get('sid')))
                elif isinstance(z,(dict,list)):bad+=unsafe_events(z,path+'/'+str(k))
        elif isinstance(v,list):
            for i,z in enumerate(v):bad+=unsafe_events(z,path+'/'+str(i))
        return bad
    unsafe=[]
    for label,v in [('native_callbacks',a.get('native_callbacks',[])),('action_log',x.get('action_log',[])),('events',x.get('events',[]))]:unsafe+=unsafe_events(v,label)
    if unsafe:raise ValueError(('explicit corporate-action/nontrade cost attribution required; no pure-trade claim',unsafe[:10]))
    for i,t in enumerate(trades):
        if t['at'][:10]>cutoff:raise ValueError('future trade after cutoff')
        if t['side']=='buy':
            if t['layer'] in buying:raise ValueError('layer has multiple buy fills; unsupported')
            buying[t['layer']]=(i,t)
        else:
            for p in t['parts']:
                sales[p['layer']].append(dict(p,at=t['at'],trade_index=i,receipt=t['receipt_id'],raw_price=t['price']))
                lastsale[p['layer']]=i
    ll=[]
    for z in a['layers']:
        i,t=buying[z['id']];cost=D(t['gross_cny'])+D(t['fees_cny']);q=int(z['qty']);m=a['capital_meta'][str(z['id'])]
        if cost<=0:raise ValueError('nonpositive actual cost')
        # The native unit_cost follows held splits. It is never a fresh CP1 floor.
        basis=D(q)*D(m['unit_cost'])*(cost/D(t['gross_cny'])) if q else Z
        if basis<0 or basis>cost+EPS:raise ValueError('unsupported quantity/cost branch')
        net=sum((D(p['net_cash']) for p in sales[z['id']]),Z)
        near(D(z['cash']),net-cost,'layer cash including buy fees')
        if q and z['sid'] not in a['market_marks']:raise ValueError('unknown held mark')
        mark=D(a['market_marks'].get(z['sid'],0));real=net-(cost-basis);unreal=D(q)*mark-basis;div=D(z['dividend']);total=real+unreal+div
        near(total,D(z['cash'])+div+D(q)*mark,'layer equity')
        if not q and z['id'] not in lastsale:raise ValueError('zero-quantity layer without sell: possible nontrade writeoff')
        reasons=sorted({p['reason'] for p in sales[z['id']]})
        ll.append(dict(layer=z['id'],sid=z['sid'],opened=z['opened'],signal_at=z['signal_at'],closed=z['closed'],role=m['role'],pool=m['pool'],purpose=m['purpose'],sector=m['sector'],source_context=m['source_context'],buy_trade_index=i,last_sell_trade_index=lastsale.get(z['id']),buy_receipt=t['receipt_id'],initial_qty=t['shares'],remaining_qty=q,quantity_closed=not q,buy_gross=D(t['gross_cny']),buy_fee=D(t['fees_cny']),buy_cost=cost,remaining_buy_cost=basis,actual_sell_parts=sales[z['id']],actual_reason_set=' | '.join(reasons) or 'NO_SALE',realized_trade_PNL=real,unrealized_net_buy_cost=unreal,booked_dividend_income=div,total_contribution=total,closed_return=total/cost if not q else None))
    # Recover actual flat-to-flat campaign from trade order and final close.
    # Splits change share units, not whether a prior layer was still held.
    active=defaultdict(list);number=defaultdict(int)
    for z in sorted(ll,key=lambda v:v['buy_trade_index']):
        sid=z['sid'];i=z['buy_trade_index'];active[sid]=[v for v in active[sid] if v['remaining_qty'] or v['last_sell_trade_index']>i]
        if not active[sid]:number[sid]+=1;entry='first' if number[sid]==1 else 'reentry'
        else:entry='add'
        z['campaign']=sid+'|actual_flat_to_flat|'+str(number[sid]);z['entry_class']=entry;active[sid].append(z)
    total=sum((z['total_contribution'] for z in ll),Z)
    near(total,D(b['nav'])-D('1000000'),'complete layer-to-NAV bridge; fixed original1m required')
    campaigns=group(ll,['sid','campaign']);stocks=group(ll,['sid'])
    for c in campaigns:c['closed_tail30']=bool(c['quantity_closed'] and c['return_on_actual_buy_cost']>=D('.3'))
    closed=[z for z in ll if z['quantity_closed']];opened=[z for z in ll if not z['quantity_closed']]
    tails=[z for z in closed if z['closed_return']>=D('.3')];ordinary=[z for z in closed if z['closed_return']<D('.3')]
    summary=dict(cutoff=cutoff,layers=len(ll),closed_layers=len(closed),open_layers=len(opened),campaigns=len(campaigns),quantity_closed_campaigns=sum(z['quantity_closed'] for z in campaigns),tail30_closed_layers=len(tails),tail30_closed_layer_contribution=sum((z['total_contribution'] for z in tails),Z),ordinary_closed_layer_contribution=sum((z['total_contribution'] for z in ordinary),Z),closed_negative_amount=-sum((min(Z,z['total_contribution']) for z in closed),Z),closed_positive_amount=sum((max(Z,z['total_contribution']) for z in closed),Z),open_layer_contribution=sum((z['total_contribution'] for z in opened),Z),open_layer_realized_partials=sum((z['realized_trade_PNL'] for z in opened),Z),open_layer_unrealized=sum((z['unrealized_net_buy_cost'] for z in opened),Z),open_layer_booked_dividend=sum((z['booked_dividend_income'] for z in opened),Z),actual_realized_trade_PNL=sum((z['realized_trade_PNL'] for z in ll),Z),actual_unrealized=sum((z['unrealized_net_buy_cost'] for z in ll),Z),booked_dividends=sum((z['booked_dividend_income'] for z in ll),Z),total_contribution=total)
    summary['terminal_clock_scope']='exact_saved_runner_CLOSE' if cursor is not None else 'externally_bound_account_only_reference; no runner cursor in supplied JSON'
    return dict(summary=summary,layers=ll,stocks=stocks,campaigns=campaigns,reason_groups=group(ll,['actual_reason_set']),role_groups=group(ll,['role','pool','purpose','entry_class']),signal_groups=group(ll,['sid','signal_at','role','pool','purpose','source_context']))

def funding(x):
    a=x['account'];g=x.get('goal_coverage');rows=[]
    if g is None:raise ValueError('missing complete native goal_coverage, cannot infer funding chains')
    tr={t['receipt_id']:t for t in a['trades']};batches={stamp(z['certificate']['known_at']):z for z in x['results']}
    for oid,owner in a['funding_coverage']['order_goals'].items():
        cert=batches[stamp(owner['created_at'])]['certificate'];cid=cert['certificate_id']
        sold=[tr[eid] for eid,v in g['sale_events'].items() if v['order']==oid]
        if not sold:continue
        if not all(z['side']=='sell' for z in sold):raise ValueError('wrong funding event kind')
        ids=[z['settlement_id'] for z in sold];settled=[dict(settlement=s,**g['settled'][s]) for s in ids if s in g['settled']]
        if not all(s in g['receivables'] and g['receivables'][s]['origin_order']==oid for s in ids):raise ValueError('funding settlement source differs')
        bought=[]
        for eid,event in x['authority']['events'].items():
            order=x['authority']['orders'][event['oid']]
            if order['cid']==cid:bought.append(tr[eid])
        rows.append(dict(original_plan_at=cert['known_at'],deadline=cert['deadline'],certificate=cid,source_exit_order=oid,source_sales=sold,actual_source_gross=sum((D(t['gross_cny']) for t in sold),Z),actual_source_net=sum((D(t['gross_cny'])-D(t['fees_cny']) for t in sold),Z),settlements=settled,owner_goals=owner['goals'],planned_Q={s:q for s,q in cert['Q'].items() if q},planned_D=cert['D'],same_certificate_actual_C_buys=bought,not_per_dollar_attribution=True,may_share_receivers_with_other_source_rows=True))
    return sorted(rows,key=lambda v:(v['original_plan_at'],v['source_exit_order']))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reference',required=True);ap.add_argument('--challenger',required=True);ap.add_argument('--cutoff',required=True);ap.add_argument('--output',required=True);ap.add_argument('--skip-funding',action='store_true');ap.add_argument('--allow-reference-account-only',action='store_true');args=ap.parse_args()
    out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sides={};ident={};funds={}
    for side,path in [('reference',args.reference),('NO_AR6',args.challenger)]:
        raw,h=read(path);sides[side]=extract(raw,args.cutoff,allow_account_only=side=='reference' and args.allow_reference_account_only);ident[side]=dict(path=str(Path(path).resolve()),sha256=h)
        if not args.skip_funding:
            if side=='reference' and args.allow_reference_account_only and 'goal_coverage' not in raw:funds[side]=dict(status='UNAVAILABLE_IN_SUPPLIED_REFERENCE_ACCOUNT_ONLY_EXPORT; not zero funding')
            else:funds[side]=funding(raw)
    ref,new=sides['reference'],sides['NO_AR6'];delta=[]
    rr={z['sid']:z for z in ref['stocks']};nn={z['sid']:z for z in new['stocks']}
    for sid in sorted(set(rr)|set(nn)):
        a=rr.get(sid);b=nn.get(sid)
        delta.append(dict(sid=sid,participation='common_stock' if a and b else 'new_stock' if b else 'lost_stock',reference=a,NO_AR6=b,whole_stock_contribution_delta=(b['total_contribution'] if b else Z)-(a['total_contribution'] if a else Z)))
    near(sum((v['whole_stock_contribution_delta'] for v in delta),Z),new['summary']['total_contribution']-ref['summary']['total_contribution'],'stock contribution delta bridge')
    sdelta=[]
    keys=['sid','signal_at','role','pool','purpose','source_context']
    rg={tuple(z[k] for k in keys):z for z in ref['signal_groups']};ng={tuple(z[k] for k in keys):z for z in new['signal_groups']}
    for key in sorted(set(rg)|set(ng)):
        a=rg.get(key);b=ng.get(key);sdelta.append(dict(**dict(zip(keys,key)),reference=a,NO_AR6=b,signal_group_contribution_delta=(b['total_contribution'] if b else Z)-(a['total_contribution'] if a else Z),interpretation='same signal grouping is descriptive; altered timing/quantity/other positions remain endogenous'))
    near(sum((v['signal_group_contribution_delta'] for v in sdelta),Z),new['summary']['total_contribution']-ref['summary']['total_contribution'],'signal contribution delta bridge')
    # Fixed baseline cohorts retain their original label; never retag baseline winners.
    tails=[z for z in ref['campaigns'] if z['closed_tail30']]
    cohorts=[]
    for c in tails:
        sid=c['sid'];cohorts.append(dict(reference_closed_tail_campaign=c,challenger_all_actual_campaigns_same_stock=[z for z in new['campaigns'] if z['sid']==sid],whole_stock_bridge=next(z for z in delta if z['sid']==sid),not_a_matched_causal_campaign_return=True))
    out.mkdir(parents=True)
    for side,z in sides.items():
        for kind,v in z.items():dump(out/(side+'-'+kind+'.json'),v)
        if not args.skip_funding:dump(out/(side+'-FUNDING_CHAINS.json'),funds[side])
    dump(out/'STOCK_DELTA.json',sorted(delta,key=lambda v:v['whole_stock_contribution_delta']))
    dump(out/'SAME_SIGNAL_GROUP_DELTA.json',sdelta);dump(out/'REFERENCE_TAIL_CAMPAIGN_COHORT.json',cohorts)
    dump(out/'IDENTITY_AND_SCOPE.json',dict(inputs=ident,cutoff=args.cutoff,financial_events=0,account_restores=0,initial_NAV_each='1000000',independent_aggregation_only=True,notes=['Layer IDs/campaign ordinals are local to each policy; do not align numerically.','Inventory-closed contribution can include booked unpaid dividend; closed trade PnL and dividends separated.','Open-layer contribution includes sold partial PnL and booked dividend, not pure floating profit.','Signal/stock bridges are exact accounting attribution, not causal policy PnL or avoidable-loss estimates.','No new future labels computed; tail30 uses actual closed economic contribution and actual buy cost.','Current-survivor developer data and daily execution proxies persist.','Funding receivers may repeat across source-exit rows: never sum them as independent buy cash.']))
    print(json.dumps({k:v['summary'] for k,v in sides.items()},ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
