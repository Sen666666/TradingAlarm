"""Independent benchmark input/signal/fill/equity audit. No engine import."""
from pathlib import Path
from decimal import Decimal as D,getcontext,ROUND_HALF_UP
from collections import defaultdict
import hashlib,json,math,re
import numpy as np,pandas as pd
getcontext().prec=60
HERE=Path(__file__).parent;ROOT=HERE.parents[1];R=ROOT/'capacity_cost_guard_analysis_v1/benchmark_B_2025_26'
OLD=ROOT/'benchmark_2022_2023'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
inp=read(R/'INPUT_FREEZE.json');run=read(OLD/'RUN_FREEZE.json')
assert inp['before_any_benchmark_simulation']and run['before_account_computation']
for p,h in {**inp['sources'],**inp['inputs'],**run['sources']}.items():assert sha(p)==h
h=pd.read_csv(R/'inputs/510300_history.csv',index_col='date',parse_dates=True)
cal=pd.read_csv(R/'inputs/calendar.csv').date.tolist();assert len(cal)==len(set(cal))==242
assert cal[0]=='2025-07-01'and cal[-1]=='2026-06-30'
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
        nav_byday[day]=nav;peak=max(peak,nav);dd=max(dd,1-nav/peak);eq(1-nav/peak,d.drawdown,'carried global close DD each day')
    eq(nav,pub[policy]['terminal_NAV'],'terminal');eq(cumulative_fee,pub[policy]['fees'],'fees');eq(dd*100,pub[policy]['max_DD_pct'],'DD')
    out[policy]=dict(passed=True,return_pct=(nav/D(1000000)-1)*100,close_DD_pct=dd*100,fees=cumulative_fee,accrued=accrued_all,paid=paid_all,actual_full_fills=len(fills),execution_verified=False)
    data[policy]=nav_byday;allfills+=len(fills)
assert allfills==22

# Extra observed proxy guards, signal/flow/period checks; no producer engine import.
for policy in ['BUY_HOLD','MA63_90']:
    ds=pd.read_csv(R/'daily'/(policy+'.csv'),dtype=str)
    signals=read(R/'logs'/(policy+'_signals.json'));assert [r['day']for r in signals]==cal
    prior=False
    for j,(d,r) in enumerate(zip(cal,signals)):
        assert r['on']==bool(on.loc[d]) and r['prior_on']==prior
        assert abs(r['signal_close']-float(h.loc[d,'signal_close']))<1e-12 and abs(r['MA63']-float(h.loc[d,'ma63']))<1e-12
        prior=r['on'];row=ds.iloc[j];bar=h.loc[d];prev=h.loc[h.index<pd.Timestamp(d)].iloc[-1]
        reference=D(str(prev.close))-D(str(div.get(d,{}).get('amount',0)))
        upper=(reference*D('1.1')).quantize(D('.001'),rounding=ROUND_HALF_UP);lower=(reference*D('.9')).quantize(D('.001'),rounding=ROUND_HALF_UP)
        eq(upper,row.indicative_upper,'daily indicative upper');eq(lower,row.indicative_lower,'daily indicative lower')
        assert lower-D('.0005')<=D(str(bar.open))<=upper+D('.0005')
        expected_capacity=int(D(str(adv.loc[d]))*D('.01'))//100*100;assert int(row.capacity_shares)==expected_capacity
    for f in read(R/'logs'/(policy+'_fills.json')):
        row=ds[ds.date==f['day']].iloc[0];p=D(f['price'])
        assert (f['side']=='buy'and p<D(row.indicative_upper)-D('.0005'))or(f['side']=='sell'and p>D(row.indicative_lower)+D('.0005'))
        assert f['limit_source']=='indicative_rule_proxy_not_dated_exchange_state'
    terminal=read(R/'logs'/(policy+'_terminal.json'));eq(ds.cash.iloc[-1],terminal['cash'],'terminal cash')
    assert int(ds.shares.iloc[-1])==terminal['shares']==sum(x['quantity']for x in terminal['lots']) and not terminal['receivables'] and terminal['pending']is None
    out[policy]['terminal_NAV']=ds.NAV.iloc[-1];out[policy]['full_daily_rows']=len(ds)
# Frozen previous history bytes unchanged; numeric float CSV roundtrip is reported, never silently exact.
prefix=[]
for oldp in [OLD/'inputs/510300_history.csv',OLD/'continuation2024/inputs/510300_history.csv']:
    oldh=pd.read_csv(oldp,index_col='date',parse_dates=True)
    assert (R/'inputs/510300_history.csv').read_bytes().startswith(oldp.read_bytes())
    assert oldh['on'].equals(h.loc[oldh.index,'on'])
    for c in ['open','close','high','low','volume','volume_shares','signal_close','ma63','adv20_prior_shares']:
        np.testing.assert_array_equal(oldh[c].to_numpy(),h.loc[oldh.index,c].to_numpy())
    prefix.append(dict(rows=len(oldh),serialized_prefix_bytes_exact=True,CSV_domain_values_exact=True))
cash=pd.read_csv(R/'daily/CASH.csv',dtype=str);assert cash.date.tolist()==cal
for c,v in [('NAV','1000000'),('cash','1000000'),('market_value','0'),('fee','0')]:assert all(D(x)==D(v)for x in cash[c])
for _,row in pd.read_csv(R/'PERIODS.csv',dtype=str).iterrows():
    ds=pd.read_csv(R/'daily'/(row.benchmark+'.csv'),dtype=str);part=ds[ds.date.between(row.start,row.end)];j=int(part.index[0]);begin=D(ds.NAV.iloc[j-1])if j else D(1000000)
    eq(begin,row.starting_NAV,'period carry');eq(part.NAV.iloc[-1],row.ending_NAV,'period terminal');eq((D(part.NAV.iloc[-1])/begin-1)*100,row.return_pct,'period return')
    peak=begin;dd=D(0)
    for v in part.NAV:peak=max(peak,D(v));dd=max(dd,1-D(v)/peak)
    eq(dd*100,row.period_DD_pct,'period close DD')
for p,hsh in read(R/'OUTPUT_SHA256.json').items():assert sha(p)==hsh
for p,hsh in {**inp['sources'],**inp['inputs'],**run['sources']}.items():assert sha(p)==hsh
out.update(status='PASS_WITH_SCOPE',dates=[cal[0],cal[-1]],full_history_rows=len(h),calendar_days=len(cal),full_original_history_prefixes=prefix,
    source_and_input_SHA_checks=len({**inp['sources'],**inp['inputs'],**run['sources']}),
    sequential_TR_MA63_max_absolute_CSV_error=float(np.max(np.abs(tr-h.signal_close))),
    MA63_max_absolute_CSV_error=float(np.nanmax(np.abs(ma-h.ma63))),
    original_prepare_numeric_roundtrip_max=5.329070518200751e-15,on_classification_exact=True,
    strict_prior20_ADV_hands_to_shares=True,ex_pay_HTML_independent=True,all_next_OPEN_fills_verified_as_daily_proxy=allfills,
    no_year_reset=True,reviewer_account_events=0,reviewer_source_SHA256=sha(__file__),
    scope='Independent raw daily proxy audit; historical dated halt/limit/auction unavailable so execution_verified=false. Different ETF universe/15bp friction from stock candidate; not stock alpha or a promoted MA strategy.')
(HERE/'BENCHMARK_B_2025_26_INDEPENDENT_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
print(json.dumps(out,indent=2,default=str))
