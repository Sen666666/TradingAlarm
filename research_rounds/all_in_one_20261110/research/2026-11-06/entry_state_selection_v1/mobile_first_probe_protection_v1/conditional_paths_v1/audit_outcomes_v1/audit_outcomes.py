"""Independent read-only arithmetic audit. Never imports or runs a trading engine."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from datetime import datetime
from collections import defaultdict, Counter
import argparse, csv, gzip, hashlib, json, math
import pandas as pd
Z=D(0); TOL=D('0.0000001')
ROOT=Path(__file__).resolve().parent.parent
IDS=[27,17,28,1527,1542,2891,2893,343,361,1942,1952,2898,2905,2897]
ARMS=['CP_CONTROL_COMMON_I_SIZE','I_PROBE_COMMON_I_SIZE']
END='2026-05-15'
def dec(x): return D(str(x))
def ts(x): return datetime.fromisoformat(str(x))
def day(x): return str(x)[:10]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def eq(x,y,label):
    assert abs(dec(x)-dec(y))<=TOL,(label,str(x),str(y),str(dec(x)-dec(y)))
def emit(p,z):
    assert not p.exists(),('no overwrite',str(p))
    p.write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def table(p,rows):
    if not rows: return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('x') as f:
        w=csv.DictWriter(f,keys);w.writeheader()
        for r in rows:
            w.writerow({k:json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def version(rows,at):
    ds=day(at);v=[r for r in rows if r['from']<=ds and (not r.get('to') or ds<r['to'])]
    assert len(v)==1,(at,'dated version ambiguity',v)
    return v[0]
def schedule(rules,sid,at):
    venue=version(rules['venue_versions'][sid],at)['venue']
    return version(rules['fee_versions'][venue],at)['schedule']
def fees(rules,sid,at,side,q,p,paid=None,accrued=None):
    if not q:return {},{}
    paid=paid or {};accrued=accrued or {};out={};add={}
    for c in schedule(rules,sid,at)['components']:
        if c.get('side','both') not in ('both',side):continue
        name=c['name'];basis=c.get('amount_basis','notional')
        base=dec(q)*p if basis=='notional' else dec(q)
        if basis=='par_value':base*=dec(rules['security_metadata'][sid]['par_value'])
        a=base*dec(c['rate']);add[name]=a
        total=max(dec(c.get('minimum_local',0)),a+(accrued.get(name,Z) if c.get('basis','order')=='order' else Z))
        if c.get('maximum_local') is not None:total=min(total,dec(c['maximum_local']))
        if c.get('rounding_unit') is not None:
            u=dec(c['rounding_unit']);total=(total/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
        out[name]=max(Z,total-paid.get(name,Z)) if c.get('basis','order')=='order' else total
    return out,add
def fee_total(rules,sid,at,q,p):return sum(fees(rules,sid,at,'sell',q,p)[0].values(),Z)
def stats(rows):
    closed=[r for r in rows if r['closed'] is not None];wins=[r for r in closed if r['net']>0];loss=[r for r in closed if r['net']<0]
    avg=lambda rr,k:sum((r[k] for r in rr),Z)/len(rr) if rr else None
    aw=avg(wins,'net');al=avg(loss,'net');arw=avg(wins,'return_on_buy_cost');arl=avg(loss,'return_on_buy_cost')
    return dict(rounds=len(rows),closed=len(closed),W=len(wins),L=len(loss),flat=len(closed)-len(wins)-len(loss),
        win_fraction=dec(len(wins))/dec(len(wins)+len(loss)) if wins or loss else None,
        closed_net=sum((r['net'] for r in closed),Z),average_win=aw,average_loss=al,payoff_ratio=aw/abs(al) if aw is not None and al else None,
        average_win_return=arw,average_loss_return=arl,payoff_ratio_returns=arw/abs(arl) if arw is not None and arl else None,
        closed_tail_30pct=sum(r['return_on_buy_cost']>=D('.3') for r in closed),
        open_positive=sum(r['closed'] is None and r['net']>0 for r in rows),
        open_negative=sum(r['closed'] is None and r['net']<0 for r in rows),
        open_flat=sum(r['closed'] is None and r['net']==0 for r in rows))
def new_unit(**kw):
    return dict(qty=0,buy_shares=0,buy_cost=Z,sale_net=Z,dividend=Z,dividend_paid=Z,fees=Z,closed=None,first_sell=None,
        cost=Z,holding_closes=0,held_dates=[],cost_days=Z,missing_price_closes=0,first_economic_recovery=None,first_cash_recovery=None,
        min_close_pnl=None,min_low_pnl=None,min_event_pnl=None,min_close_return=None,min_low_return=None,min_event_return=None,max_cost=Z,**kw)
def update_min(r,key,value,at):
    if r[key] is None or value<r[key]:r[key]=value;r[key+'_at']=at
def pnl_snapshot(r,qty,price,rules,sid,at):
    liquidation=dec(qty)*price*D('.9995')-fee_total(rules,sid,at,qty,price*D('.9995')) if qty else Z
    return r['sale_net']+r['dividend']+liquidation-r['buy_cost']
def source_data(freeze,sid):
    rp=[p for p in freeze if p.endswith('/bars/'+sid+'.parquet')]
    ap=[p for p in freeze if p.endswith('/actions/'+sid+'.json')]
    assert len(rp)==len(ap)==1,(sid,rp,ap)
    raw=pd.read_parquet(rp[0]);raw['day']=pd.to_datetime(raw['trade_date']).dt.strftime('%Y-%m-%d');raw=raw.set_index('day').sort_index()
    actions=read(ap[0])['events']
    raw['_audit_valid']=raw.apply(valid_row,axis=1)
    return raw,actions
def valid_row(row):
    if row is None:return False
    return bool(row.get('observed_bar',True)) and bool(row.get('price_eligible',True)) and not bool(row.get('source_invalid',False)) and all(pd.notna(row[k]) and math.isfinite(float(row[k])) and float(row[k])>0 for k in ['open','high','low','close'])
def mark(raw,actions,at):
    ds=day(at);r=raw.loc[:ds]
    eligible=r.loc[r['_audit_valid']]
    assert len(eligible),('no valid source mark',at)
    sd=eligible.index[-1];v=eligible.iloc[-1];p=dec(v['close'])
    for a in sorted(actions,key=lambda a:a['effective_date']):
        if sd<a['effective_date']<=ds:
            p=(p-dec(a.get('signal_cash_per_old_share',a['cash_per_old_share'])))/dec(a.get('signal_split_ratio',a['split_ratio']))
    return p,sd
def audit_path(p,freeze,rules,netfactor):
    x=json.load(gzip.open(p,'rt'));c=x['case'];sid=c['sid'];arm=x['summary']['arm'];identity=dict(case_id=c['round_id'],sid=sid,name=c['name'],arm=arm)
    daily=x['daily'];assert day(daily[0]['at'])==c['signal_day'] and day(daily[-1]['at'])==END
    assert [day(d['at']) for d in daily]==[day(v) for v in rules['decision_cutoffs'] if c['signal_day']<=day(v)<=END],('common calendar mismatch',identity)
    assert dec(daily[0]['nav'])==dec(c['seed_nav']) and not daily[0]['positions']
    raw,actions=source_data(freeze,sid);qty=0;cost=Z;tradecash=Z;divtotal=Z;paidtotal=Z;feetotal=Z
    rounds=[];layers={};groups={};cur=None;events=[];divmap={};diagnostics=[];checks=Counter()
    # Original source actions are separate expectation events, not assumed present in journal.
    for a in actions:
        if c['signal_day']<a['effective_date']<=END:events.append((ts(a['effective_date']+'T00:00:00+08:00'),-1,0,'source_action',a))
    for n,j in enumerate(x['journal']):
        if j['kind'] in ['real_buy_fill','real_sell_fill','actual_split']:events.append((ts(j['at']),1,n,'journal',j))
    for n,a in enumerate(x['audit']):
        if a['kind']=='dividend_accrual':events.append((ts(a['receivable']['ex_at']),0,n,'div',a['receivable']))
        if a['kind']=='dividend_payment':events.append((ts(a['at']),2,n,'paydiv',a))
    events.sort(key=lambda v:v[:3]);ei=0;expected_div={};expected_split={}
    fills=[a for a in x['audit'] if a['kind']=='fill'];fillby={a['receipt']['receipt_id']:a for a in fills}
    assert len(fillby)==len(x['trades'])
    fee_paid=defaultdict(dict);fee_acc=defaultdict(dict)
    for t in x['trades']:
        a=fillby[t['receipt_id']];oid=a['order_id'];q=t['shares'];px=dec(t['price']);parts,ac=fees(rules,sid,t['at'],t['side'],q,px,fee_paid[oid],fee_acc[oid])
        assert a['fee_schedule']==schedule(rules,sid,t['at'])['schedule_id']
        eq(sum(parts.values(),Z),t['fees_cny'],'dated fill fee');eq(dec(q)*px,t['gross_cny'],'fill gross')
        for k,v in parts.items():eq(v,a['fee_components'][k],'fee component');fee_paid[oid][k]=fee_paid[oid].get(k,Z)+v
        for k,v in ac.items():fee_acc[oid][k]=fee_acc[oid].get(k,Z)+v
        assert day(t['signal_at'])<day(t['at']) if t['side']=='buy' else True
        checks['fill_fees']+=1
    bridge=[]
    for d in daily:
        at=ts(d['at']);ds=day(at)
        while ei<len(events) and events[ei][0]<=at:
            et,_,_,kind,e=events[ei];ei+=1
            if kind=='source_action':
                if qty and dec(e['cash_per_old_share']):
                    expected_div['dividend:'+sid+':'+e['effective_date']]=dec(qty)*dec(e['cash_per_old_share'])*netfactor
                if qty and dec(e['split_ratio'])!=1:expected_split['split:'+sid+':'+e['effective_date']]=(qty,dec(e['split_ratio']))
                continue
            if kind=='div':
                amount=dec(e['net_local']);eq(amount,expected_div.pop(e['event_id']),'source dividend entitlement')
                assert qty>0
                divtotal+=amount;cur['dividend']+=amount
                allocations={}
                for lid,l in layers.items():
                    if l['qty']:
                        v=amount*dec(l['qty'])/dec(qty);l['dividend']+=v;groups[l['group']]['dividend']+=v;allocations[lid]=v
                divmap[e['event_id']]=(cur,allocations,amount)
                checks['dividend_entitlements']+=1;continue
            if kind=='paydiv':
                ent=e['entitlement'];rr,alloc,amount=divmap[ent['event_id']]
                paidtotal+=amount;rr['dividend_paid']+=amount
                for lid,v in alloc.items():layers[lid]['dividend_paid']+=v;groups[layers[lid]['group']]['dividend_paid']+=v
                checks['dividend_payments']+=1;continue
            k=e['kind']
            if k=='real_buy_fill':
                if qty==0:
                    origin='SEED_MOBILE' if day(e['signal_at'])==c['signal_day'] else ('LATER_FIRST_' if not rounds else 'REENTRY_')+e['role'].upper()
                    cur=new_unit(round=len(rounds)+1,opened=e['at'],signal=e['signal_at'],origin=origin,first_role=e['role'],layer_ids=[],first_group=e['budget_order'])
                    rounds.append(cur)
                q=e['shares'];amount=dec(q)*dec(e['price'])+dec(e['fees']);lid=e['layer'];gid=e['budget_order']
                if gid not in groups:groups[gid]=new_unit(group=gid,round=cur['round'],opened=e['at'],signal=e['signal_at'],origin=cur['origin'],first_role=e['role'],layer_ids=[])
                l=new_unit(layer=lid,group=gid,round=cur['round'],opened=e['at'],signal=e['signal_at'])
                assert lid not in layers;layers[lid]=l;cur['layer_ids'].append(lid);groups[gid]['layer_ids'].append(lid)
                for r in [cur,groups[gid],l]:r['qty']+=q;r['buy_shares']+=q;r['buy_cost']+=amount;r['cost']+=amount;r['fees']+=dec(e['fees'])
                qty+=q;cost+=amount;tradecash-=amount;feetotal+=dec(e['fees'])
            elif k=='real_sell_fill':
                q=e['shares'];assert qty>=q>0
                value=dec(q)*dec(e['price'])-dec(e['fees']);oldqty=qty;cost*=dec(qty-q)/dec(qty);qty-=q;tradecash+=value;feetotal+=dec(e['fees'])
                cur['qty']-=q;cur['cost']=cost;cur['sale_net']+=value;cur['fees']+=dec(e['fees']);cur['first_sell']=cur['first_sell'] or e['at']
                assert sum(z['shares'] for z in e['parts'])==q
                for part in e['parts']:
                    l=layers[part['layer']];g=groups[l['group']];n=part['shares'];v=value*dec(n)/dec(q);ff=dec(e['fees'])*dec(n)/dec(q)
                    assert l['qty']>=n;eq(v,part['net_cash'],'layer sale allocation')
                    # Per-layer remaining cost is proportional within that physical layer.
                    l['cost']*=dec(l['qty']-n)/dec(l['qty'])
                    for r in [l,g]:
                        r['qty']-=n;r['sale_net']+=v;r['fees']+=ff;r['first_sell']=r['first_sell'] or e['at']
                        if not r['qty']:r['closed']=e['at']
                if not qty:cur['closed']=e['at'];cost=Z;cur['cost']=Z
            else:
                ratio=dec(e['ratio']);target=int(dec(qty)*ratio)
                if qty:
                    old,r=expected_split.pop(e['event_id']);assert old==qty and r==ratio
                active=[l for l in layers.values() if l['qty']];parts=[int(dec(l['qty'])*ratio) for l in active]
                extra=target-sum(parts)
                for n in range(extra):parts[n%len(parts)]+=1
                for l,q in zip(active,parts):groups[l['group']]['qty']+=q-l['qty'];l['qty']=q
                qty=target
                if cur:cur['qty']=qty
                if not qty and cur and cur['closed'] is None:
                    cur['closed']=e['at'];cur['closed_by']='split_fraction_writeoff';cost=Z;cur['cost']=Z
                    diagnostics.append('Round closed by fractional split writeoff')
                    for l in active:
                        if not l['qty']:l['closed']=e['at'];l['cost']=Z
                    for g in groups.values():
                        if not g['qty'] and g['closed'] is None:g['closed']=e['at']
                checks['splits']+=1
            if k in ['real_buy_fill','real_sell_fill']:
                erow=raw.loc[day(et)] if day(et) in raw.index else None
                assert erow is not None and pd.notna(erow['open']) and dec(erow['open'])>0
                for rr in rounds+list(groups.values()):
                    pv=pnl_snapshot(rr,rr['qty'],dec(erow['open']),rules,sid,e['at'])
                    update_min(rr,'min_event_pnl',pv,e['at']);update_min(rr,'min_event_return',pv/rr['buy_cost'],e['at'])
        assert qty==sum(l['qty'] for l in layers.values())==d['positions'].get(sid,0)
        eq(cost,d['remaining_stock_cost'],'remaining K')
        live={l['id']:l for l in d['layers']};assert set(live)=={lid for lid,l in layers.items() if l['qty']}
        for lid,l in live.items():assert l['qty']==layers[lid]['qty'];eq(l['dividend'],layers[lid]['dividend'],'layer dividend');eq(l['cash'],layers[lid]['sale_net']-layers[lid]['buy_cost'],'layer cash')
        independent_mark,markday=mark(raw,actions,at) if qty else (Z,None)
        eq(dec(qty)*independent_mark,d['inventory'],'independent raw inventory')
        eq(dec(c['seed_nav'])+tradecash+divtotal+dec(qty)*independent_mark,d['nav'],'independent NAV')
        eq(dec(c['seed_nav'])+tradecash+paidtotal,dec(d['available'])+dec(d['order_reserved'])+dec(d['sale_receivable']),'cash resource bridge')
        eq(divtotal-paidtotal,d['dividend_receivable'],'dividend receivable')
        eq(feetotal,d['fees_cny'],'cumulative fee')
        audits=[a for a in x['audit'] if ts(a.get('at',a.get('receipt',{}).get('at',a.get('receivable',{}).get('ex_at',d['at']))))<=at]
        reserved=sum((dec(a['gross_budget_cny'])+dec(a['fee_reserved_cny']) for a in audits if a['kind']=='reserve'),Z)
        reserved-=sum((dec(a['receipt']['gross_cny'])+dec(a['receipt']['fees_cny']) for a in audits if a['kind']=='fill' and a['receipt']['side']=='buy'),Z)
        reserved-=sum((dec(a['gross_released'])+dec(a['fee_released']) for a in audits if a['kind']=='release_buy'),Z)
        eq(reserved,d['order_reserved'],'reserved cash audit')
        settled={a['settlement']['settlement_id'] for a in audits if a['kind']=='settle'}
        salerec=sum((dec(t['gross_cny'])-dec(t['fees_cny']) for t in x['trades'] if t['side']=='sell' and ts(t['at'])<=at and t['settlement_id'] not in settled),Z)
        eq(salerec,d['sale_receivable'],'sale receivable')
        eq(d['settlement_locked'],d['payable'],'buy lock payable')
        row=raw.loc[ds] if ds in raw.index else None;usable=valid_row(row)
        for rr in rounds:
            rr['cost']=cost if rr is cur else Z
        for gid,g in groups.items():g['cost']=sum((l['cost'] for l in layers.values() if l['group']==gid),Z)
        units=rounds+list(groups.values())
        for r in units:
            if ts(r['opened'])>at:continue
            if r['qty']:
                r['holding_closes']+=1;r['held_dates'].append(ds);r['cost_days']+=r['cost'];r['max_cost']=max(r['max_cost'],r['cost'])
                if not usable:r['missing_price_closes']+=1
                else:
                    pc=pnl_snapshot(r,r['qty'],dec(row['close']),rules,sid,d['at']);pl=pnl_snapshot(r,r['qty'],dec(row['low']),rules,sid,d['at'])
                    update_min(r,'min_close_pnl',pc,d['at']);update_min(r,'min_low_pnl',pl,d['at'])
                    update_min(r,'min_close_return',pc/r['buy_cost'],d['at']);update_min(r,'min_low_return',pl/r['buy_cost'],d['at'])
                    if pc>=0 and r['first_economic_recovery'] is None:r['first_economic_recovery']=d['at']
            if not r['qty'] and r['sale_net']+r['dividend']>=r['buy_cost'] and r['first_economic_recovery'] is None:r['first_economic_recovery']=r['closed']
            # All sampled sales settle same day, but verify before using as cash recovery.
            soldt=[t for t in x['trades'] if t['side']=='sell' and ts(t['at'])<=at and any(p['layer'] in r['layer_ids'] for p in t['parts'])]
            settlednet=sum((sum((dec(p['net_cash']) for p in t['parts'] if p['layer'] in r['layer_ids']),Z) for t in soldt if t['settlement_id'] in settled),Z)
            if settlednet+r['dividend_paid']>=r['buy_cost'] and r['first_cash_recovery'] is None:r['first_cash_recovery']=d['at']
        bridge.append(dict(**identity,at=d['at'],qty=qty,cost=cost,raw_mark=independent_mark,raw_mark_day=markday,
            native_inventory=d['inventory'],native_NAV=d['nav'],trade_cash=tradecash,dividend_accrued=divtotal,dividend_paid=paidtotal,
            cash_available=d['available'],reserved=reserved,sale_receivable=salerec,unknown_today_price=bool(qty and not usable),pending_exit=sid in d['pending_sells']))
        checks['daily_balances']+=1
    assert ei==len(events) and not expected_div and not expected_split
    finalmark,finalmarkday=mark(raw,actions,daily[-1]['at']);finalusable=END in raw.index and valid_row(raw.loc[END])
    triggers=[a for a in x['audit'] if a['kind']=='pilot_layer_exit']
    for r in rounds+list(groups.values()):
        r['net']=r['sale_net']+r['dividend']+dec(r['qty'])*finalmark-r['buy_cost']
        r['cash_realized_net']=r['sale_net']+r['dividend_paid']-r['buy_cost']
        r['unpaid_dividend']=r['dividend']-r['dividend_paid']
        r['return_on_buy_cost']=r['net']/r['buy_cost']
        r['status']=('CLOSED_WIN' if r['net']>0 else 'CLOSED_LOSS' if r['net']<0 else 'CLOSED_FLAT') if r['closed'] else ('OPEN_UNKNOWN' if not finalusable else 'OPEN_POSITIVE' if r['net']>0 else 'OPEN_NEGATIVE' if r['net']<0 else 'OPEN_FLAT')
        r['terminal_net_liquidation_pnl']=pnl_snapshot(r,r['qty'],finalmark,rules,sid,daily[-1]['at']) if finalusable else None
        r['closed_tail_30pct']=bool(r['closed'] and r['return_on_buy_cost']>=D('.3'))
        matches=[a for a in triggers if set(a['layers']).intersection(r['layer_ids'])]
        r['first_exit_trigger']=matches[0]['at'] if matches else None
        r['first_exit_reason']=matches[0]['reason'] if matches else None
        r['exit_to_first_fill_calendar_days']=(ts(r['first_sell'])-ts(r['first_exit_trigger'])).total_seconds()/86400 if r['first_sell'] and matches else None
        r['exit_to_flat_calendar_days']=(ts(r['closed'])-ts(r['first_exit_trigger'])).total_seconds()/86400 if r['closed'] and matches else None
        r['pending_exit_common_closes']=sum(any(z['id'] in r['layer_ids'] and any(z['id'] in tr['layers'] and ts(tr['at'])<=ts(d['at']) for tr in triggers) for z in d['layers']) and sid in d['pending_sells'] for d in daily)
        r['exit_to_first_fill_common_closes']=sum(ts(r['first_exit_trigger'])<=ts(d['at'])<ts(r['first_sell']) for d in daily) if r['first_sell'] and matches else None
        r['exit_to_flat_common_closes']=sum(ts(r['first_exit_trigger'])<=ts(d['at'])<ts(r['closed']) for d in daily) if r['closed'] and matches else None
        r['max_adverse_observed_close_and_fill']=min(v for v in [r['min_event_pnl'],r['min_close_pnl']] if v is not None)
        r['max_adverse_including_visible_low_proxy']=min(v for v in [r['min_event_pnl'],r['min_low_pnl']] if v is not None)
        r['max_adverse_close_and_fill_return']=min(v for v in [r['min_event_return'],r['min_close_return']] if v is not None)
        r['max_adverse_visible_low_and_fill_return']=min(v for v in [r['min_event_return'],r['min_low_return']] if v is not None)
        r['holding_calendar_days']=(ts(r['closed'] or daily[-1]['at'])-ts(r['opened'])).total_seconds()/86400
        r.update(identity)
    eq(sum((r['net'] for r in rounds),Z),dec(daily[-1]['nav'])-dec(c['seed_nav']),'round NAV decomposition')
    assert len(rounds)==len(x['rounds'])
    for rr,original in zip(rounds,x['rounds']):
        eq(rr['net'],original['net'],'reported round net');assert rr['closed']==original['closed']
    firstgroups=[groups[r['first_group']] for r in rounds]
    for lid,l in layers.items():
        original=next(v for v in x['layers'] if v['id']==lid);assert original['qty']==l['qty'];eq(original['cash'],l['sale_net']-l['buy_cost'],'final layer cash');eq(original['dividend'],l['dividend'],'final layer div')
    seed=[g for g in firstgroups if day(g['signal'])==c['signal_day']]
    assert len(seed)<=1
    seedrow=dict(**identity,entered=bool(seed),signal=c['signal_day'],seed_NAV=c['seed_nav'],seed_no_entry_reasons=[f for f in x['funding'] if day(f['at'])==c['signal_day']],original_first_layer_net=c['first_layer_net_pnl'],original_first_layer_exit=c['exit_day'])
    if seed:seedrow.update(seed[0])
    else:seedrow.update(status='NO_ENTRY',net=None,closed=None,qty=0)
    metrics=[]
    for scope,rr in [('WHOLE_ROUND',rounds),('FIRST_INTENT',firstgroups)]:
        for origin in ['ALL','SEED_MOBILE','LATER_FIRST_MOBILE','LATER_FIRST_CORE','REENTRY_MOBILE','REENTRY_CORE']:
            rsel=rr if origin=='ALL' else [r for r in rr if r['origin']==origin]
            metrics.append(dict(**identity,scope=scope,origin=origin,**stats(rsel)))
    reentries=[]
    prev=None
    for rr in rounds:
        if rr['origin']!='SEED_MOBILE':
            reentries.append(dict(**identity,round=rr['round'],origin=rr['origin'],role=rr['first_role'],signal=rr['signal'],opened=rr['opened'],previous_flat=prev,first_order=rr['first_group'],net=rr['net'],status=rr['status']))
        prev=rr['closed']
    summary=dict(**identity,seed_status=seedrow['status'],ending_NAV=daily[-1]['nav'],marked_net=dec(daily[-1]['nav'])-dec(c['seed_nav']),
        ending_qty=qty,ending_unpaid_dividend=divtotal-paidtotal,holding_closes=sum(d['qty']>0 for d in bridge),
        unknown_holding_closes=sum(d['unknown_today_price'] for d in bridge),ending_pending_exit=sid in daily[-1]['pending_sells'],
        checks=dict(checks),diagnostics=diagnostics,**stats(rounds))
    return dict(summary=summary,seed=seedrow,rounds=rounds,first_intents=firstgroups,metrics=metrics,reentries=reentries,bridge=bridge)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,default=ROOT/'run');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    assert a.out.resolve().parent==Path(__file__).resolve().parent
    assert not a.out.exists()
    done=read(a.run/'DONE.json');assert done['passed'] and done['paths']==28
    outputs=read(a.run/'OUTPUT_HASHES.json')
    for p,h in outputs.items():assert sha(a.run/p)==h,('sealed output changed',p)
    freeze=read(a.run/'SOURCE_FREEZE.json')
    for p,h in freeze.items():assert sha(p)==h,('source changed',p)
    rulespath=next(p for p in freeze if p.endswith('/execution-rules-v2.json'))
    protocolpath=next(p for p in freeze if p.endswith('/economic-protocol.json'))
    rules=read(rulespath);netfactor=dec(read(protocolpath)['dividend_net_factor']['A'])
    original_daily=next(p for p in freeze if '/act_only_ablation_continuous_v1/' in p and p.endswith('/pair/daily.jsonl.gz'))
    nav={}
    with gzip.open(original_daily,'rt') as f:
        for line in f:
            row=json.loads(line)
            if row['account']=='NOACT':nav[day(row['at'])]=dec(row['nav'])
    results=[]
    for caseid in IDS:
        for arm in ARMS:
            p=a.run/f'{caseid}_{arm}'/'PATH.json.gz'
            z=audit_path(p,freeze,rules,netfactor);eq(z['seed']['seed_NAV'],nav[z['seed']['signal'][:10]],'original NOACT seed NAV');results.append(z)
            print('AUDIT_PASS',caseid,arm,z['summary']['checks'],flush=True)
    a.out.mkdir()
    for key in ['summary','seed','rounds','first_intents','metrics','reentries','bridge']:
        rows=[z[key] for z in results] if key in ['summary','seed'] else [r for z in results for r in z[key]]
        emit(a.out/(key.upper()+'.json'),rows);table(a.out/(key.upper()+'.csv'),rows)
    pairs=[]
    for caseid in IDS:
        cp,ip=[r for r in results if r['summary']['case_id']==caseid]
        cs,iss=cp['seed'],ip['seed'];cpflat=cs.get('closed');idays=iss.get('held_dates',[])
        pairs.append(dict(case_id=caseid,name=cs['name'],sid=cs['sid'],CP_seed_status=cs['status'],I_seed_status=iss['status'],
            CP_seed_net=cs['net'],I_seed_net=iss['net'],CP_seed_buy_shares=cs.get('buy_shares',0),I_seed_buy_shares=iss.get('buy_shares',0),
            CP_seed_flat=cpflat,I_seed_flat=iss.get('closed'),
            I_seed_holding_closes_after_CP_flat=sum(d>=day(cpflat) for d in idays) if cpflat else None,
            CP_path_marked_net=cp['summary']['marked_net'],I_path_marked_net=ip['summary']['marked_net'],
            same_case_path_delta=ip['summary']['marked_net']-cp['summary']['marked_net'],
            CP_rounds=cp['summary']['rounds'],I_rounds=ip['summary']['rounds']))
    emit(a.out/'PAIRS.json',pairs);table(a.out/'PAIRS.csv',pairs)
    counts=Counter()
    for z in results:counts.update(z['summary']['checks'])
    emit(a.out/'RESULT.json',dict(passed=True,paths=28,cutoff=END,checks=dict(counts),source_hashes_verified=len(freeze),
        output_hashes_verified=len(outputs),strategy_engines_imported_or_executed=0,account_reruns=0,
        code_sha256=sha(__file__),methodology_sha256=sha(Path(__file__).with_name('METHODOLOGY.md')),
        audit_scope='Independent arithmetic, raw source marks, dated fees, action entitlements, cash/quantity/cost/NAV and complete rounds. Not an independent strategy or eligibility replay.',
        caveats=['Historical outcome selected development cases; no OOS or 35% inference.','No cross-case portfolio return.','Official tradability and historical PIT unavailable.','Accrued dividends need not be paid cash.','Open positive is not a win; last day has no forced liquidation.']))
    emit(a.out/'OUTPUT_HASHES.json',{p.name:sha(p) for p in a.out.iterdir() if p.is_file()})
if __name__=='__main__':main()

