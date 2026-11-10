
import sys,json,gzip,copy,collections
from decimal import Decimal as D
from pathlib import Path
sys.dont_write_bytecode=True
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
sys.path.insert(0,str(R/'account_comparison_continuous_v1/factors'))
from continuous_factors import OpenFactorTimeline
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import FeeComponent,FeeSchedule,QuantityRule
rules=json.load(open(B/'inputs-v2/market-rules.json'));proxies=json.load(open(B/'inputs-v2/economic-protocol.json'))['approved_proxy_ids']
manifest={x['series_id']:x for x in json.load(open('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json'))['series']}
data={}
def loadprice(sid):
    if sid not in data:
        rec=manifest[sid];f=pd.read_parquet(rec['raw']['path'])
        if 'trade_date' in f:f=f.set_index('trade_date')
        elif 'date' in f:f=f.set_index('date')
        f.index=pd.DatetimeIndex(pd.to_datetime(f.index))
        acts=json.load(open(rec['adjustment']['actions']['path']))['events']
        data[sid]=(f,OpenFactorTimeline(f,acts,method=rec['adjustment']['method'],end='2026-05-15'))
    return data[sid]
def op(sid,dt):
    f,_=loadprice(sid);v=f.loc[pd.Timestamp(dt),'open']
    assert pd.notna(v) and v>0,('UNKNOWN_OPEN',sid,dt)
    return D(str(v))
def factor(sid,dt):return loadprice(sid)[1].factor(dt)
def fee(sid,q,p,dt,side):
    ident=market_identity_on(rules,sid,dt,proxies);v=version_on(rules['fee_versions'][ident['venue']],dt,proxies)['schedule'];fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components']))
    return sum(fs.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=D(str(rules['security_metadata'][sid]['par_value']))).values(),D(0)) if q else D(0)
def loads(p):return [json.loads(l) for l in gzip.open(p,'rt')]
def jload(p):return json.load(gzip.open(p,'rt'))
def smal(x):return float(x) if isinstance(x,D) else x
def risk(sid,q,p,s,dt):return max(D(0),q*p+fee(sid,q,p,dt,'buy')-q*s*D('.9995')+fee(sid,q,s*D('.9995'),dt,'sell'))
def ownstate(a,sid,dt):
    live={};H=D(0);R0=D(0)
    tr={t['layer']:t for t in a['trades'] if t['side']=='buy'}
    for j in a['journal']:
        if j.get('sid')!=sid or j['at'][:10]>dt:continue
        if j['at'][:10]==dt and j['kind']!='real_sell_fill':continue
        k=j['kind'];qty=sum(z['q'] for z in live.values())
        if k=='real_buy_fill':
            if qty==0:live={};H=D(0);t=tr[j['layer']];R0=risk(sid,j['shares'],D(j['price']),D(t['floor'])/factor(sid,j['at'][:10]),j['at'][:10])
            live[j['layer']]=dict(q=j['shares'],cost=j['shares']*D(j['price'])+D(j['fees']),added=qty>0)
        elif k=='real_sell_fill':
            for part in j['parts']:
                z=live[part['layer']];ret=z['cost']*D(part['shares'])/z['q'];rp=D(part['net_cash'])-ret
                if z['added']:H+=max(D(0),-rp)
                z['q']-=part['shares'];z['cost']-=ret
        elif k=='actual_split' and qty:raise AssertionError('split not covered')
    return live,H,R0
