"""Bounded saved-event bookkeeping, not a strategy/Account replay.

Only three already-observed opens are reconstructed. Actual reservations/sells
are imposed, never selected anew. Migration is the unchanged deterministic
resource representation transfer. Quantity probes are local feasibility only.
"""
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
import sys,json,gzip,copy,hashlib,collections,bisect,time
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;Z=D(0)
sys.path.insert(0,str(W/'migration-admission-native-readiness-20261101'))
import native_adapter as N
J=N.J
ROOTS={'SC':W/'q2-normal-continuation-20261031/runs/B_diag/pair',
       'SD':W/'migration-admission-singlepass-economics-20261101/runs/2025_26/pair'}
INPUT={};FF={};STATE={};AMAP={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):INPUT[str(Path(p).resolve())]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
    INPUT[str(Path(p).resolve())]=sha(p)
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
    INPUT[str(Path(p).resolve())]=sha(p)
    with gzip.open(p,'rt') as f:return json.load(f)
def save(name,x):N.IO.write_json(O/name,J.W.canon(x))
META=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
SM={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
for r in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json'):
    p=Path(r['refs']['state']);assert sha(p)==r['output_sha256'][str(p)];INPUT[str(p)]=sha(p)
    q=pd.read_parquet(p);STATE[r['series']]={x['day']:x for x in q.to_dict('records')}
    for x in q.to_dict('records'):
        if x['action']=='probe':AMAP[x['attempt_id']]=f"{x['E0_episode']}:{x['receipt_id']}"

def facts(sid,d):
    if sid not in FF:
        p=Path(SM[sid]['refs']['facts']);assert sha(p)==SM[sid]['output_sha256'][str(p)];INPUT[str(p)]=sha(p)
        FF[sid]=pd.read_parquet(p,columns=['factor','i_target','raw_close'])
    f=FF[sid];ix=f.index.searchsorted(pd.Timestamp(d),side='right')-1
    assert ix>=0,(sid,d,'no as-of source')
    return f.iloc[ix]

def load():
    data={}
    for ref,p in ROOTS.items():
        b=book(p/'B.json.gz');ds=rows(p/'daily.jsonl.gz');fund=rows(p/'funding.jsonl.gz')
        data[ref]=dict(book=b,daily=ds,dates=[x['at'][:10] for x in ds],byday={x['at'][:10]:x for x in ds},
            funding=fund,decisions={x['at'][:10]:x for x in b['decisions']},opps={})
        # Only named stocks and deterministic positive-control stocks.
        keep={'601869.SH','301511.SZ','301489.SZ','688585.SH','603268.SH'}
        for r in rows(p/'opportunities.jsonl.gz'):
            if r['sid'] in keep:data[ref]['opps'][r['sid'],r['day']]=r
    data['SD']['route']=rows(ROOTS['SD']/'SD-route.jsonl.gz')
    return data

def condition(sector,d):
    x=STATE[sector][d];active=bool(x['E0_valid'] and pd.notna(x['attempt_id']) and x['stage']>0)
    return NS(active=active,level=int(x['stage'])-1 if active else 0,attempt=AMAP.get(x['attempt_id']) if active else None,
              market_attempt=x['attempt_id'],stage=x['stage_name'])

def resources(lots,orders,pool=None,sector=None):
    ls=[x for x in lots if (pool is None or x['pool']==pool) and (sector is None or x['sector']==sector)]
    os=[x for x in orders if (pool is None or x['pool']==pool) and (sector is None or x['sector']==sector)]
    cap=sum(x['qty']*x['mark'] for x in ls)+sum(x['qty']*x['price'] for x in os)
    risk=sum(x['qty']*max(0.,x['mark']-x['raw_floor']) for x in ls)+sum(x['qty']*max(0.,x['price']-x['raw_floor']) for x in os)
    reserve=sum(x['gross']+x['fee'] for x in os)
    return cap,risk,reserve

def migrate(lots,orders,sector,st,nav,trace):
    # Exact original semantics; no Account, Contract or strategy is advanced.
    if not st.active or st.level==0:return
    old=[x for x in lots if x['sector']==sector and x['attempt']==st.attempt and x['pool']=='probe']
    pending=[x for x in orders if x['sector']==sector and x['attempt']==st.attempt and x['pool']=='probe']
    required=sum(x['qty']*x['mark'] for x in old);cc=resources(lots,orders,'confirmed')[0]
    remaining=.60*(nav-sum(x['fee'] for x in orders))-cc
    ok=not pending and required<=remaining+1e-9
    trace.append(dict(sector=sector,result=ok,required=required,remaining=remaining,
        pending=[x['sid'] for x in pending],moved=[x['id'] for x in old] if ok else []))
    if ok:
        for x in old:x['pool']='confirmed'

def point(data,ref,d,sid,market):
    a=data[ref];ix=a['dates'].index(d);prev=a['dates'][ix-1];last=a['byday'][prev];b=a['book'];at=J.M.N.iso(d+'T09:30:00+08:00')
    assert D(last['order_reserved'])==0 and all(D(last[k])==0 for k in ['sale_receivable','settlement_locked','payable']),('unhandled overnight accounts',ref,d)
    overnight=[x for x in b['journal'] if x['kind']=='actual_split' and prev<x['at'][:10]<=d]
    assert not overnight,('selected point needs unimplemented split bookkeeping',ref,d,overnight)
    # No fictional sell intent money: only already recorded actual sell fills.
    cash=D(last['available']);raw=copy.deepcopy(last['layers']);byid={x['id']:x for x in raw}
    sells=[t for t in b['trades'] if t['side']=='sell' and t['at'][:10]==d]
    for t in sells:
        cash+=D(t['gross_cny'])-D(t['fees_cny'])
        for part in t['parts']:
            x=byid[part['layer']];x['qty']-=part['shares'];x['cash']=str(D(x['cash'])+D(part['net_cash']));assert x['qty']>=0
    ar=D(last['dividend_receivable'])
    overnight_div=[x['receivable'] for x in b['audit'] if x['kind']=='dividend_accrual' and prev<x['receivable']['ex_at'][:10]<=d]
    assert all(x['paid_at'] is None and x['currency']=='CNY' for x in overnight_div)
    ar+=sum((D(x['net_local']) for x in overnight_div),Z)
    marks=market.marks(at,{x['sid'] for x in raw if x['qty']});lots=[]
    for x in raw:
        if not x['qty']:continue
        fs=facts(x['sid'],d);factor=D(str(fs['factor']));st=condition(x['sector'],prev)
        line=D(str(x['last_core_line'] if x['role']=='core' else x['floor']))
        lots.append(dict(id=x['id'],sid=x['sid'],name=META[x['sid']]['name'],sector=x['sector'],industry=META[x['sid']]['industry'],
            qty=x['qty'],pool=x['pool'],role=x['role'],attempt=x['attempt'],mark=float(marks[x['sid']].cny_price(at)),
            raw_floor=float(line/factor),unit_cost=x['unit_cost'],opened=x['opened'],age_observations=ix-a['dates'].index(x['opened'][:10]),
            current_stage=st.stage,own_attempt_still_current=st.active and x['attempt']==st.attempt,
            I_valid_previous_close=bool(facts(x['sid'],prev)['i_target']),previous_close_pending_sell=x['sid'] in last['pending_sells'],
            economic_net_previous_close=str(D(lastx['cash'])+D(lastx['dividend'])+D(lastx['qty'])*D(str(facts(x['sid'],prev)['raw_close'])))
                if (lastx:=next(z for z in last['layers'] if z['id']==x['id'])) else None))
    nav=float(cash+ar)+sum(x['qty']*x['mark'] for x in lots);decision_nav=D(last['nav']);orders=[];migration=[]
    source=a['decisions'][prev];intents={(x['sid'],x['role']):x for x in source['intents']}
    audit={x['order_id']:x for x in b['audit'] if x['kind']=='reserve'}
    actual={ (x['sid'],x['role']):x for x in b['journal'] if x['kind']=='real_reserve' and x['at'][:10]==d }
    fund=[x for x in a['funding'] if x['at'][:10]==d and '09:30:00' in x['at']]
    target=None;anchors=[];seen_reserve=[]
    for ev in fund:
        key=ev['sid'],ev['role'];i=intents.get(key)
        if i is None:continue
        sector=META[ev['sid']]['sector_id'];st=condition(sector,prev)
        if ref=='SD':
            anchor=next((x for x in data['SD']['route'] if x['at'][:10]==d and x['sid']==ev['sid'] and x['role']==ev['role']),None)
            if anchor and anchor['resource_when_probe_or_pool_blocked']:
                x=anchor['resource_when_probe_or_pool_blocked'];pc=resources(lots,orders,'probe');cc=resources(lots,orders,'confirmed')
                gaps=dict(probe_capital=pc[0]-x['probe'][0],probe_risk=pc[1]-x['probe'][1],confirmed_capital=cc[0]-x['confirmed'][0],confirmed_risk=cc[1]-x['confirmed'][1],NAV=nav-x['budget_NAV'],cash=float(cash)-float(x['available']))
                assert all(abs(v)<1e-6 for v in gaps.values()),('saved SD anchor mismatch',d,ev,gaps)
                anchors.append(dict(sid=ev['sid'],role=ev['role'],gaps=gaps))
        if ev['role']=='mobile' and st.active and st.level>0 and ev['result'] not in ('missing_open','open_minimum_exceeds_frozen_contract','open_at_or_below_protection','no_fresh_stock_CP1','industry_invalidated'):
            migrate(lots,orders,sector,st,nav,migration)
        if ev['sid']==sid and ev['role']=='mobile':
            factor=D(str(facts(sid,d)['factor']));it=copy.deepcopy(i)
            for k in ['floor','budget','risk_budget']:
                if k in it:it[k]=D(str(it[k]))
            it['quote']=NS(par_value=market.quote(sid,J.M.N.iso(prev+'T15:10:00+08:00')).par_value)
            op=D(str(market.raw[sid].loc[pd.Timestamp(d),'open']));x,why=J.LR.preview(it,op,factor,market.quantity(sid,at),market.fees(sid,at));assert not why
            p=float(x['price']);floor=float(x['floor']);fees=sum(o['fee'] for o in orders)
            def allowed(q,pool):
                fee=float(J.LR.fees(q,x['price'],x['schedule'],'buy',it['quote'].par_value));bn=nav-fees-fee;cap=q*p;risk=q*max(0.,p-floor)
                pc,pr,reserve=resources(lots,orders,pool);sc,sr,_=resources(lots,orders,sector=sector);fail=[]
                if cap+fee>min(float(cash-decision_nav*D('.1')),float(cash)+resources(lots,orders)[2]-resources(lots,orders)[2])+1e-9:fail.append('cash_or_original_reserve')
                if pc+cap>(.1 if pool=='probe' else .6)*bn+1e-9:fail.append('pool_capital')
                if pool=='probe' and pr+risk>.005*bn+1e-9:fail.append('probe_risk')
                if sc+cap>(.02 if pool=='probe' else (.02,.1,.2)[st.level])*bn+1e-9:fail.append('sector_capital')
                if sr+risk>.01*bn+1e-9:fail.append('sector_risk')
                held=sum(z['qty'] for z in lots if z['sid']==sid)*float(op)
                if held+cap>.10*float(decision_nav)+1e-9:fail.append('stock_capital')
                return fail
            selected=actual.get(key);qs=sorted(set([x['minq'],x['maxq']]+([selected['shares']] if selected else [])))
            probe_checks=[]
            for q in qs:
                fee=float(J.LR.fees(q,x['price'],x['schedule'],'buy',it['quote'].par_value))
                effective_nav=nav-fees-fee
                probe_checks.append(dict(quantity=q,probe=allowed(q,'probe'),confirmed=allowed(q,'confirmed'),
                    gross=q*p,new_nominal_risk=q*max(0.,p-floor),fee=fee,effective_budget_NAV=effective_nav,
                    remaining_industry_risk=.01*effective_nav-resources(lots,orders,sector=sector)[1],
                    remaining_confirmed_capital=.60*effective_nav-resources(lots,orders,'confirmed')[0],
                    remaining_probe_risk=.005*effective_nav-resources(lots,orders,'probe')[1]))
            for z in lots:
                z['capital']=z['qty']*z['mark'];z['nominal_risk']=z['qty']*max(0.,z['mark']-z['raw_floor'])
            target=dict(reference=ref,day=d,previous=prev,sid=sid,market_open=str(op),price=str(x['price']),floor=str(x['floor']),original_maxq=x['maxq'],minimum=x['minq'],
                signal=i,stage=vars(st),ACT_on=last['on'],decision_NAV=str(decision_nav),opening_live_NAV=nav,cash_available=str(cash),
                probe=resources(lots,orders,'probe'),confirmed=resources(lots,orders,'confirmed'),industry=resources(lots,orders,sector=sector),
                full_or_minimum_checks=probe_checks,actual_reserved=selected,lots=copy.deepcopy(lots),earlier_open_reservations=copy.deepcopy(orders),migration=copy.deepcopy(migration),
                local_quantity_checks_are_feasibility_not_executable_counterfactual_PnL=True)
        if ev['result']=='reserved':
            real=actual[key];rs=audit[real['order']];q=real['shares'];p=float(real['price']);floor=float(D(str(i['floor']))/D(str(facts(ev['sid'],d)['factor'])))
            if real['pool']=='confirmed':migrate(lots,orders,sector,st,nav,migration)
            order=dict(sid=ev['sid'],name=META[ev['sid']]['name'],sector=sector,industry=META[ev['sid']]['industry'],qty=q,price=p,raw_floor=floor,
                pool=real['pool'],role=real['role'],attempt=st.attempt,capital=q*p,gross=float(rs['gross_budget_cny']),fee=float(rs['fee_reserved_cny']),
                nominal_risk=q*max(0.,p-floor),budget_order=real['budget_order'],receipt=real.get('receipt'),priority_index=len(seen_reserve))
            orders.append(order);cash-=D(rs['gross_budget_cny'])+D(rs['fee_reserved_cny']);seen_reserve.append(key)
    assert target is not None,('no actual mobile route at requested point',ref,d,sid)
    target['SD_full_batch_scalar_anchor_checks']=anchors
    target['point_is_exact_resource_projection_not_full_Account_restore']=True
    return target

def main():
    begun=time.monotonic();data=load();configs=[('2025-09-01','601869.SH'),('2025-12-19','601869.SH'),('2026-04-22','301511.SZ')]
    ids=set()
    for d,sid in configs:
        for a in data.values():
            prev=a['dates'][a['dates'].index(d)-1];ids.update(x['sid'] for x in a['byday'][prev]['layers'])
        ids.add(sid)
    # Original market-only price/rule access: no Account, Contract or runner.
    _,market,_=J.M.context('2026-06-30',ids=sorted(ids))
    results=[]
    for d,sid in configs:
        for ref in ('SC','SD'):
            try:
                r=point(data,ref,d,sid,market);save(Path('points')/(d+'_'+sid+'_'+ref+'.json'),r)
                results.append(dict(day=d,sid=sid,reference=ref,known=True,actual_quantity=(r['actual_reserved'] or {}).get('shares',0),maxq=r['original_maxq'],checks=r['full_or_minimum_checks'],anchor_checks=len(r['SD_full_batch_scalar_anchor_checks'])))
            except AssertionError as e:
                save(Path('points')/(d+'_'+sid+'_'+ref+'_UNKNOWN.json'),dict(reason=str(e),no_approximation_used=True));results.append(dict(day=d,sid=sid,reference=ref,known=False,reason=str(e)))
    save('POINT_READINESS.json',dict(points=results,seconds=time.monotonic()-begun,no_account_or_strategy_replay=True,no_alternative_planner_run=True))
    assert all(sha(p)==h for p,h in INPUT.items());save('SOURCE_INPUT_HASHES.json',INPUT)
    print('POINTS',json.dumps(results,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
