"""Independent fixed-order resource replay from JSON. No native imports/events."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import json,hashlib,copy,sys
getcontext().prec=60
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent/'pvr_pool_feasibility';Z=D(0);EPS=D('0.000001')
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eq(a,b,label):assert abs(D(str(a))-D(str(b)))<EPS,(label,str(a),str(b))
def fee(schedule,q,price,par):
    v=Z
    for c in schedule['components']:
        if c.get('side','buy')=='sell':continue
        base=D(q)*D(par) if c.get('amount_basis')=='par_value' else D(q)*price
        # All actual selected schedules use an uncapped minimum plus proportional rate.
        assert c.get('maximum_local') is None and c.get('rounding_unit') is None
        v+=max(base*D(c['rate']),D(c.get('minimum_local','0')))
    return v
def resources(s,pool=None,sector=None):
    cap=risk=reserve=Z
    for l in s['lots']:
        if (pool is not None and l['pool']!=pool) or (sector is not None and l['sector']!=sector):continue
        p=D(str(s['prices'][l['stock']]));q=D(str(l['qty']));cap+=p*q;risk+=q*max(Z,p-D(str(l['floor'])))
    for o in s['orders'].values():
        if o['status'] not in ['open','cancel_pending'] or o['qty']<=0:continue
        if (pool is not None and o['pool']!=pool) or (sector is not None and o['sector']!=sector):continue
        q=D(str(o['qty']));p=D(str(o['limit']));f=D(str(o['fee_per_share']))
        cap+=q*p;risk+=q*max(Z,p-D(str(o['floor'])));reserve+=q*(p+f)
    return cap,risk,reserve
def check(case):
    folder=ROOT/case;x=load(folder/'INPUT_VIEW.json');s0=x['state'];summary=load(folder/'SUMMARY.json');freeze=load(folder/'RESTORE_FREEZE.json')
    assert load(folder/'COMPLETION.json')['passed'] and load(folder/'RESTORE_IDENTITY.json')['passed'] and load(folder/'OFF_IDENTITY.json')['passed']
    assert len(x['intents'])==summary['case']['intents'] and len({i['sid'] for i in x['intents']})==summary['case']['stocks']
    for p,h in freeze['source_freeze'].items():assert sha(p)==h,p
    for p,h in freeze['diagnostic_sources'].items():assert sha(p)==h,p
    assert sha(freeze['checkpoint'])==freeze['checkpoint_sha256']
    # Native post-admission fields were captured before the execution loop.
    off=load(folder/'OFF.json');on=load(folder/'ON.json');post=load(folder/'NATIVE_POST_ADMISSION.json')
    for k in ['cash','nav','receivables','lots','orders','sectors','prices','consumed','stock_requests','historical_shared_loss','core_epoch']:assert off['final_state'][k]==post[k],k
    assert D(off['available'])==D(post['available_exact'])
    results={}
    for name,result,relax in [('OFF',off,False),('ON',on,True)]:
        s=copy.deepcopy(s0);available=D(s['available_exact']);decision=D(s['decision_nav']);old_orders=copy.deepcopy(s['orders']);held=defaultdict(lambda:Z)
        for l in s['lots']:held[l['stock']]+=D(str(l['qty']))
        nav=D(str(s['cash']))+D(str(s['receivables']))+sum((D(str(l['qty']))*D(str(s['prices'][l['stock']])) for l in s['lots']),Z)
        eq(nav,s['nav'],'S0 budget NAV')
        by={(i['sid'],i['role']):i for i in x['intents']};orders={r['key']:r for r in result['orders']};assert len(orders)==len(result['orders'])
        migration=defaultdict(list)
        for m in result['migrations']:migration[m['candidate']].append(m)
        rows=[];accepted=[];done=set();consumed=set(s['consumed']);requests=set(s['stock_requests']);seen_keys=[]
        expected_order=sorted(x['intents'],key=lambda i:(i['rank'],i['role']!='core'))
        assert [(r['sid'],r['role']) for r in result['attempts']]==[(i['sid'],i['role']) for i in expected_order]
        for attempt in result['attempts']:
            sid,role=attempt['sid'],attempt['role'];i=by[sid,role];key='B|'+i['clock']['decision_at']+'|'+sid+'|'+role
            if attempt.get('skip'):
                assert sid in done or sid in s0['pending_sells'] or any(o['stock']==sid and o['qty']>0 and o['status'] in ['open','cancel_pending'] for o in old_orders.values())
                assert key not in orders;continue
            sec=s['sector_by_sid'][sid];sector=s['sectors'][sec]
            # Apply the actual recorded native migration sequence; independently check
            # its pending/cap conditions and that it never releases total resources.
            for m in migration[key]:
                assert m['sector']==sec and m['old_status']==sector['status']
                pending=any(o['sector']==sec and o['attempt']==sector['attempt'] and o['pool']=='probe' and o['qty']>0 and o['status'] in ['open','cancel_pending'] for o in s['orders'].values())
                candidates=[l for l in s['lots'] if l['sector']==sec and l['attempt']==sector['attempt'] and l['pool']=='probe']
                moved=sum((D(str(l['qty']))*D(str(s['prices'][l['stock']])) for l in candidates),Z)
                pendingfees=sum((D(str(o['qty']))*D(str(o['fee_per_share'])) for o in s['orders'].values() if o['status'] in ['open','cancel_pending']),Z)
                legal=sector['active'] and sector['level']>0 and not pending and (relax or resources(s,'confirmed')[0]+moved<=D('.6')*(nav-pendingfees)+EPS)
                assert bool(m['result'])==bool(legal),(name,key,'migration condition')
                before=resources(s)
                if legal:
                    assert sorted(m['moved'])==sorted(l['batch'] for l in candidates)
                    for l in candidates:l['pool']='confirmed'
                else:assert not m['moved']
                assert before==resources(s)
                sector['status']=m['new_status']
            if attempt['result']!='reserved':assert key not in orders;continue
            o=orders[key];seen_keys.append(key);p=i['preview'];q=o['quantity'];price=D(p['price']);floor=D(p['floor']);rule=p['rule'];gross=D(q)*price
            assert q>0 and q>=rule['buy_minimum'] and (q-rule['buy_minimum'])%rule['buy_step']==0 and q<=p['maxq'] and q<=i['cap']
            assert gross<=D(i['budget']) and o['role']==role and sid==o['sid'] and o['rank']==i['rank']
            assert key not in requests and sector['active']
            if role=='mobile':assert o['CP1_id']==i['CP1_id'] and i['CP1_id'] not in consumed;consumed.add(i['CP1_id'])
            else:assert o['pool']=='probe' and i['epoch']!=s['core_epoch'].get(sid)
            f=fee(p['schedule'],q,price,i['quote']['par_value']);eq(f,o['fee'],'exact selected fee')
            pendingfees=sum((D(str(v['qty']))*D(str(v['fee_per_share'])) for v in s['orders'].values() if v['status'] in ['open','cancel_pending']),Z)
            budgetnav=nav-pendingfees-f;cap,risk,reserve=resources(s);pc,pr,_=resources(s,o['pool']);sc,sr,_=resources(s,sector=sec);newrisk=D(q)*max(Z,price-floor)
            margin=dict(cash_original=available-decision*D('.1')-gross-f,cash_budget=D(str(s['cash']))-reserve-gross-f,
                sector_capital=(D('.02') if o['pool']=='probe' else [D('.02'),D('.1'),D('.2')][sector['level']])*budgetnav-sc-gross,
                sector_risk=D('.01')*budgetnav-sr-newrisk,
                stock_capital=D('.1')*decision-held[sid]*D(p['known_open'])-gross)
            if o['pool']=='probe':margin.update(probe_capital=D('.1')*budgetnav-pc-gross,probe_risk=D('.005')*budgetnav-pr-newrisk)
            elif not relax:margin['confirmed60']=D('.6')*budgetnav-pc-gross
            assert all(v>=-EPS for v in margin.values()),(name,key,margin)
            native=result['final_state']['orders'][key];assert native['stock']==sid and native['pool']==o['pool'] and native['role']==role and native['qty']==q
            eq(native['limit'],price,'native order price');eq(native['floor'],floor,'native order floor');eq(D(str(native['fee_per_share']))*q,f,'native order fee')
            s['orders'][key]=copy.deepcopy(native);available-=gross+f;requests.add(key);done.add(sid);accepted.append(o)
            rows.append(dict(key=key,quantity=q,pool=o['pool'],margins=margin))
        assert seen_keys==[o['key'] for o in result['orders']]
        assert consumed==set(result['final_state']['consumed']) and requests==set(result['final_state']['stock_requests'])
        for k in ['lots','orders','sectors']:assert s[k]==result['final_state'][k],(name,k)
        c,r,v=resources(s);eq(c,result['capital'],'terminal capital');eq(r,result['nominal_risk'],'terminal risk');eq(v,result['cash_reserve'],'terminal reserve');eq(available,result['available'],'terminal spendable')
        eq(sum((D(o['fee']) for o in accepted),Z),result['fees'],'fee sum')
        assert result['inputs_unchanged'] and result['native_Account_initializations']==result['real_fills']==result['new_financial_paths']==0
        results[name]=dict(orders=len(accepted),semiconductor_orders=sum(s['sector_by_sid'][o['sid']]=='URFI881121' for o in accepted),capital=c,risk=r,reserve=v,available=available,fees=D(result['fees']),fixed_order_constraints_independently_checked=len(rows),checks=rows)
    delta={k:results['ON'][k]-results['OFF'][k] for k in ['capital','risk','reserve','available','fees']}
    for k,field in [('capital','capital_delta'),('risk','nominal_risk_delta'),('reserve','reserved_cash_delta'),('available','available_cash_delta'),('fees','fee_delta')]:eq(delta[k],summary[field],field)
    source={str(p):sha(p) for p in folder.iterdir() if p.is_file() and p.suffix=='.json'}
    out=dict(status='PASS_WITH_SCOPE',case=case,full_intents=len(x['intents']),full_stocks=len({i['sid'] for i in x['intents']}),original_replay_identity=load(folder/'RESTORE_IDENTITY.json'),results=results,deltas=delta,
        NAV_clock_note='decision_nav is sampled native a.current_nav at OPEN but retains prior decision CLOSE value; budget.nav is current marked NAV. Original differing consumers preserved.',
        cash_view_note='final_state.available_exact is the S0 anchor; top-level available is post-plan actual spendable.',
        scope='independent pure JSON fixed-quantity/resource replay and source hashes, not native engine replay, proof of global quantity optimality, fills, PnL or economic promotion',account_events_by_audit=0,source_sha256=source)
    (HERE/('PVR_'+case+'_EXACT_AUDIT.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps(dict(case=case,status=out['status'],full_intents=out['full_intents'],counts={k:{a:b for a,b in v.items() if a!='checks'}for k,v in results.items()},deltas=delta),ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':
    for case in sys.argv[1:]:check(case)
