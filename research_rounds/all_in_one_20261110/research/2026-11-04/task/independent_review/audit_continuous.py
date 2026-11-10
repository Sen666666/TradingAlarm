"""Read-only independent ledger/campaign audit. Never imports account code."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
from datetime import datetime
import json,gzip,hashlib,argparse
getcontext().prec=70
HERE=Path(__file__).resolve().parent;TASK=HERE.parent
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0);INITIAL=D(1000000);EPS=D('1e-12');SOURCES={}
def read(p):
    p=Path(p);b=p.read_bytes();SOURCES[str(p)]=hashlib.sha256(b).hexdigest()
    return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def eq(a,b,where):assert abs(a-b)<EPS,(where,str(a),str(b))
def stamp(s):return datetime.fromisoformat(str(s))
def curve_audit(events):
    events=sorted(events,key=lambda e:stamp(e['at']));closes=[e for e in events if e['phase']=='CLOSE']
    assert len({(e['at'],e['phase']) for e in events})==len(events)
    def dd(rows):
        peak=INITIAL;worst=Z
        for e in rows:
            nav=D(e['bridge']['nav']);peak=max(peak,nav);worst=max(worst,1-nav/peak)
        return worst
    return dict(close_points=len(closes),event_points=len(events),close_DD=dd(closes),event_observation_DD=dd(events),
        mean_close_exposure=sum((D(e['bridge']['inventory'])/D(e['bridge']['nav']) for e in closes),Z)/len(closes))
def audit(x,end):
    a=x['account'];b=a['balance'];trades=a['trades'];fills=a['fills'];layers=a['layers'];cut=stamp(end+'T15:10:00+08:00')
    if 'last_completed' in x:assert stamp(x['last_completed'])==cut
    for t in trades+fills:assert stamp(t['at'])<=cut
    assert all(stamp(v)<=cut for v in a['market_asof'].values())
    assert len({f['receipt_id'] for f in fills})==len(fills)
    assert {f['receipt_id'] for f in fills}=={t['receipt_id'] for t in trades}
    buy={t['layer']:t for t in trades if t['side']=='buy'};assert len(buy)==len(layers)
    sold=defaultdict(lambda:Z)
    for t in trades:
        if t['side']=='sell':
            assert sum(p['shares'] for p in t['parts'])==t['shares']
            eq(sum((D(p['net_cash']) for p in t['parts']),Z),D(t['gross_cny'])-D(t['fees_cny']),'sell parts')
            for p in t['parts']:sold[p['layer']]+=D(p['net_cash'])
    # Keep cumulative original basis under actual integer splits. No share writeoff is silently accepted.
    timeline=[(stamp(t['at']),1,k,'trade',t) for k,t in enumerate(trades)]
    for k,c in enumerate(a.get('native_callbacks',[])):
        kind=c.get('kind','')
        assert 'writeoff' not in kind and 'fraction' not in kind
        if kind=='native_split':timeline.append((stamp(c['event'].split(':')[-1]+'T00:00:00+08:00'),0,k,'split',c))
    holdings=defaultdict(int);active={};campaigns=[];layercamp={}
    for at,_,_,kind,t in sorted(timeline,key=lambda q:q[:3]):
        assert at<=cut;sid=t.get('security_id',t.get('sid'))
        if kind=='split':
            qty=D(holdings[sid])*D(t['ratio']);assert qty==int(qty);holdings[sid]=int(qty);continue
        if t['side']=='buy':
            if holdings[sid]==0:
                active[sid]=len(campaigns);campaigns.append(dict(sid=sid,opened=t['at'],closed=None,layers=[]))
            cc=active[sid];campaigns[cc]['layers'].append(t['layer']);layercamp[t['layer']]=cc;holdings[sid]+=t['shares']
        else:
            holdings[sid]-=t['shares'];assert holdings[sid]>=0
            if holdings[sid]==0:campaigns[active.pop(sid)]['closed']=t['at']
    records=[]
    for l in layers:
        lid=l['id'];t=buy[lid];cost=D(t['gross_cny'])+D(t['fees_cny']);m=a['capital_meta'][str(lid)]
        remain=D(l['qty'])*D(m['unit_cost'])*cost/D(t['gross_cny'])
        mark=D(a['market_marks'][l['sid']]) if l['qty'] else Z
        realized=sold[lid]-(cost-remain);unreal=D(l['qty'])*mark-remain;div=D(l['dividend'])
        contribution=D(l['cash'])+div+D(l['qty'])*mark
        eq(realized+unreal+div,contribution,'layer basis/cash bridge')
        records.append(dict(id=lid,sid=l['sid'],cost=cost,remaining=l['qty'],realized=realized,unrealized=unreal,dividend=div,contribution=contribution))
    inventory=sum((D(l['qty'])*D(a['market_marks'][l['sid']]) for l in layers if l['qty']),Z)
    eq(inventory,D(b['inventory']),'inventory')
    fees=sum((D(f['fees_cny']) for f in fills),Z);eq(fees,D(b['fees_cny']),'fees')
    flow=sum((D(f['gross_cny'])*(1 if f['side']=='sell' else -1) for f in fills),Z)
    div=sum((r['dividend'] for r in records),Z)
    cash=sum((D(b[k]) for k in ['available','order_reserved','sale_receivable']),Z)
    # This branch's saved corp-action protocol leaves all booked dividends
    # unpaid. Without a per-layer payment bridge, do not call a flat campaign
    # with paid/unknown claims cash-closed using only cumulative layer income.
    eq(div,D(b['dividend_receivable']),'supported unpaid-only dividend allocation')
    assert all(z.get('paid_at') is None for z in a.get('native_dividends',{}).values())
    eq(INITIAL+flow-fees+div+inventory,D(b['nav']),'NAV journal')
    eq(INITIAL+flow-fees+div-D(b['dividend_receivable']),cash,'cash journal')
    eq(sum((r['contribution'] for r in records),Z),D(b['nav'])-INITIAL,'all layer PNL')
    eq(sum((D(o['remaining_budget_cny'])+D(o['fee_reserved_cny']) for o in a['buys'].values()),Z),D(b['order_reserved']),'reserved')
    by={r['id']:r for r in records}
    for c in campaigns:
        rr=[by[l] for l in c['layers']]
        c['cost']=sum((r['cost'] for r in rr),Z);c['contribution']=sum((r['contribution'] for r in rr),Z)
        c['dividend']=sum((r['dividend'] for r in rr),Z);c['remaining']=sum(r['remaining'] for r in rr)
        c['cash_closed']=c['remaining']==0 and c['dividend']==0
        c['tail30']=c['cash_closed'] and c['contribution']/c['cost']>=D('.3')
    closed=[r for r in records if not r['remaining']];opened=[r for r in records if r['remaining']]
    cashclosed=[c for c in campaigns if c['cash_closed']]
    summary=dict(nav=D(b['nav']),wealth_PNL=D(b['nav'])-INITIAL,fees=fees,layers=len(layers),stocks=len({l['sid'] for l in layers}),
        strict_trade_realized=sum((r['realized'] for r in records),Z),unrealized=sum((r['unrealized'] for r in records),Z),dividend=div,
        closed_layer_positive=sum((max(Z,r['contribution']) for r in closed),Z),closed_layer_negative=sum((min(Z,r['contribution']) for r in closed),Z),
        closed_layers=len(closed),open_layers=len(opened),open_layer_contribution=sum((r['contribution'] for r in opened),Z),
        campaigns=len(campaigns),cash_closed_campaigns=len(cashclosed),active_campaigns=sum(bool(c['remaining']) for c in campaigns),
        cash_closed_tail30_count=sum(c['tail30'] for c in cashclosed),cash_closed_tail30_net=sum((c['contribution'] for c in cashclosed if c['tail30']),Z),
        cash_closed_ordinary_net=sum((c['contribution'] for c in cashclosed if not c['tail30']),Z),
        tail30_campaigns=[c for c in cashclosed if c['tail30']])
    # Prefix money arithmetic uses saved authoritative inventory, not an independent price feed.
    checks=0
    for e in x.get('events',[]):
        at=stamp(e['at']);assert at<=cut;bb=e['bridge'];ff=[f for f in fills if stamp(f['at'])<=at]
        d=sum((D(z['net_local']) for z in a.get('native_dividends',{}).values() if stamp(z['ex_at'])<=at),Z)
        fflow=sum((D(f['gross_cny'])*(1 if f['side']=='sell' else -1) for f in ff),Z);ffee=sum((D(f['fees_cny']) for f in ff),Z)
        eq(D(bb['nav']),INITIAL+fflow-ffee+d+D(bb['inventory']),'prefix NAV')
        eq(sum((D(bb[k]) for k in ['available','order_reserved','sale_receivable']),Z),INITIAL+fflow-ffee+d-D(bb['dividend_receivable']),'prefix cash');checks+=1
    summary['event_prefix_money_checks']=checks
    return summary,records,campaigns
def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2025_26'],required=True);args=p.parse_args();w=args.window
    SOURCES[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    new=read(TASK/'ar6_native_feasibility/runs'/w/'FINAL.json.gz')
    old=read(OLD/('g-s-C-R0-continuous-january-v1-20261102/baseline_readonly/C10-NATIVE_ACCOUNT.json' if w=='2022' else 'g-s-C-August-continuation-v1-20261102/runs/C10/2025-08-29-CLOSE.json'))
    end='2022-01-28' if w=='2022' else '2025-08-29';n,nr,nc=audit(new,end);o,orr,oc=audit(old,end)
    published=read(TASK/'risk_constraints'/('ar6_results_'+w)/'COMPARISON.json')
    if w=='2022':
        # Original Jan account-only export has no event log; explicitly bind the published curve.
        curve=read(Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-2022-month-native-baseline-20261102/analysis/2022-C10-NAV.json'))
        oldevents=[dict(at=e['at'],phase=e['phase'],bridge=dict(nav=e['NAV'],inventory=e['inventory'])) for e in curve]
    else:oldevents=old['events']
    o['curve']=curve_audit(oldevents);n['curve']=curve_audit(new['events'])
    for side,ss in [('original',o),('NO_AR6',n)]:
        pp=published[side];eq(ss['nav'],D(pp['terminal_NAV']),'published NAV')
        for a,b in [('strict_trade_realized','strict_actual_trade_realized'),('unrealized','unrealized_mark_minus_remaining_buy_cost'),('closed_layer_positive','closed_position_layer_positive'),('closed_layer_negative','closed_position_layer_negative'),('open_layer_contribution','open_position_layer_contribution')]:eq(ss[a],D(pp['pnl'][b]),'published '+a)
        for a,b in [('campaigns','campaigns'),('cash_closed_campaigns','cash_closed_campaigns'),('cash_closed_tail30_count','cash_closed_tail30_campaigns')]:assert ss[a]==pp[b],(a,ss[a],pp[b])
        eq(ss['cash_closed_tail30_net'],D(pp['closed_campaign_tail_net']),'published tail')
        eq(ss['cash_closed_ordinary_net'],D(pp['closed_campaign_ordinary_net']),'published ordinary')
        for k in ['close_DD','event_observation_DD']:eq(ss['curve'][k],D(pp[k]['max_DD']),'published '+k)
        eq(ss['curve']['mean_close_exposure'],D(pp['mean_close_exposure']),'published exposure')
        assert ss['curve']['close_points']==pp['close_points']
    out=dict(status='PASS_WITH_SCOPE',window=w,original=o,NO_AR6=n,NAV_difference=n['nav']-o['nav'],
        classification_warning='Each-arm tail30 is retrospective and changes membership with cost/size; ordinary and tail differences are not a common fixed cohort or independent causal decomposition.',
        valuation_scope='original authoritative marks; no independent price feed or real opening certification',account_events=0,source_sha256=SOURCES)
    (HERE/('CONTINUOUS_'+w+'_AUDIT.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='source_sha256'},ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
