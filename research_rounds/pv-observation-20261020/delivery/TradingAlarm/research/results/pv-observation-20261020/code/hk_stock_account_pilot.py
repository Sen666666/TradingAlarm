"""Explicit-assumption Tencent account pilot; not certified investable performance."""
import json,re,math
from pathlib import Path
import numpy as np
import pandas as pd
from in_kind_ledger import InKindLedger
from hk_cash_annotations import parse_cash
from trend_engine import baselines
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/hk-stock-account-pilot'
IN_KIND={'2022-01-20':('09618',21),'2023-01-05':('03690',10)}
def load(code):
 d=json.loads((ROOT/f'data/hk-stock-raw/hk{code}.json').read_text())
 raw=pd.DataFrame([dict(date=pd.Timestamp(r[0]),open=float(r[1]),close=float(r[2]),high=float(r[3]),low=float(r[4]),volume=float(r[5])) for r in d['rows']]).set_index('date')
 if raw.index.has_duplicates or not raw.index.is_monotonic_increasing or not np.isfinite(raw.to_numpy()).all() or (raw[['open','close','high','low']]<=0).any().any() or (raw.high<raw[['open','close','low']].max(axis=1)).any() or (raw.low>raw[['open','close','high']].min(axis=1)).any():raise ValueError('invalid raw bars')
 events=[]
 for r in d['rows']:
  if r[0]<'2020-01-01':continue
  for e in r[6:]:
   if not isinstance(e,dict):continue
   if e.get('hgcgContent') or e.get('ggContent'):raise ValueError('unmodeled share action')
   text=e.get('FHcontent','')
   if not text:continue
   if code=='00700' and r[0] in IN_KIND:continue
   ex=pd.Timestamp(e['cqr']);pay=pd.Timestamp(e['paixiri'])
   if ex!=pd.Timestamp(r[0]) or pay<ex:raise ValueError('invalid dividend dates')
   for component in parse_cash(text):
    events.append(dict(ex=ex,pay=pay,amount=float(component['amount']),currency=component['currency']))
 return raw,events

def run(raw,events,fx,target,cost_bps=20,primary="00700",start="2022-01-01",order_increment=100,signal_lag=1):
 if type(order_increment) is not int or order_increment<=0 or type(signal_lag) is not int or signal_lag<1:raise ValueError("invalid execution assumptions")
 parent=raw[primary];dates=parent.loc[start:].index
 if len(dates)==0 or parent.index.get_loc(dates[0])<signal_lag:raise ValueError("insufficient signal history")
 distributions=IN_KIND if primary=='00700' else {}
 if target.isna().any() or not target.between(0,1).all() or fx.reindex(dates).isna().any() or not fx.reindex(dates).gt(0).all():raise ValueError('invalid target/FX')
 cash=1e6;shares=0;claims=InKindLedger();due=[];rows=[];orders=[];last=1e6;peak=1e6
 for dt in dates:
  day=str(dt.date());row=parent.loc[dt]
  if day in distributions:
   child,den=distributions[day];claims.accrue(day,child,day,shares,1,den)
  for code,items in events.items():
   qty=shares if code==primary else sum(c.whole for c in claims.claims.values() if c.recipient==code)
   for e in items:
    if dt==e['ex'] and qty:due.append(dict(pay=e['pay'],amount=qty*e['amount'],currency=e['currency'],settlement=e.get('settlement'),quantity=qty))
  def due_value(e):
   settlement=e.get('settlement')
   if settlement and dt>pd.Timestamp(settlement['fixing']):return e['quantity']*settlement['hkd_per_share']
   return e['amount']*(float(fx.loc[dt]) if e['currency']=='USD' else 1.)
  pending=[]
  for e in due:
   value=due_value(e)
   if e['pay']<=dt:
    fixed=e.get('settlement') and dt>pd.Timestamp(e['settlement']['fixing'])
    cash+=value*(.999 if e['currency']=='USD' and not fixed else 1.)
   else:pending.append(e)
  due=pending
  cash_due=sum(due_value(e) for e in due)
  def mark(field):
   return {code:(day,float(raw[code].loc[dt,field]),day,1.) for code in raw if any(c.recipient==code and c.whole for c in claims.claims.values())}
  owed_open=claims.value(day,mark('open'),fraction_policy='zero_floor')['total']
  navopen=cash+cash_due+owed_open+shares*row.open
  prev=parent.index[parent.index.get_loc(dt)-signal_lag]
  desired=math.floor(max(0,navopen*target.loc[prev]-owed_open)/row.open/order_increment)*order_increment
  delta=desired-shares;fee=0
  if row.volume<=0:delta=0
  if delta>0:
   delta=min(delta,math.floor(max(0,cash-18)/(row.open*(1+cost_bps/10000))/order_increment)*order_increment)
  if delta:
   fee=max(18,abs(delta)*row.open*cost_bps/10000);cash-=delta*row.open+fee;shares+=delta
   orders.append(dict(date=day,signal_date=str(prev.date()),delta=delta,price=float(row.open),fee=float(fee)))
  if cash<-.001:raise AssertionError('negative cash')
  owed=claims.value(day,mark('close'),fraction_policy='zero_floor')['total']
  nav=cash+cash_due+owed+shares*row.close;peak=max(peak,nav)
  rows.append(dict(date=dt,nav=nav/1e6,return_daily=nav/last-1,drawdown=nav/peak-1,cash=cash,parent_shares=shares,security_claim_value=owed,cash_receivable=cash_due,fee=fee));last=nav
 path=pd.DataFrame(rows).set_index('date');years=(path.index[-1]-path.index[0]).days/365.25
 return dict(cagr=float(path.nav.iloc[-1]**(1/years)-1),max_drawdown=float(path.drawdown.min()),best252=float(path.nav.pct_change(252).max()),total_return=float(path.nav.iloc[-1]-1),orders=len(orders),fees=float(path.fee.sum()),terminal_security_claim=float(path.security_claim_value.iloc[-1])),path,orders

