"""Independent benchmark input/signal/fill/equity audit. No engine import."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict
import hashlib,json,math,re
import numpy as np,pandas as pd
getcontext().prec=60
HERE=Path(__file__).parent;R=HERE.parent/'benchmark_2022_2023/continuation2024'
OLD=R.parent
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
inp=read(R/'INPUT_AVAILABILITY.json');run=read(R/'RUN_FREEZE.json')
assert inp['before_new_account_events']and run['before_account_events']
for p,h in {**inp['sources'],**inp['inputs'],**run['sources']}.items():assert sha(p)==h
h=pd.read_csv(R/'inputs/510300_history.csv',index_col='date',parse_dates=True)
cal=pd.read_csv(OLD/'inputs/calendar.csv').date.tolist()+pd.read_csv(R/'inputs/calendar2024.csv').date.tolist();assert len(cal)==len(set(cal))==726
assert cal[0]=='2022-01-04'and cal[-1]=='2024-12-31'
actions=read(R/'inputs/510300_actions.json');assert actions['splits']==[]
rawpath=next(p for p in inp['sources']if p.endswith('tencent-sh510300-raw.json'))
raw=read(rawpath)['data']['sh510300']['day'];raw={r[0]:r for r in raw}
for d,r in h.iterrows():
    q=raw[str(d.date())]
    for col,index in [('open',1),('close',2),('high',3),('low',4),('volume',5)]:assert abs(float(r[col])-float(q[index]))<1e-12
    assert r.volume_shares==r.volume*100
html=next(p for p in inp['sources']if p.endswith('eastmoney-fhsp-510300.html'))
parsed=[]
for table in pd.read_html(html):
    if '除息日'not in table:continue
    for _,r in table.iterrows():
        if '暂无'in str(r['除息日']):continue
        date=str(pd.Timestamp(r['除息日']).date())
        if str(h.index[0].date())<=date<=str(h.index[-1].date()):
            amount=D(re.fullmatch(r'每10份派现金([0-9.]+)元',str(r['每10份分红']))[1])/10
            parsed.append((date,str(r['分红发放日']),amount))
expected_div=sorted((e['ex_date'],e['pay_date'],D(str(e['amount'])))for e in actions['dividends']);assert len(parsed)==len(expected_div)
for a,b in zip(sorted(parsed),expected_div):assert a[:2]==b[:2]and abs(a[2]-b[2])<D('1e-15')
div={e['ex_date']:e for e in actions['dividends']};assert len(div)==len(actions['dividends'])
# Sequential raw total-return construction never looks beyond today's ex action.
tr=[];last=None;last_raw=None
for date,row in h.iterrows():
    cl=float(row.close);amount=float(div.get(str(date.date()),{}).get('amount',0))
    last=cl if last is None else last*(cl+amount)/last_raw;tr.append(last);last_raw=cl
tr=pd.Series(tr,index=h.index);ma=tr.rolling(63,min_periods=63).mean();on=tr.gt(ma)&ma.notna()
assert np.max(np.abs(tr-h.signal_close))<1e-10
assert np.nanmax(np.abs(ma-h.ma63))<1e-10 and on.equals(h['on'])
adv=(h.volume*100).shift().rolling(20,min_periods=20).mean()
assert np.nanmax(np.abs(adv-h.adv20_prior_shares))<1e-6
puball=read(R/'RESULTS_2024.json')['results'];pub={k:v['cumulative2022_2024']for k,v in puball.items()};out={};data={};allfills=0
def fee(g):return max(D(5),g*D('.0015'))if g else D(0)
def eq(a,b,where):assert abs(D(str(a))-D(str(b)))<D('1e-8'),(where,a,b)
for policy in ['BUY_HOLD','MA63_90']:
    ds=pd.read_csv(R/'daily_2022_2024'/(policy+'.csv'),dtype=str);assert ds.date.tolist()==cal
    fills=read(R/'logs_2022_2024'/(policy+'_fills.json'));assert len({f['order']for f in fills})==len(fills),'observed full-fill-only scope'
    byday={f['day']:f for f in fills};assert len(byday)==len(fills)
    expected=[];prior=False
    for k,d in enumerate(cal):
        state=bool(on.loc[d]);side=None
        if policy=='BUY_HOLD'and k==0:side='buy'
        if policy=='MA63_90'and state!=prior:side='buy'if state else'sell'
        if side and k+1<len(cal):expected.append((d,cal[k+1],side))
        prior=state
    assert [(f['signal_day'],f['day'],f['side'])for f in fills]==expected
    cash=D(1000000);q=0;claims=[];lots=[];cumulative_fee=D(0);peak=D(1000000);dd=D(0);nav_byday={};paid_all=D(0);accrued_all=D(0)
    for _,d in ds.iterrows():
        day=d.date;bar=h.loc[day];accrued=paid=D(0)
        if day in div:
            amount=D(str(div[day]['amount']))*q
            if amount:claims.append(dict(amount=amount,pay=div[day]['pay_date']));accrued+=amount
        keep=[]
        for c in claims:
            if c['pay']<=day:cash+=c['amount'];paid+=c['amount']
            else:keep.append(c)
        claims=keep;paid_all+=paid;accrued_all+=accrued
        f=byday.get(day);todayfee=D(0)
        if f:
            shares=f['quantity'];price=D(str(bar.open));assert price==D(f['price'])==D(f['raw_open'])and shares%100==0
            assert shares<=int(D(str(adv.loc[day]))*D('.01'))//100*100
            gross=D(shares)*price;todayfee=fee(gross);eq(gross,f['gross'],'fill gross');eq(todayfee,f['fee'],'single friction')
            if f['side']=='buy':
                budget=nav_byday[f['signal_day']]*(D('.9')if policy=='MA63_90'else D(1));spend=min(cash,budget)
                assert gross+todayfee<=spend and (D(shares+100)*price+fee(D(shares+100)*price))>spend
                cash-=gross+todayfee;q+=shares;lots.append([day,shares])
            else:
                assert shares==q and sum(v for t,v in lots if t<day)>=shares
                cash+=gross-todayfee;q-=shares;left=shares
                for lot in lots:
                    if lot[0]<day:z=min(left,lot[1]);lot[1]-=z;left-=z
                assert left==0
            cumulative_fee+=todayfee
        ar=sum((c['amount']for c in claims),D(0));nav=cash+D(q)*D(str(bar.close))+ar
        eq(cash,d.cash,'daily cash');assert q==int(d.shares);eq(ar,d.dividend_receivable,'daily claim');eq(accrued,d.dividend_accrued,'ex entitlement');eq(paid,d.dividend_paid,'pay timing');eq(todayfee,d.fee,'daily fee')
        eq(nav,d.NAV,'daily equity');eq(nav+cumulative_fee,d.same_quantity_cost_before_NAV,'same quantity cost bridge');assert d.execution_verified=='False'
        nav_byday[day]=nav;peak=max(peak,nav);dd=max(dd,1-nav/peak);eq(1-nav/peak,d.drawdown,'carried global close DD each day')
    eq(nav,pub[policy]['terminal_NAV'],'terminal');eq(cumulative_fee,pub[policy]['fees'],'fees');eq(dd*100,pub[policy]['max_DD_pct'],'DD')
    out[policy]=dict(passed=True,return_pct=(nav/D(1000000)-1)*100,close_DD_pct=dd*100,fees=cumulative_fee,accrued=accrued_all,paid=paid_all,actual_full_fills=len(fills),execution_verified=False)
    data[policy]=nav_byday;allfills+=len(fills)
assert allfills==28
# Exact own-parent and original-history identities; financial726-day reconstruction above is independent.
parent=read(R/'PARENT_STATE.json');proof=read(R/'PARENT_AND_OVERLAP_PROOF.json');assert proof['passed']and proof['body_inverse_exact']
for policy in ['BUY_HOLD','MA63_90']:
    olddaily=pd.read_csv(OLD/'daily'/(policy+'.csv'),dtype=str);full=pd.read_csv(R/'daily_2022_2024'/(policy+'.csv'),dtype=str);tail=full.iloc[484:];a=parent[policy]
    assert (R/'daily_2022_2024'/(policy+'.csv')).read_bytes().startswith((OLD/'daily'/(policy+'.csv')).read_bytes())
    for kind in ['fills','orders','signals']:
        oldlog=read(OLD/'logs'/(policy+'_'+kind+'.json'));assert read(R/'logs_2022_2024'/(policy+'_'+kind+'.json'))[:len(oldlog)]==oldlog
    eq(a['NAV'],olddaily.NAV.iloc[-1],'ownparentNAV');eq(a['cash'],olddaily.cash.iloc[-1],'ownparentcash');assert a['shares']==int(olddaily.shares.iloc[-1])
    eq(a['cumulative_fee'],olddaily.cumulative_fee.iloc[-1],'costcarry');assert a['previous_on']==read(OLD/'logs'/(policy+'_signals.json'))[-1]['on']
    terminal=read(OLD/'logs'/(policy+'_terminal.json'));assert a['lots']==terminal['lots']and a['receivables']==terminal['receivables']and a['pending']==terminal['pending']
    oldorders=read(OLD/'logs'/(policy+'_orders.json'));assert a['orderid']==max(int(x['id'].rsplit('-',1)[1])for x in oldorders if'id'in x)
    peak=max([D(1000000)]+[D(v)for v in olddaily.NAV]);eq(a['global_peak'],peak,'globalpeakcarry')
    p=D(a['NAV']);w=D(0)
    for nav in tail.NAV:p=max(p,D(nav));w=max(w,1-D(nav)/p)
    eq((D(tail.NAV.iloc[-1])/D(a['NAV'])-1)*100,puball[policy]['year2024']['return_pct'],'ownyearreturn');eq(w*100,puball[policy]['year2024']['period_DD_pct'],'ownyearDD')
    out[policy]['ownyear2024']=puball[policy]['year2024']
quarters=pd.read_csv(R/'ALL_12_QUARTERS.csv',dtype=str);assert len(quarters)==24
periods=pd.read_csv(R/'PERIODS_2022_2024.csv',dtype=str);assert len(periods)==102
for _,row in periods.iterrows():
    full=pd.read_csv(R/'daily_2022_2024'/(row.benchmark+'.csv'),dtype=str);lo=row.start;hi=row.end;part=full[full.date.between(lo,hi)];j=int(part.index[0]);begin=D(full.NAV.iloc[j-1])if j else D(1000000)
    eq(begin,row.starting_NAV,'quarterparent');eq(part.NAV.iloc[-1],row.ending_NAV,'quarterend');eq((D(part.NAV.iloc[-1])/begin-1)*100,row.return_pct,'quarterreturn')
    peak=begin;dd=D(0)
    for v in part.NAV:peak=max(peak,D(v));dd=max(dd,1-D(v)/peak)
    eq(dd*100,row.period_DD_pct,'complete calendar period close DD')
phases=pd.read_csv(R/'FIXED_924_PHASES.csv',dtype=str)
for _,row in phases.iterrows():
    full=pd.read_csv(R/'daily_2022_2024'/(row.benchmark+'.csv'),dtype=str);part=full[full.date.between(row.start,row.end)];j=int(part.index[0]);begin=D(full.NAV.iloc[j-1]);eq(begin,row.starting_NAV,'phaseparent');eq(part.NAV.iloc[-1],row.ending_NAV,'phaseend');eq((D(part.NAV.iloc[-1])/begin-1)*100,row.return_pct,'phase return')
# Non-tradable index arithmetic only; shares inherited from existing aligned reference.
oldidx=pd.read_csv(OLD/'daily/HS300_PRICE_INDEX.csv',dtype=str);idx=pd.read_csv(R/'inputs/HS300_2024_daily.csv');dsidx=pd.read_csv(R/'HS300_2024_REFERENCE.csv',dtype=str);units=D(oldidx.synthetic_units.iloc[-1])
assert idx.date.tolist()==dsidx.date.tolist()==cal[484:]
for k,row in dsidx.iterrows():eq(units*D(str(idx.iloc[k].close)),row.NAV,'nontradableindexcontinuation')
out.update(status='PASS_WITH_SCOPE',source_and_input_SHA_checks=len({**inp['sources'],**inp['inputs'],**run['sources']}),
    sequential_total_return_and_inclusive_MA63_full_warm_history_through2024_exact=True,strict_prior20_ADV_and_hands_to_shares_exact=True,
    ex_pay_amounts_independently_parsed=True,all726_calendar_closes_and28_nextsessionOPEN_fills_verified=True, ownstate_parent_and_old484_byte_history_exact=True, all3years_12quarters_36months_each_and_fixed924phase_boundaries_checked=True,
    reviewer_account_events=0,reviewer_source_SHA256=sha(__file__),
    scope='Two independently audited ETF proxy benchmarks with actual ex/payment cash timing and one modeled15bp/min5 friction. Missing historical dated halt/limit/auction files means execution_verified=false remains. HS300 is a non-tradable price reference, MA63 is frozen diagnostic, neither is a promoted strategy or proof that cash/less exposure solves stock strategy loss. Net+cumulativecost is same-quantity bridge, not full no-cost feedback counterfactual.')
(HERE/'BENCHMARK_2024_CONTINUATION_INDEPENDENT_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
print(json.dumps(out,indent=2,default=str))
