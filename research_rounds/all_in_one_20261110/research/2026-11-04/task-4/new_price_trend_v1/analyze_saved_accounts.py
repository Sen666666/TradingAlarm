"""Read-only actual cash/mark/recognized-dividend attribution of native books.
No Runner/Account construction, no new fills and no deletion-return estimate.
"""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import gzip,hashlib,importlib.util,json,sys,time
from datetime import datetime

O=Path(__file__).resolve().parent;OUT=O/'analysis';Z=D(0);EPS=D('.000001');SRC={}
PRICE_READER=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/c1-drawdown-capacity-20261101/analyze_saved.py')
spec=importlib.util.spec_from_file_location('BB_entry_unchanged_saved_price_reader',PRICE_READER)
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
sys.path.insert(0,str(O));import native_mark_reader as MARK
# The old saved reader's plain facts.raw_close is metadata-only here. Actual
# valuation must include native stale-action unit transformations.
A.price=MARK.price
def bind(p):p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def load(p,lines=False):
 with gzip.open(bind(p),'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
def n(x):return D(str(x))
def save(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def eq(a,b,tag):assert abs(a-b)<EPS,(tag,str(a),str(b),str(a-b))
def dd(nav,initial):
 peak=initial;worst=Z
 for v in nav:peak=max(peak,v);worst=max(worst,(peak-v)/peak)
 return worst*100
def underwater(rr,initial):
 peak=initial;peakday=datetime.fromisoformat(rr[0]['begin_NAV_day']);longest=0;under=False
 for r in rr:
  d=datetime.fromisoformat(r['day']);v=r['end_NAV']
  if v>=peak:
   if under:longest=max(longest,(d-peakday).days)
   peak=v;peakday=d;under=False
  else:under=True;longest=max(longest,(d-peakday).days)
 return dict(longest_underwater_calendar_days=longest,end_underwater_censored=under,
  definition='Own-period CLOSE high-water incl actual prior-CLOSE initial NAV; terminal un-recovered run included and flagged')
def period(rr):
 assert rr
 a=rr[0]['begin_NAV'];b=rr[-1]['end_NAV']
 return dict(begin=rr[0]['day'],end=rr[-1]['day'],CLOSEs=len(rr),begin_NAV=a,end_NAV=b,wealth_change=b-a,
  return_pct=(b/a-1)*100,max_CLOSE_DD_pct=dd([r['end_NAV']for r in rr],a),
  mean_exposure_pct=sum((r['exposure_pct']for r in rr),Z)/len(rr),
  peak_exposure_pct=max(r['exposure_pct']for r in rr),
  actual_buy_cash=sum((r['buy_cash']for r in rr),Z),actual_sell_net=sum((r['sell_net']for r in rr),Z),
  actual_fees=sum((r['fees']for r in rr),Z),actual_fill_sides=sum(r['fill_sides']for r in rr),
  actual_gross_turnover=sum((r['gross_turnover']for r in rr),Z),
  gross_turnover_over_mean_NAV=sum((r['gross_turnover']for r in rr),Z)/(sum((r['end_NAV']for r in rr),Z)/len(rr)),
  actual_OPENs=sum(r['has_actual_OPEN']for r in rr),active_OPENs=sum(r['has_actual_OPEN']and r['ACT_at_OPEN']for r in rr),
  **underwater(rr,a))

def analyze(name,root,expected,window_start):
 b=load(root/'pair/B.json.gz');ds=load(root/'pair/daily.jsonl.gz',True);certs=load(root/'pair/balances.jsonl.gz',True)
 assert len(ds)==len(certs)==expected and read(root/'DONE.json')['completed']
 rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
 start_at=datetime.fromisoformat(window_start+'T15:10:00+08:00');end_at=datetime.fromisoformat(str(ds[-1]['at']))
 OPEN_days={str(t)[:10]for t in rules['calendars']['A']if start_at<=datetime.fromisoformat(t)<=end_at}
 all_industries={A.META[s]['sector_id']:A.META[s]['industry']for s in A.SM};assert len(all_industries)==90
 tx=defaultdict(list);div=defaultdict(list);buycost=defaultdict(lambda:Z)
 for t in b['trades']:
  tx[str(t['at'])[:10]].append(t)
  if t['side']=='buy':buycost[t['layer']]+=n(t['gross_cny'])+n(t['fees_cny'])
 for e in b['audit']:
  if e['kind']=='dividend_accrual':
   r=e['receivable'];div[str(r['ex_at'])[:10]].append(r)
 cash=defaultdict(lambda:Z);dividend=defaultdict(lambda:Z);oldwealth=defaultdict(lambda:Z)
 rows=[];sector_rows=[];prev_nav=D(1000000);prev_day=window_start;prev_on=True;stockdays=defaultdict(list)
 for r,cert in zip(ds,certs):
  day=str(r['at'])[:10];assert str(cert['at'])[:10]==day
  for k in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']:
   eq(n(cert[k]),Z,(name,day,k))
  for d in cert['pool_occupancy_difference'].values():eq(n(d),Z,(name,day,'pool'))
  bc=sc=fees=Z
  for t in tx[day]:
   sid=t['security_id'];gross=n(t['gross_cny']);fee=n(t['fees_cny']);fees+=fee
   if t['side']=='buy':cash[sid]-=gross+fee;bc+=gross+fee
   else:cash[sid]+=gross-fee;sc+=gross-fee
  for e in div[day]:dividend[e['security_id']]+=n(e['net_local'])
  inv={sid:D(q)*A.price(sid,day)for sid,q in r['positions'].items()if q}
  eq(sum(inv.values(),Z),n(r['inventory']),(name,day,'independent raw marks over saved actual shares'))
  wealth={sid:cash[sid]+dividend[sid]+inv.get(sid,Z)for sid in set(cash)|set(dividend)|set(inv)}
  eq(D(1000000)+sum(wealth.values(),Z),n(r['nav']),(name,day,'tradecash+recognizeddiv+inventory NAV'))
  sec=defaultdict(lambda:dict(wealth_change=Z,inventory=Z))
  for sid,w in wealth.items():
   meta=A.META[sid];g=sec[meta['sector_id']];g['industry']=meta['industry'];g['wealth_change']+=w-oldwealth[sid];g['inventory']+=inv.get(sid,Z)
   if sid in inv:stockdays[sid].append(dict(day=day,value=inv[sid],NAV=n(r['nav'])))
  for sector,g in sec.items():sector_rows.append(dict(day=day,sector=sector,**g,exposure_pct=g['inventory']/n(r['nav'])*100))
  eq(sum((v['wealth_change']for v in sec.values()),Z),n(r['nav'])-prev_nav,(name,day,'allindustry wealth'))
  rows.append(dict(day=day,begin_NAV_day=prev_day,begin_NAV=prev_nav,end_NAV=n(r['nav']),wealth_change=n(r['nav'])-prev_nav,
   inventory=n(r['inventory']),exposure_pct=n(r['inventory'])/n(r['nav'])*100,available=n(r['available']),
   buy_cash=bc,sell_net=sc,fees=fees,fill_sides=len(tx[day]),gross_turnover=sum((n(t['gross_cny'])for t in tx[day]),Z),
   has_actual_OPEN=day in OPEN_days,ACT_at_OPEN=prev_on,ACT_after_CLOSE=bool(r['on'])))
  oldwealth=defaultdict(lambda:Z,wealth);prev_nav=n(r['nav']);prev_day=day;prev_on=bool(r['on'])
 eq(prev_nav,n(b['ending_NAV']),(name,'final NAV'))
 fills={e['layer']:e for e in b['journal']if e['kind']=='real_buy_fill'}
 end=rows[-1]['day'];layers=[]
 for l in b['layers']:
  sid=l['sid'];m=b['metadata'][str(l['id'])];j=fills[l['id']];value=D(l['qty'])*A.price(sid,end)if l['qty']else Z
  layers.append(dict(layer=l['id'],sid=sid,name=A.META[sid]['name'],industry=A.META[sid]['industry'],role=j['role'],
   signal_day=str(l['signal_at'])[:10],opened=l['opened'],closed=l['closed'],qty=l['qty'],
   cost=buycost[l['id']],net=n(l['cash'])+n(l['dividend'])+value,value=value,receipt=j['CP1_id']))
 eq(sum((l['net']for l in layers),Z),prev_nav-D(1000000),(name,'alllayer ending contribution'))
 stock=[]
 for sid in sorted({l['sid']for l in layers}):
  ll=[l for l in layers if l['sid']==sid];sd=stockdays[sid]
  stock.append(dict(sid=sid,name=A.META[sid]['name'],industry=A.META[sid]['industry'],layers=len(ll),
   cost=sum((l['cost']for l in ll),Z),net=sum((l['net']for l in ll),Z),open_layers=sum(bool(l['qty'])for l in ll),
   first_buy=min(str(l['opened'])for l in ll),held_CLOSEs=len(sd),
   mean_whole_window_NAV_weight_pct=sum((r['value']/r['NAV']*100 for r in sd),Z)/len(rows)))
 periods={'all':period(rows)}
 for year in sorted({r['day'][:4]for r in rows}):periods[year]=period([r for r in rows if r['day'].startswith(year)])
 if rows[0]['day']<'2024-09-24'<=end:periods['after_924']=period([r for r in rows if r['day']>='2024-09-24'])
 if rows[0]['day']<'2026-01-01'<=end:periods['2026H1']=period([r for r in rows if r['day']>='2026-01-01'])
 industry=[]
 for pname in periods:
  begin,finish=periods[pname]['begin'],periods[pname]['end']
  rs=[r for r in sector_rows if begin<=r['day']<=finish]
  for sec in sorted(all_industries):
   a=[r for r in rs if r['sector']==sec]
   industry.append(dict(period=pname,sector=sec,industry=all_industries[sec],wealth_change=sum((r['wealth_change']for r in a),Z),
    mean_NAV_weight_pct=sum((r['exposure_pct']for r in a),Z)/periods[pname]['CLOSEs']))
 save(name+'_DAILY.json',rows);save(name+'_LAYERS.json',layers);save(name+'_STOCKS.json',stock)
 save(name+'_PERIODS.json',periods);save(name+'_INDUSTRIES.json',industry)
 return dict(periods=periods,stocks=stock,layers=layers,industry=industry)

def main():
 start=time.monotonic();OUT.mkdir(exist_ok=True);bind(__file__);bind(PRICE_READER)
 root=O/'funding/runs';assert read(root/'COMPLETE.json')['passed'];data={}
 for window,days in [('long',726),('strong',242)]:
  for mode in ['OFF','BB20']:
   key=window+'_'+mode;data[key]=analyze(key,root/key,days,'2022-01-01'if window=='long'else'2025-07-01')
 comparisons={};winner=[]
 for window in ['long','strong']:
  old,new=data[window+'_OFF'],data[window+'_BB20'];oldstocks={r['sid']:r for r in old['stocks']};newstocks={r['sid']:r for r in new['stocks']}
  delta=[]
  for sid in sorted(set(oldstocks)|set(newstocks)):
   a=oldstocks.get(sid);b=newstocks.get(sid);delta.append(dict(sid=sid,name=A.META[sid]['name'],industry=A.META[sid]['industry'],
    old=a,new=b,net_delta=(b['net']if b else Z)-(a['net']if a else Z)))
  eq(sum((r['net_delta']for r in delta),Z),new['periods']['all']['end_NAV']-old['periods']['all']['end_NAV'],(window,'stock delta bridge'))
  comparisons[window]=dict(old=old['periods'],new=new['periods'],new_stock_count=len(set(newstocks)-set(oldstocks)),lost_stock_count=len(set(oldstocks)-set(newstocks)))
  for a in sorted(old['stocks'],key=lambda r:-r['net'])[:10]:winner.append(dict(window=window,original_winner=a,new=newstocks.get(a['sid'])))
  save(window+'_STOCK_DELTAS.json',sorted(delta,key=lambda r:-r['net_delta']))
 save('ACCOUNT_COMPARISONS.json',comparisons);save('ORIGINAL_TOP10_WINNER_COVERAGE.json',winner)
 for sid in A.frames:
  p=Path(A.SM[sid]['refs']['facts']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==A.SM[sid]['output_sha256'][str(p)];SRC[str(p)]=h
 SRC.update(MARK.sources);save('NATIVE_DERIVED_EX_MARK_REFERENCES.json',MARK.derived_marks)
 save('SOURCE_SHA256.json',SRC);save('SCOPE.json',dict(seconds=time.monotonic()-start,account_runs=0,
  cash_mark_bridge='Actual trade consideration plus fees once, recognized dividends once, unchanged native raw-mark function over independently re-read sources and saved actual quantities; stale theoretical ex references retained. Native certificate all-close checks also verified.',
  quantity_boundary='Uses actual saved quantities and checks original native quantity/pool/NAV certificates; does not claim a third independent corporate-action share ledger.',
  cohort_boundary='Period wealth and ending lifecycle layer net reported separately; original winner label evaluated after planning; no proportional old PnL or filtered-layer deletion return.',
  price_execution='Original A-share daily execution proxy incl5bps and dated fees/T+1; no new data, limit-down queue position not identified by daily bars',
  sample='Current1709 survivor universe/current industry snapshot; development history, no PIT/OOS/live claim'))
 print(json.dumps(comparisons,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