def main():
 OUT.mkdir(exist_ok=True);protocol=dict(status='Conditional accounting pilot,not certified fullstrategy',start='2022-01-01',symbol='HK00700',rules=['buy_hold','sma200','donchian55_20','sma200_vol15'],cost_bps_per_side=[20,40],minimum_fee_hkd=18,lot=100,distribution_policy='Keep whole recipient shares marked indefinitely,never sell or use claims as cash;fractions valuedzero explicit conservative scenario',usd_dividend_policy='Vendor cashamount perHKshare,not ADR;convert onpaydate usinglaggedECB FX less10bps',limitations=['Single retrospectively chosen surviving stock;not A/HK universe validation','Vendor cashdates andper-shareamounts not fullyissuerverified','No full historical tax/levy/minfee/quote/oddlot model','Fractional cashinlieuforegone;no brokerdeliveryverification','No desired20%DD guarantee;strategies frozennooptimization'])
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2));loaded={c:load(c) for c in ['00700','09618','03690']};raw={c:v[0] for c,v in loaded.items()};events={c:v[1] for c,v in loaded.items()}
 f=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text())
 if f['base']!='USD':raise ValueError('wrongFXbase')
 source=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in f['rates'].items()}).sort_index()
 idx=raw['00700'].index;fx=source.reindex(source.index.union(idx)).ffill().reindex(idx)
 parent=raw['00700'].loc['2020-01-01':].copy();cash=pd.Series(0.,index=parent.index)
 for e in events['00700']:cash.loc[e['ex']]+=e['amount']
 for d,(c,den) in IN_KIND.items():cash.loc[d]+=raw[c].loc[d,'close']/den
 gross=(parent.close+cash)/parent.close.shift();level=parent.close.iloc[0]*gross.fillna(1).cumprod();signal=parent.copy()
 for col in ['open','high','low','close']:signal[col]*=level/parent.close
 targets=baselines(signal);vol=np.log(signal.close).diff().rolling(60).std()*np.sqrt(252);targets['sma200_vol15']=targets.sma200*(.15/vol).clip(upper=1).fillna(0)
 result=[]
 for name,cost in [(n,c) for n in protocol['rules'] for c in [20,40]]:
  m,p,o=run(raw,events,fx,targets[name],cost_bps=cost);m.update(strategy=name,cost_bps=cost);result.append(m);p.to_csv(OUT/f'{name}-cost{cost}-path.csv');(OUT/f'{name}-cost{cost}-orders.json').write_text(json.dumps(o));print(name,cost,m,flush=True)
 (OUT/'results.json').write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
