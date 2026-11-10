"""Independent benchmark input/signal/fill/equity audit. No engine import."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict
import hashlib,json,math,re
import numpy as np,pandas as pd
getcontext().prec=60
HERE=Path(__file__).parent;R=HERE.parent/'benchmark_2022_2023'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
inp=read(R/'INPUT_FREEZE.json');run=read(R/'RUN_FREEZE.json')
assert inp['before_benchmark_account_computation']and run['before_account_computation']
for p,h in {**inp['sources'],**inp['inputs'],**run['sources']}.items():assert sha(p)==h
h=pd.read_csv(R/'inputs/510300_history.csv',index_col='date',parse_dates=True)
cal=pd.read_csv(R/'inputs/calendar.csv').date.tolist();assert len(cal)==len(set(cal))==484
assert cal[0]=='2022-01-04'and cal[-1]=='2023-12-29'
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
assert sorted(parsed)==sorted((e['ex_date'],e['pay_date'],D(str(e['amount'])))for e in actions['dividends'])
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
pub=read(R/'RESULTS.json')['results'];out={};data={};allfills=0
def fee(g):return max(D(5),g*D('.0015'))if g else D(0)
def eq(a,b,where):assert abs(D(str(a))-D(str(b)))<D('1e-8'),(where,a,b)
for policy in ['BUY_HOLD','MA63_90']:
    ds=pd.read_csv(R/'daily'/(policy+'.csv'),dtype=str);assert ds.date.tolist()==cal
    fills=read(R/'logs'/(policy+'_fills.json'));assert len({f['order']for f in fills})==len(fills),'observed full-fill-only scope'
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
        nav_byday[day]=nav;peak=max(peak,nav);dd=max(dd,1-nav/peak)
    eq(nav,pub[policy]['terminal_NAV'],'terminal');eq(cumulative_fee,pub[policy]['fees'],'fees');eq(dd*100,pub[policy]['max_DD_pct'],'DD')
    out[policy]=dict(passed=True,return_pct=(nav/D(1000000)-1)*100,close_DD_pct=dd*100,fees=cumulative_fee,accrued=accrued_all,paid=paid_all,actual_full_fills=len(fills),execution_verified=False)
    data[policy]=nav_byday;allfills+=len(fills)
assert allfills==23
index=pd.read_csv(R/'inputs/HS300_daily.csv');assert index.date.tolist()==cal
source=pd.read_csv(next(p for p in inp['sources']if p.endswith('canonical/USZI399300.csv'))).set_index('date')
assert np.max(np.abs(index.close.to_numpy()-source.loc[cal].close.to_numpy()))<1e-8
units=D(1000000)/D(str(index.iloc[1].open));ds=pd.read_csv(R/'daily/HS300_PRICE_INDEX.csv',dtype=str)
for k,d in ds.iterrows():eq(D(1000000)if k==0 else units*D(str(index.iloc[k].close)),d.NAV,'index reference, not executable')
out.update(status='PASS_WITH_SCOPE',source_and_input_SHA_checks=len({**inp['sources'],**inp['inputs'],**run['sources']}),
    sequential_total_return_and_inclusive_MA63_full1327_warm_rows_exact=True,strict_prior20_ADV_and_hands_to_shares_exact=True,
    ex_pay_amounts_independently_parsed=True,all484_calendar_closes_and23_nextsessionOPEN_fills_verified=True,
    reviewer_account_events=0,reviewer_source_SHA256=sha(__file__),
    scope='Two independently audited ETF proxy benchmarks with actual ex/payment cash timing and one modeled15bp/min5 friction. Missing historical dated halt/limit/auction files means execution_verified=false remains. HS300 is a non-tradable price reference, MA63 is frozen diagnostic, neither is a promoted strategy or proof that cash/less exposure solves stock strategy loss. Net+cumulativecost is same-quantity bridge, not full no-cost feedback counterfactual.')
(HERE/'BENCHMARK_2022_2023_INDEPENDENT_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
print(json.dumps(out,indent=2,default=str))
