"""Read-only aggregation of recorded account paths; no signal or trade execution."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from bisect import bisect_right
import csv,json,gzip,time,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');ZERO=D(0);START=time.monotonic()
def read(p):return json.loads(Path(p).read_text())
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def csvrows(p):
 with Path(p).open() as f:return list(csv.DictReader(f))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def writecsv(name,rs):
 if not rs:return
 with (O/name).open('w') as f:
  keys=list(dict.fromkeys(k for r in rs for k in r));w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rs)
class Prices:
 def __init__(self,path):self.records={r['series_id']:r for r in read(path)['series']};self.cache={};self.used={}
 def mark(self,sid,day):
  if sid not in self.cache:
   r=self.records[sid];f=pd.read_parquet(r['raw']['path']);dt=pd.to_datetime(f.trade_date if 'trade_date' in f else f.index);days=[str(x.date()) for x in dt];actions=read(r['adjustment']['actions']['path'])['events'];self.cache[sid]=(days,f.close.to_numpy(),actions);self.used[sid]=r['raw']
  ds,cs,acts=self.cache[sid];i=bisect_right(ds,day)-1;assert i>=0;(p,old)=(D(str(cs[i])),ds[i]);assert p.is_finite() and p>0,(sid,day,'price unknown')
  for e in acts:
   if old<e['effective_date']<=day:p=(p-D(str(e.get('signal_cash_per_old_share',e['cash_per_old_share']))))/D(str(e.get('signal_split_ratio',e['split_ratio'])))
  return p
CASES={};bridge=[];stockbridge=[];stockrows=[];actrows=[];summary=[]
for sec,mode in [('TECH','I'),('DRUG','ACT')]:
 ar=RR/('pvr-local-finite-capital-20261029/baseline' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/S0');manifest=RR/('pvr-act-comparison-20261027/input/manifest.json' if sec=='TECH' else 'innovative-drug-sfw3-20261028/prepared/manifest.json');prices=Prices(manifest)
 for stress in ['base','delay1']:
  roots={'A':ar,'B':W/'partial-action-full-account-20261030'/sec/'on' if stress=='base' else W/'partial-action-delay-repair-20261030'/sec/'full'};case={'sector':sec,'stress':stress,'roots':roots,'prices':prices};names={};daily={};contri={};flows={};on={};acts={};profits={};case['accounts']={}
  for pol,root in roots.items():
   aid=f'{mode}__'+('' if pol=='A' else 'B_')+'S0_'+stress;obj=read(root/'accounts-v2'/f'{aid}.json');ds=[r for r in gz(root/'accounts-v2/daily.jsonl.gz') if r['account']==aid];daily[pol]={r['at'][:10]:r for r in ds};cr={(r['date'],r['symbol']):r for r in csvrows(root/'analysis/contributions.csv') if r['account']==aid};contri[pol]=cr;profits[pol]=defaultdict(D)
   for (day,sid),c in cr.items():profits[pol][sid]+=D(c['net_contribution'])
   for r in csvrows(root/'analysis/stocks.csv'):
    if r['account']==aid:names[r['symbol']]=r['name']
   ff=defaultdict(lambda:defaultdict(lambda:dict(buys=0,sells=0,buy_gross=ZERO,sell_gross=ZERO,fee=ZERO,dividend=ZERO,ratios=[])))
   for r in obj['audit_log']:
    k=r['kind']
    if k=='fill':
     f=r['receipt'];x=ff[f['at'][:10]][f['security_id']];side='buy' if f['side']=='buy' else 'sell';x[side+'s']+=int(f['shares']);x[side+'_gross']+=D(f['gross_cny']);x['fee']+=D(f['fees_cny'])
    elif k in ['split','split_fraction_floor_proxy']:ff[r['at'][:10]][r['sid']]['ratios'].append(D(r['ratio']))
    elif k=='dividend_accrual':e=r['receivable'];assert e['currency']=='CNY';ff[e['ex_at'][:10]][e['security_id']]['dividend']+=D(e['net_local'])
    elif k=='expense':raise AssertionError(('explicit account expense needs separate bridge',r))
   flows[pol]=ff;acts[pol]={r['at'][:10]:r for r in obj['audit_log'] if r['kind']=='risk_checkpoint'};on[pol]=True;case['accounts'][pol]=dict(id=aid,obj=obj,daily=ds,contributions=cr,profits=profits[pol],root=root,names=names)
  assert list(daily['A'])==list(daily['B']);days=list(daily['A']);components=['start_holding_price','trade_to_close','cash_dividend','split_rounding','explicit_fees'];totals=defaultdict(D);prevday=None;prevnav={p:D(1000000) for p in ['A','B']};bucket=defaultdict(D);maxerr=ZERO
  for day in days:
   status=('A_on' if on['A'] else 'A_off')+'_'+('B_on' if on['B'] else 'B_off');allvals={}
   for pol in ['A','B']:
    qprev=daily[pol][prevday]['positions'] if prevday else {};qnow=daily[pol][day]['positions'];vals=defaultdict(D)
    for sid in set(qprev)|set(qnow)|set(flows[pol][day]):
     x=flows[pol][day][sid];n=int(qprev.get(sid,0));qty=n;ratio=D(1)
     for r in x['ratios']:ratio*=r;qty=int(D(qty)*r)
     assert qty+x['buys']-x['sells']==qnow.get(sid,0),(sec,stress,pol,day,sid,'share flow')
     pt=prices.mark(sid,day);pp=prices.mark(sid,prevday) if n else ZERO
     z=dict(start_holding_price=D(n)*(ratio*pt-pp),trade_to_close=D(x['buys']-x['sells'])*pt-x['buy_gross']+x['sell_gross'],cash_dividend=x['dividend'],split_rounding=(D(qty)-D(n)*ratio)*pt,explicit_fees=-x['fee']);pnl=sum(z.values(),ZERO);existing=D(contri[pol].get((day,sid),{}).get('net_contribution','0'));err=abs(pnl-existing);maxerr=max(maxerr,err);assert err<D('1e-8'),(sec,stress,pol,day,sid,pnl,existing)
     if qnow.get(sid):assert D(qnow[sid])*pt==D(contri[pol][day,sid]['market_value'])
     for k,v in z.items():vals[k]+=v
     stockbridge.append(dict(sector=sec,stress=stress,policy=pol,date=day,symbol=sid,**z,pnl=pnl))
    nav=D(daily[pol][day]['nav']);err=abs(sum(vals.values(),ZERO)-(nav-prevnav[pol]));maxerr=max(maxerr,err);assert err<D('1e-8'),(sec,stress,pol,day,'daily bridge',err);prevnav[pol]=nav;allvals[pol]=vals
   z={k:allvals['B'][k]-allvals['A'][k] for k in components};delta=sum(z.values(),ZERO);bucket[status]+=delta
   for k,v in z.items():totals[k]+=v
   bridge.append(dict(sector=sec,stress=stress,date=day,prior_ACT_status=status,**z,delta_nav=delta))
   for pol in ['A','B']:on[pol]=acts[pol][day]['on']
   prevday=day
  net=prevnav['B']-prevnav['A'];residual=net-sum(totals.values(),ZERO);assert abs(residual)<D('1e-8');assert abs(sum(profits['B'].values(),ZERO)-sum(profits['A'].values(),ZERO)-net)<D('1e-8')
  sr=[]
  for sid in set(profits['A'])|set(profits['B']):
   z=dict(sector=sec,stress=stress,symbol=sid,name=names.get(sid),A=profits['A'].get(sid,ZERO),B=profits['B'].get(sid,ZERO));z['difference']=z['B']-z['A'];sr.append(z);stockrows.append(z)
  for k,v in bucket.items():actrows.append(dict(sector=sec,stress=stress,prior_status=k,descriptive_delta=v))
  sm=dict(sector=sec,stress=stress,A_profit=prevnav['A']-D(1000000),B_profit=prevnav['B']-D(1000000),delta=net,**totals,residual=residual,max_stock_day_error=maxerr,stocks=len(sr),days=len(days));summary.append(sm);case.update(summary=sm,stocks=sr,names=names);CASES[sec,stress]=case
  print('BRIDGE',sm,flush=True);print('TOP',sec,stress,sorted(sr,key=lambda r:r['difference'],reverse=True)[:3],sorted(sr,key=lambda r:r['difference'])[:3],flush=True)
writecsv('DAILY_VALUE_BRIDGE.csv',bridge);writecsv('STOCK_DAY_VALUE_BRIDGE.csv',stockbridge);writecsv('STOCK_DIFFERENCES.csv',stockrows);writecsv('ACT_CONDITIONAL_BUCKETS.csv',actrows);save(O/'BRIDGE_SUMMARY.json',summary)
dids=[]
for sec in ['TECH','DRUG']:
 aa={r['symbol']:r for r in CASES[sec,'base']['stocks']};bb={r['symbol']:r for r in CASES[sec,'delay1']['stocks']}
 for sid in set(aa)|set(bb):dids.append(dict(sector=sec,symbol=sid,name=(aa.get(sid) or bb[sid])['name'],normal_delta=aa.get(sid,{}).get('difference',ZERO),delay_delta=bb.get(sid,{}).get('difference',ZERO),change=bb.get(sid,{}).get('difference',ZERO)-aa.get(sid,{}).get('difference',ZERO)))
writecsv('STRESS_DIFFERENCE_BRIDGE.csv',dids)
print('STRESS_CHAIN',sorted([r for r in dids if r['sector']=='TECH'],key=lambda r:r['change'])[:5],flush=True)
# More descriptive event aggregates follow; no controller or account is executed.
