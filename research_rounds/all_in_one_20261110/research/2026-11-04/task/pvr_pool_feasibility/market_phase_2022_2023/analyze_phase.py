"""All calendar periods + fixed retrospective HS300 zigzag, no policy events."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter,defaultdict
import csv,gzip,hashlib,json,statistics
O=Path(__file__).resolve().parent;T=O.parents[1]
FIN=T/'risk_constraints/absolute_loss_2022_2023';BEN=T/'benchmark_2022_2023'
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101')
ROOT=O.parent
CONFIG={
 'NO60':dict(native=ROOT/'continuation2023/run-2023/pair',finance=FIN/'NO60_2022_2023_DAILY.json',sector=FIN/'NO60_2022_2023_SECTOR_DAILY.json'),
 'PVR':dict(native=OLD/'continuation-2023-readiness/run-2023/pair',finance=FIN/'PVR_2022_2023_DAILY.json',sector=FIN/'PVR_2022_2023_SECTOR_DAILY.json')}
SRC={}
getcontext().prec=50
FINANCE_WEALTH_MAX_DIFF={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def stream(p):
 p=Path(p);SRC[str(p)]=sha(p)
 with gzip.open(p,'rt')as f:
  for line in f:yield json.loads(line)
def book(p):
 p=Path(p);SRC[str(p)]=sha(p)
 with gzip.open(p,'rt')as f:return json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def quarter(d):return d[:4]+'Q'+str((int(d[5:7])-1)//3+1)
def mean(x):return sum(x,D(0))/len(x)if x else None
def zigzag(dates,prices):
 """One10% reversal, pivot dates and their later confirmation preserved."""
 piv=[dict(index=0,day=dates[0],price=prices[0],kind='left_anchor',confirmed_at=dates[0])]
 direction=0;hi=lo=0
 def add(i,kind,confirmed):
  if i>piv[-1]['index']:piv.append(dict(index=i,day=dates[i],price=prices[i],kind=kind,confirmed_at=confirmed))
 for i,p in enumerate(prices[1:],1):
  if direction==0:
   if p>prices[hi]:hi=i
   if p<prices[lo]:lo=i
   if p<=prices[hi]*D('.9'):add(hi,'peak',dates[i]);direction=-1;lo=i
   elif p>=prices[lo]*D('1.1'):add(lo,'trough',dates[i]);direction=1;hi=i
  elif direction==1:
   if p>prices[hi]:hi=i
   elif p<=prices[hi]*D('.9'):add(hi,'peak',dates[i]);direction=-1;lo=i
  else:
   if p<prices[lo]:lo=i
   elif p>=prices[lo]*D('1.1'):add(lo,'trough',dates[i]);direction=1;hi=i
 if piv[-1]['index']<len(dates)-1:add(len(dates)-1,'right_censored_endpoint',None)
 legs=[];assigned={}
 for k,(a,b)in enumerate(zip(piv,piv[1:]),1):
  ret=(b['price']/a['price']-1)*100;ident=f'L{k:02d}'
  leg=dict(id=ident,left=a['day'],right=b['day'],direction='UP'if ret>0 else'DOWN'if ret<0 else'FLAT',HS300_return_pct=ret,
   left_pivot_kind=a['kind'],right_pivot_kind=b['kind'],right_pivot_confirmed_at=b['confirmed_at'],right_censored=b['confirmed_at']is None,
   first_analysis_day=dates[a['index']+1],last_analysis_day=b['day'],days=b['index']-a['index'],retrospective_only=True)
  legs.append(leg)
  for d in dates[a['index']+1:b['index']+1]:assert d not in assigned;assigned[d]=ident
 return piv,legs,assigned

def load_inputs():
 freeze=read(BEN/'INPUT_FREEZE.json')
 for p,h in freeze['inputs'].items():assert sha(p)==h
 index_path=next(Path(p)for p in freeze['sources']if p.endswith('/canonical/USZI399300.csv'))
 assert sha(index_path)==freeze['sources'][str(index_path)];SRC[str(index_path)]=sha(index_path)
 with index_path.open()as f:hist=list(csv.DictReader(f))
 close={x['date']:D(x['close'])for x in hist}
 fp=BEN/'inputs/HS300_daily.csv';SRC[str(fp)]=sha(fp)
 with fp.open()as f:hs=list(csv.DictReader(f))
 dates=[x['date']for x in hs];assert len(dates)==len(set(dates))==484
 assert all(D(x['close'])==close[x['date']]for x in hs)
 anchor=max(d for d in close if d<dates[0]);assert anchor=='2021-12-31'
 return dates,anchor,close

def load_policy(label,conf,dates):
 raw={x['at'][:10]:x for x in stream(conf['native']/'daily.jsonl.gz')};fin={x['day']:x for x in read(conf['finance'])}
 assert list(raw)==list(fin)==dates
 out=[];prev_nav=D(1000000);prev_on=True;prev_expo=D(0)
 maxdiff=D(0)
 for d in dates:
  x=raw[d];f=fin[d];nav=D(x['nav']);wealth=nav-prev_nav
  difference=abs(wealth-D(f['wealth_change']));maxdiff=max(maxdiff,difference)
  assert difference<D('.00000001')and nav==D(f['NAV_end'])and prev_nav==D(f['NAV_begin'])
  assert D(x['available'])==D(f['available_cash'])and bool(x['on'])==f['ACT_after_CLOSE']and prev_on==f['ACT_at_OPEN']
  expo=D(x['inventory'])/nav*100;assert abs(expo-D(f['exposure_pct']))<D('1e-20')
  y=dict(f,policy=label,day=d,nav=nav,wealth_change=wealth,exposure_pct=expo,lag_exposure_pct=prev_expo,
   cash_pct=D(x['available'])/nav*100,committed_pct=D(str(x['pool_probe'][0]+x['pool_confirmed'][0]))/nav*100,
   pending_intents=x['pending_intents'],pending_exits=len(x['pending_sells']),held_stocks=len(x['positions']))
  out.append(y);prev_nav=nav;prev_on=bool(x['on']);prev_expo=expo
 FINANCE_WEALTH_MAX_DIFF[label]=maxdiff
 return out

def aggregate(rows,ident,kind,hs,anchor):
 a=rows[0];b=rows[-1];begin=D(a['NAV_begin']);end=D(b['NAV_end']);wealth=end-begin
 assert wealth==sum((D(r['wealth_change'])for r in rows),D(0))
 first_index=CAL.index(a['day']);left=CAL[first_index-1]if first_index else anchor
 buys=[r['day']for r in rows if r['buy_fills']];ons=[r['day']for r in rows if r['ACT_at_OPEN']]
 peak=begin;mdd=D(0)
 for r in rows:peak=max(peak,D(r['NAV_end']));mdd=max(mdd,(1-D(r['NAV_end'])/peak)*100)
 return dict(policy=a['policy'],grain=kind,period=ident,start=a['day'],end=b['day'],days=len(rows),begin_NAV=begin,end_NAV=end,
  net_PnL=wealth,return_pct=(end/begin-1)*100,HS300_return_pct=(hs[b['day']]/hs[left]-1)*100,HS300_left_close_reference_day=left,
  HS300_first_period_aligned_to_Jan4_close_pct=(hs[b['day']]/hs[CAL[0]]-1)*100 if first_index==0 else None,
  actual_fees=sum((D(r['actual_fees'])for r in rows),D(0)),actual_buy_cash=sum((D(r['actual_buy_cash'])for r in rows),D(0)),actual_sell_net=sum((D(r['actual_sell_net'])for r in rows),D(0)),
  buy_fills=sum(r['buy_fills']for r in rows),sell_fills=sum(r['sell_fills']for r in rows),
  mean_lag_exposure_pct=mean([r['lag_exposure_pct']for r in rows]),mean_close_exposure_pct=mean([r['exposure_pct']for r in rows]),
  mean_close_committed_pct=mean([r['committed_pct']for r in rows]),mean_close_cash_pct=mean([r['cash_pct']for r in rows]),
  start_lag_exposure_pct=a['lag_exposure_pct'],end_close_exposure_pct=b['exposure_pct'],end_cash_pct=b['cash_pct'],
  ACT_active_OPEN_days=sum(r['ACT_at_OPEN']for r in rows),ACT_paused_OPEN_days=sum(not r['ACT_at_OPEN']for r in rows),
  ACT_paused_CLOSE_days=sum(not r['ACT_after_CLOSE']for r in rows),ACT_at_first_OPEN=a['ACT_at_OPEN'],first_active_OPEN=ons[0]if ons else None,
  first_actual_buy=buys[0]if buys else None,days_to_first_actual_buy=CAL.index(buys[0])-first_index if buys else None,
  peak_close_exposure_pct=max(r['exposure_pct']for r in rows),maximum_drawdown_within_period_pct=mdd,
  phase_label_not_available_in_real_time=kind=='HS300_zigzag10_leg')

def phase_sector_contributions(conf,phases):
 by=defaultdict(lambda:defaultdict(lambda:dict(net=D(0),buy_cash=D(0),exposure_sum=D(0),days=0,industry=None)))
 for r in read(conf['sector']):
  leg=phases[r['day']];x=by[leg][r['sector']];x['net']+=D(r['wealth_change']);x['buy_cash']+=D(r['actual_buy_cash']);x['exposure_sum']+=D(r['exposure_pct']);x['days']+=1;x['industry']=r['industry']
 out={}
 for leg,sectors in by.items():
  rows=[dict(sector=s,industry=x['industry'],net_PnL=x['net'],actual_buy_cash=x['buy_cash'],mean_exposure_pct=x['exposure_sum']/x['days'])for s,x in sectors.items()]
  out[leg]=sorted(rows,key=lambda x:x['net_PnL'])
 return out

def main():
 global CAL
 CAL,anchor,hs=load_inputs();piv,legs,phases=zigzag([anchor]+CAL,[hs[d]for d in [anchor]+CAL]);assert set(phases)==set(CAL)
 save('HS300_PIVOTS.json',piv);save('HS300_ALL_LEGS.json',legs)
 assert len({d[:7]for d in CAL})==24 and len({quarter(d)for d in CAL})==8
 allrows=[];all_daily={};sectors={}
 for label,conf in CONFIG.items():
  daily=load_policy(label,conf,CAL);all_daily[label]=daily;groupings=[('month',lambda d:d[:7]),('quarter',quarter),('HS300_zigzag10_leg',lambda d:phases[d])]
  for grain,key in groupings:
   groups=defaultdict(list)
   for r in daily:groups[key(r['day'])].append(r)
   table=[aggregate(rs,k,grain,hs,anchor)for k,rs in groups.items()]
   assert sum((r['net_PnL']for r in table),D(0))==daily[-1]['nav']-D(1000000)
   allrows.extend(table)
  sectors[label]=phase_sector_contributions(conf,phases)
 save('ALL_PERIODS.json',allrows);save('DAILY_ALIGNED.json',all_daily);save('PHASE_SECTOR_CONTRIBUTIONS.json',sectors)
 selected={}
 n=[x for x in allrows if x['policy']=='NO60'and x['grain']=='HS300_zigzag10_leg']
 byid={x['id']:x for x in legs}
 for typ,condition,key in [('negative_UP',lambda x:byid[x['period']]['direction']=='UP'and not byid[x['period']]['right_censored']and x['net_PnL']<0,lambda x:x['net_PnL']),
  ('worst_DOWN',lambda x:byid[x['period']]['direction']=='DOWN'and x['net_PnL']<0,lambda x:x['net_PnL']),
  ('best_positive_UP',lambda x:byid[x['period']]['direction']=='UP'and x['net_PnL']>0,lambda x:-x['net_PnL'])]:
  candidates=[x for x in n if condition(x)];selected[typ]=min(candidates,key=lambda x:(key(x),x['start']))if candidates else None
 save('CASE_SELECTION.json',dict(selection=selected,retrospective_diagnostic_only=True,all_other_legs_retained=True))
 def fmt(x):return f'{float(x):,.2f}'
 lines=['全部24月/8季度及HS300固定10%事后阶段；只读归因。',f'HS300 anchor={anchor}；全484日无遗漏。价格指数不是可交易收益，标签不进入任何实时信号。','']
 for grain in ['quarter','HS300_zigzag10_leg']:
  lines.append(grain)
  for row in [r for r in allrows if r['policy']=='NO60'and r['grain']==grain]:
   lines.append(f"{row['period']} {row['start']}..{row['end']} HS300{fmt(row['HS300_return_pct'])}% | NO60 {fmt(row['net_PnL'])}/{fmt(row['return_pct'])}% lagExpo{fmt(row['mean_lag_exposure_pct'])}% cash{fmt(row['mean_close_cash_pct'])}% ACTpause{row['ACT_paused_OPEN_days']}/{row['days']} actualBuy{fmt(row['actual_buy_cash'])}")
  lines.append('')
 lines+=['下一步将把各阶段全部原Q/CP1/角色/size/优先→route/实单补齐；当前金额已逐日与原账及独审finance日桥核同。','不从事后底顶计算可得利润；ETF实际MA63 long-only由benchmark agent单独计算。']
 (O/'FIRST_READOUT.txt').write_text('\n'.join(lines)+'\n')
 SRC[str(Path(__file__))]=sha(__file__);SRC[str(O/'PROTOCOL.txt')]=sha(O/'PROTOCOL.txt');save('SOURCE_SHA256.json',SRC)
 for p,h in SRC.items():assert sha(p)==h
 save('PHASE_AGGREGATION_GATE.json',dict(passed=True,days=484,months_per_policy=24,quarters_per_policy=8,phase_legs=len(legs),
  policy_count=2,all_calendar_and_phase_PnL_partitions_exact=True,source_finance_day_bridges_crosschecked_with_native=True,finance_day_wealth_max_abs_difference=FINANCE_WEALTH_MAX_DIFF,
  fixed_one_threshold_pct=10,phase_tags_only_ex_post=True,account_events=0,new_strategy_runs=0))
 print('\n'.join(lines))
if __name__=='__main__':main()