def check(arm,run,sid,days):
    a=jload(run/'pair/PVR.json.gz');daily=loads(run/'pair/daily.jsonl.gz');fund=loads(run/'pair/funding.jsonl.gz');cash=loads(run/'OPEN_CASH_CHECKS.jsonl.gz');events=loads(run/'pair/industry.jsonl.gz');gate=loads(run/'PROFIT_GATE_EVENTS.jsonl.gz')
    gc=loads(run/'GROWTH_CANDIDATES.jsonl.gz') if (run/'GROWTH_CANDIDATES.jsonl.gz').exists() else []
    audits={x['order_id']:x for x in a['audit'] if x['kind']=='reserve'}
    for dt in days:
        prev=[x for x in daily if x['at'][:10]<dt][-1];ds=prev['at'][:10]
        intent=next(i for de in a['decisions'] if de['at'][:10]==ds for i in de['intents'] if i['sid']==sid and i['role']=='mobile')
        dayfund=[x for x in fund if x['at'][:10]==dt and '09:30' in x['at']]
        target=next(x for x in dayfund if x['sid']==sid and x['role']=='mobile');idx=dayfund.index(target)
        pre_res=[x for x in dayfund[:idx] if x['result']=='reserved']
        lots=copy.deepcopy(prev['layers']);byid={z['id']:z for z in lots}
        dayj=[x for x in a['journal'] if x['at'][:10]==dt]
        for j in dayj:
            if j['kind']=='real_sell_fill':
                for part in j['parts']:byid[part['layer']]['qty']-=part['shares']
            assert j['kind']!='actual_split'
        lots=[z for z in lots if z['qty']]
        marks={z['sid']:op(z['sid'],dt) for z in lots}
        for z in lots:z['raw_floor']=D(str(z['last_core_line'] if z['kind']=='core' else z['floor']))/factor(z['sid'],dt)
        inv=sum(z['qty']*marks[z['sid']] for z in lots)
        cash0=D(next(x for x in cash if x['at'][:10]==dt)['available_before'])
        sold=sum(sum(D(p['net_cash']) for p in j['parts']) for j in dayj if j['kind']=='real_sell_fill')
        startcash=cash0+sold
        assert D(prev['sale_receivable'])==0
        nav=startcash+inv+D(prev['dividend_receivable'])
        orders=[]
        for f in pre_res:
            j=next(x for x in dayj if x['kind']=='real_reserve' and x['sid']==f['sid'])
            z=copy.deepcopy(a['budget']['orders'][j['budget_order']]);au=audits[j['order']]
            z.update(qty=j['shares'],cap=D(au['gross_budget_cny']),fee=D(au['fee_reserved_cny']))
            orders.append(z)
        pcash=sum(z['cap']+z['fee'] for z in orders);pf=sum(z['fee'] for z in orders)
        available=startcash-pcash
        own,H,R0=ownstate(a,sid,dt);Q=sum(z['q'] for z in own.values());K=sum(z['cost'] for z in own.values())
        O=op(sid,dt);p=O*D('1.0005');S=D(intent['floor'])/factor(sid,dt)
        sec=next(z['sector'] for z in lots if z['sid']==sid)
        sev=[x for x in events if x['sector']==sec and x['day']<=ds][-1];lev=sev['financial_level'];att=sev['attempt']
        conf=lev>0 and not any(z['sector']==sec and z['pool']=='probe' and z['attempt']==att for z in orders)
        sc=sum(z['qty']*marks[z['sid']] for z in lots if z['sector']==sec)+sum(z['cap'] for z in orders if z['sector']==sec)
        sr=sum(z['qty']*max(D(0),marks[z['sid']]-z['raw_floor']) for z in lots if z['sector']==sec)+sum(z['qty']*max(D(0),D(str(z['limit']))-D(str(z['floor']))) for z in orders if z['sector']==sec)
        L=sum(max(D(0),own[z['id']]['cost']-z['qty']*z['raw_floor']*D('.9995')+fee(sid,z['qty'],z['raw_floor']*D('.9995'),dt,'sell')) for z in lots if z['sid']==sid and own[z['id']]['added'])
        U=Q*O*D('.9995')-fee(sid,Q,O*D('.9995'),dt,'sell')-K
        qrule=QuantityRule(**version_on(rules['quantity_versions'][sid],dt,proxies)['rule'])
        maxq=qrule.buy_floor(min(intent['cap'],int(D(intent['budget'])/p)))
        vals=[]
        uavg=next(x for x in gate if x['sid']==sid and x['role']=='mobile' and x['at'][:10]==dt)['net_profit']
        def numbers(q):
            c=q*p+fee(sid,q,p,dt,'buy');up=(Q+q)*O*D('.9995')-fee(sid,Q+q,O*D('.9995'),dt,'sell')-K-c;dn=risk(sid,q,p,S,dt);gnav=nav-pf-fee(sid,q,p,dt,'buy')
            growth=(D(uavg)>0 and U>0 and up>0 and H+L+dn<=D('.25')*R0+up)
            fail=[]
            if c>available-D(prev['nav'])*D('.1'):fail.append('cash')
            if sc+q*p>D(str((.02,.1,.2)[lev] if conf else .02))*gnav:fail.append('sector_capital')
            if sr+q*max(D(0),p-S)>D('.01')*gnav:fail.append('sector_risk')
            if Q*O+q*p>D('.1')*D(prev['nav']):fail.append('stock_capital')
            return dict(q=q,cash=c,risk=dn,post=up,growth=growth,fail=fail)
        vals=[numbers(q) for q in range(qrule.buy_minimum,maxq+1,qrule.buy_step)]
        growmax=max([v['q'] for v in vals if v['growth']]+[0])
        allmax=max([v['q'] for v in vals if v['growth'] and not v['fail']]+[0]) if conf else 'PROBE_NOT_RECONSTRUCTED'
        row=dict(arm=arm,day=dt,sid=sid,Q=Q,R0=R0,H=H,L=L,U=U,U_avg=uavg,maxq=maxq,actual_q=target.get('shares',0),actual_result=target['result'],growth_no_qcap=growmax,combined_no_qcap=allmax,confirmed_available=conf,level=lev,cash_after_reserve=available,free_after_cash_floor=available-D(prev['nav'])*D('.1'),bnav=nav,pending_fees=pf,sector_capital=sc,sector_risk=sr,sector_capital_headroom=D(str((.02,.1,.2)[lev]))*(nav-pf)-sc,sector_risk_headroom=D('.01')*(nav-pf)-sr,prior_orders=len(orders))
        row['native_quantity_without_growth']=max([v['q'] for v in vals if not v['fail']]+[0]) if conf else 'PROBE_NOT_RECONSTRUCTED'
        row['growth_with_qcap']=max([v['q'] for v in vals if v['growth'] and not v['fail'] and v['q']<=Q]+[0]) if conf else None
        if arm=='original' and conf:assert row['native_quantity_without_growth']==target.get('shares',0),(dt,'native_reproduction_failed',row,target)
        if gc:
            g=next(x for x in gc if x['sid']==sid and x['role']=='mobile' and x['at'][:10]==dt)
            for key,v in [('available',available),('native_pending_cash',pcash),('U_layer',U),('R0',R0),('H',H),('L',L)]:assert abs(v-D(g[key]))<D('0.000001'),(arm,dt,key,v,g[key])
            qold=max([v['q'] for v in vals if v['growth'] and not v['fail'] and v['q']<=Q]+[0])
            if conf:assert qold==target.get('shares',0),(dt,'old_qty_mismatch',qold,target)
            row['growth_context_bridge']='PASS'
        print(json.dumps({k:row[k] for k in ['arm','day','sid','Q','actual_q','native_quantity_without_growth','growth_with_qcap','growth_no_qcap','combined_no_qcap']},default=smal),flush=True)
check('growth',R/'actual_account_add_capacity_v1/growth_continuous_78_v1/growth/run','601019.SH',['2023-03-23','2023-03-29','2023-04-04','2023-04-14','2023-04-25','2023-04-27','2023-04-28'])
check('original',R/'actual_account_add_capacity_v1/growth_continuous_78_v1/baseline/run','601019.SH',['2023-03-23','2023-03-29','2023-04-14','2023-04-28'])
check('original',R/'account_comparison_continuous_v1/no_loss_add_v1/run_1200000','601298.SH',['2023-05-05','2023-05-08','2023-05-09'])
