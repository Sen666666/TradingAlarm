"""Independent saved-book/daily arithmetic audit; no strategy import/replay/mark engine."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import gzip,json,hashlib,csv
ROOT=Path(__file__).resolve().parent.parent; OUT=Path(__file__).resolve().parent
Z=D(0); H=D(100); EPS=D('.000001')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def day(r):return r['at'][:10]
def near(a,b,label):
 assert abs(a-b)<EPS,(label,str(a),str(b),str(a-b))
def ser(x):
 if isinstance(x,D):return str(x)
 if isinstance(x,dict):return {k:ser(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [ser(v) for v in x]
 return x
binding=json.load(open(ROOT/'market_gross_admission_native_v1/ARCHIVED_B_CONTROL_BINDING.json'))
prior_finance=json.load(open(ROOT/'market_gross_admission_full_ledger_review_v1/long/FINANCE_AND_ATOMIC_AUDIT.json'))
prior_derived=json.load(open(ROOT/'market_gross_admission_full_ledger_review_v1/DERIVED_KEY_REVIEW.json'))
bfiles=binding['long']['source_sha256']; cases={
 'No60':(Path(next(x for x in bfiles if x.endswith('/daily.jsonl.gz'))),Path(next(x for x in bfiles if x.endswith('/B.json.gz')))),
 'D_GROSS10':(ROOT/'market_gross_admission_native_v1/full-long-v1/pair/daily.jsonl.gz',ROOT/'market_gross_admission_native_v1/full-long-v1/pair/D_GROSS10.json.gz')}
anchors=['2023-12-29','2024-09-23','2024-10-08','2024-12-31']; phases=[('PRE_924','2024-01-02','2024-09-23'),('924_TO_OCT8','2024-09-24','2024-10-08'),('POST_OCT8','2024-10-09','2024-12-31'),('FULL_2024','2024-01-02','2024-12-31')]
report={'status':'PASS_INDEPENDENT_SAVED_ARITHMETIC_AUDIT','scope':'No new accounts/replay/indicators/prices/valuation engine. Original saved native financial basis reused, previously audited raw marks/CA quantities not re-marked here. New independent Decimal cash/fee/dividend_AR/daily NAV component/phase/MDD/actual-fill/H timing arithmetic.','cases':{},'source_sha256':{}}
def mdd(ds,begin,begin_day):
 peak=begin; peak_day=begin_day; result={'pct':Z,'peak_day':begin_day,'peak_NAV':begin,'trough_day':begin_day,'trough_NAV':begin}
 for r in ds:
  v=D(r['nav'])
  if v>peak:peak=v;peak_day=day(r)
  dd=(1-v/peak)*H
  if dd>result['pct']:result=dict(pct=dd,peak_day=peak_day,peak_NAV=peak,trough_day=day(r),trough_NAV=v)
 return result

def intervals(rs,key):
 result=[];cur=None
 for r in rs:
  if not r[key]:
   if cur is None:cur=dict(first=day(r),last=day(r),days=0)
   cur['last']=day(r);cur['days']+=1
  elif cur is not None:result.append(cur);cur=None
 if cur:result.append(cur)
 return result
for label,(dp,bp) in cases.items():
 for p in (dp,bp):
  report['source_sha256'][str(p)]=sha(p)
  if label=='No60':assert sha(p)==bfiles[str(p)],('No60 binding',p)
  else:assert sha(p)==prior_finance['source_sha256'][str(p)],('D previously audited source identity',p)
 ds=rows(dp); book=load(bp); byday={day(r):r for r in ds}; ix={day(r):i for i,r in enumerate(ds)}
 trades=book['trades']; txd=defaultdict(list);divd=defaultdict(lambda:Z)
 for t in trades:txd[day(t)].append(t)
 for e in book['audit']:
  if e['kind']=='dividend_accrual':divd[e['receivable']['ex_at'][:10]]+=D(e['receivable']['net_local'])
 cash=D('1000000');fees=Z;div=Z;cum_buy=0;cum_sell=0;peak=D('1000000'); glo={};prev_on=True
 audit_counts=Counter(); daily_detail=[]
 for r in ds:
  dt=day(r);r['OPEN_on_from_prior_CLOSE']=prev_on;prev_on=r['on']
  for t in txd[dt]:
   f=D(t['fees_cny']);g=D(t['gross_cny']);fees+=f
   if t['side']=='buy':cash-=g+f;cum_buy+=1
   else:cash+=g-f;cum_sell+=1
  div+=divd[dt]
  liquid=sum((D(r[k]) for k in ['available','order_reserved','settlement_locked','sale_receivable']),Z)-D(r['payable'])
  near(cash,liquid,('all saved close cash bridge',label,dt))
  near(div,D(r['dividend_receivable']),('all saved close original accrued dividend AR',label,dt))
  near(fees,D(r['fees_cny']),('all saved close cumulative actual fees',label,dt))
  near(liquid+D(r['dividend_receivable'])+D(r['inventory']),D(r['nav']),('all saved close NAV components',label,dt))
  assert int(r['counts'].get('buy_fills',0))==cum_buy and int(r['counts'].get('sell_fills',0))==cum_sell
  peak=max(peak,D(r['nav']));glo[dt]=(1-D(r['nav'])/peak)*H
  if dt.startswith('2024'):
   daily_detail.append(dict(date=dt,NAV=r['nav'],cash_buckets_net=liquid,available=r['available'],order_reserved=r['order_reserved'],settlement_locked=r['settlement_locked'],payable=r['payable'],sale_receivable=r['sale_receivable'],dividend_AR=r['dividend_receivable'],inventory=r['inventory'],gross_pct=D(r['inventory'])/D(r['nav'])*H,held_stocks=len(r['positions']),layers=len(r['layers']),OPEN_on=r['OPEN_on_from_prior_CLOSE'],CLOSE_on=r['on'],global_DD_pct=glo[dt],actual_buy_fills=sum(t['side']=='buy' for t in txd[dt]),actual_sell_fills=sum(t['side']=='sell' for t in txd[dt]),actual_fees=sum((D(t['fees_cny']) for t in txd[dt]),Z)))
  audit_counts['daily_cash_fee_AR_components_actualcount_checks']+=1
 points=[]
 for dt in anchors:
  r=byday[dt];points.append(dict(date=dt,at=r['at'],NAV=r['nav'],available=r['available'],order_reserved=r['order_reserved'],settlement_locked=r['settlement_locked'],payable=r['payable'],sale_receivable=r['sale_receivable'],dividend_AR=r['dividend_receivable'],inventory=r['inventory'],gross_pct=D(r['inventory'])/D(r['nav'])*H,held_stocks=len(r['positions']),layers=len(r['layers']),CLOSE_on=r['on'],global_DD_at_anchor_pct=glo[dt]))
 metrics=[]
 for name,start,end in phases:
  a=ix[start];b=ix[end];subset=ds[a:b+1];before=ds[a-1];initial=D(before['nav']);terminal=D(subset[-1]['nav']);tx=[t for r in subset for t in txd[day(r)]];buys=[t for t in tx if t['side']=='buy'];sells=[t for t in tx if t['side']=='sell']
  buygross=sum((D(t['gross_cny']) for t in buys),Z);buyfees=sum((D(t['fees_cny']) for t in buys),Z);sellgross=sum((D(t['gross_cny']) for t in sells),Z);sellfees=sum((D(t['fees_cny']) for t in sells),Z);netcash=sellgross-sellfees-buygross-buyfees
  div_delta=D(subset[-1]['dividend_receivable'])-D(before['dividend_receivable']);invdelta=D(subset[-1]['inventory'])-D(before['inventory'])
  def cliq(r):return sum((D(r[k]) for k in ['available','order_reserved','settlement_locked','sale_receivable']),Z)-D(r['payable'])
  near(netcash,cliq(subset[-1])-cliq(before),('phase net trade cash',label,name))
  near(netcash+div_delta+invdelta,terminal-initial,('phase wealth telescope',label,name))
  near(sum((divd[day(r)] for r in subset),Z),div_delta,('phase AR change equals accrual',label,name))
  near(buyfees+sellfees,D(subset[-1]['fees_cny'])-D(before['fees_cny']),('phase fees',label,name))
  metrics.append(dict(phase=name,start=start,end=end,CLOSE_days=len(subset),own_initial_anchor=day(before),own_initial_NAV=initial,end_NAV=terminal,NAV_change=terminal-initial,own_return_pct=(terminal/initial-1)*H,buy_fills=len(buys),sell_fills=len(sells),actual_buy_gross=buygross,actual_buy_fees=buyfees,actual_buy_cash=buygross+buyfees,actual_sell_gross=sellgross,actual_sell_fees=sellfees,actual_sell_net=sellgross-sellfees,actual_fees=buyfees+sellfees,net_trade_cash_flow=netcash,cash_bucket_delta=cliq(subset[-1])-cliq(before),dividend_AR_delta=div_delta,inventory_value_delta=invdelta,phase_local_MDD=mdd(subset,initial,day(before)),global_DD_peak_within_phase_pct=max(glo[day(r)] for r in subset),paused_OPEN_days=sum(not r['OPEN_on_from_prior_CLOSE'] for r in subset),paused_CLOSE_days=sum(not r['on'] for r in subset),mean_prior_CLOSE_gross_pct=sum((D(ds[ix[day(r)]-1]['inventory'])/D(ds[ix[day(r)]-1]['nav'])*H for r in subset),Z)/D(len(subset)),mean_CLOSE_gross_pct=sum((D(r['inventory'])/D(r['nav'])*H for r in subset),Z)/D(len(subset))))
 near(sum((v['NAV_change'] for v in metrics[:3]),Z),metrics[-1]['NAV_change'],('three phases total',label))
 year=[r for r in ds if day(r).startswith('2024')]
 h=[r for r in book['audit'] if r['kind']=='risk_checkpoint']
 assert len(h)==len(ds)==726
 for r,e in zip(ds,h):
  assert r['at']==e['at'] and r['on']==e['on'],('native H checkpoint clock/state',label,r['at'])
  near(D(r['nav']),D(e['nav']),('native H checkpoint equity',label,r['at']))
 audit_counts['native_H_checkpoint_clock_state_NAV_checks']=len(h)
 transitions=[];prev=None
 for r in h:
  if r['on']!=prev:
   if day(r).startswith('2024'):transitions.append(r)
  prev=r['on']
 ca=[r for r in book['audit'] if r['kind'] in ('split','split_fraction_floor_proxy','targeted_non_pro_rata_issuance') and day(r).startswith('2024')]
 case=dict(anchors=points,phases=metrics,full_2022_2024_close_MDD=mdd(ds,D('1000000'),'initial_2022'),year_2024_CLOSE_paused_intervals=intervals(year,'on'),year_2024_OPEN_paused_intervals=intervals(year,'OPEN_on_from_prior_CLOSE'),year_2024_H_transitions=transitions,year_2024_CA=ca,original_dividend_ar_all_years=dict(accrued=div,paid_cash_events=0,qualification='All saved original dividend receivable records have paid_at=null; retained as AR, not spendable cash or actual cash receipt.'),checks=dict(audit_counts),notes=['Inventory delta is a change in position VALUE including purchases/sales, not unrealized P&L by itself. Net cash flow is not realized profit. NAV change = net trade cash + dividend AR delta + inventory value delta.','Actual fees exclude implicit daily-bar slippage embedded in execution price. No assumption that higher cost multipliers were used.','Phase local MDD includes the previous close as the initial peak candidate; global DD uses peak from initial2022, no annual reset. All are CLOSE observations, not intraday MDD.','Mean prior CLOSE exposure is a lagged endpoint statistic, not daily/intraday average exposure; Sep30 new buys are not included until next lag observation.'])
 assert all(e['receivable']['paid_at'] is None for e in book['audit'] if e['kind']=='dividend_accrual')
 report['cases'][label]=case
 with open(OUT/(label+'_2024_DAILY.csv'),'w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(daily_detail[0]));w.writeheader();w.writerows(ser(daily_detail))
 if label=='D_GROSS10':
  for phase,key in [('924_TO_OCT8','period_924'),('POST_OCT8','period_post924')]:
   new=next(v for v in metrics if v['phase']==phase);old=prior_derived[key]
   for nk,ok in [('own_initial_NAV','initial_own_NAV'),('end_NAV','end_NAV'),('NAV_change','wealth_change'),('own_return_pct','return_pct'),('actual_buy_cash','actual_buy_cash'),('actual_sell_net','actual_sell_net'),('actual_fees','actual_fees'),('dividend_AR_delta','recognized_dividend')]:
    near(new[nk],D(old[ok]),('new independent result versus prior3017',phase,nk))
   assert new['buy_fills']==old['buy_fills'] and new['sell_fills']==old['sell_fills']
  case['newly_recomputed_924_and_post_matches_prior3017']=True
report['reused_evidence']={}
for rel in ['market_gross_admission_full_ledger_review_v1/DERIVED_KEY_REVIEW.json','market_gross_admission_full_ledger_review_v1/FINAL_TWO_WINDOW_FINANCE_PVR_ATOMIC_REVIEW.json','market_gross_admission_full_ledger_review_v1/long/FINANCE_AND_ATOMIC_AUDIT.json','market_gross_admission_native_v1/ARCHIVED_B_CONTROL_BINDING.json']:
 p=ROOT/rel;report['reused_evidence'][rel]=sha(p)
report['checker_sha256']=sha(__file__)
for p,v in report['source_sha256'].items():assert sha(p)==v,('source immutable during audit',p)
(OUT/'ACCOUNT_2024_INDEPENDENT_AUDIT.json').write_text(json.dumps(ser(report),ensure_ascii=False,indent=2))
for name,c in report['cases'].items():
 print(name)
 for x in c['anchors']:print(x['date'], 'NAV',x['NAV'],'cash',x['available'],'AR',x['dividend_AR'],'inventory',x['inventory'],'gross%',x['gross_pct'])
 for x in c['phases']:print(x['phase'], 'delta',x['NAV_change'],'ret%',x['own_return_pct'],'localMDD%',x['phase_local_MDD']['pct'],'globalDD%',x['global_DD_peak_within_phase_pct'],'buy/sell',x['buy_fills'],x['sell_fills'],'fees',x['actual_fees'],'cash/AR/invdelta',x['cash_bucket_delta'],x['dividend_AR_delta'],x['inventory_value_delta'])
 print('OPEN_PAUSED',c['year_2024_OPEN_paused_intervals'])
print('PASS output',str(OUT/'ACCOUNT_2024_INDEPENDENT_AUDIT.json'))
