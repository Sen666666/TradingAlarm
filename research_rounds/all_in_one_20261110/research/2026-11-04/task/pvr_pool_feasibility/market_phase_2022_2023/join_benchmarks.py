"""Read benchmark-agent results; no benchmark execution or duplicate engine."""
from collections import defaultdict
from decimal import Decimal as D
import csv
import analyze_phase as A
O=A.O
def main():
 cal,anchor,hs=A.load_inputs();_,legs,phase=A.zigzag([anchor]+cal,[hs[d]for d in [anchor]+cal]);rows=[]
 result=A.read(A.BEN/'RESULTS.json')
 latest=A.read(A.BEN/'INDEPENDENT_REVIEW_STATUS.json')
 for name in ['BUY_HOLD','MA63_90','HS300_PRICE_INDEX','CASH']:
  p=A.BEN/'daily'/(name+'.csv');A.SRC[str(p)]=A.sha(p)
  with p.open()as f:daily=list(csv.DictReader(f))
  assert [r['date']for r in daily]==cal
  nav0=D(1000000);prepared=[];prev_expo=D(0)
  for r in daily:
   nav=D(r['NAV']);expo=D(r['market_value'])/nav*100
   prepared.append(dict(day=r['date'],NAV_begin=nav0,NAV_end=nav,wealth_change=nav-nav0,exposure_pct=expo,lag_exposure_pct=prev_expo,cash_pct=D(r['cash'])/nav*100,
    fee=D(r.get('fee','0')),buy_gross=D(r.get('buy_gross','0')),bought=D(r.get('bought','0'))))
   nav0=nav;prev_expo=expo
  for grain,key in [('month',lambda d:d[:7]),('quarter',A.quarter),('HS300_zigzag10_leg',lambda d:phase[d])]:
   groups=defaultdict(list)
   for r in prepared:groups[key(r['day'])].append(r)
   for ident,rs in groups.items():
    first,last=rs[0],rs[-1];peak=first['NAV_begin'];dd=D(0)
    for r in rs:peak=max(peak,r['NAV_end']);dd=max(dd,(1-r['NAV_end']/peak)*100)
    buys=[r['day']for r in rs if r['bought']>0]
    rows.append(dict(policy='benchmark_'+name,grain=grain,period=ident,start=first['day'],end=last['day'],days=len(rs),begin_NAV=first['NAV_begin'],end_NAV=last['NAV_end'],
     net_PnL=last['NAV_end']-first['NAV_begin'],return_pct=(last['NAV_end']/first['NAV_begin']-1)*100,
     mean_lag_exposure_pct=A.mean([r['lag_exposure_pct']for r in rs]),mean_close_exposure_pct=A.mean([r['exposure_pct']for r in rs]),mean_close_cash_pct=A.mean([r['cash_pct']for r in rs]),
     first_actual_buy=buys[0]if buys else None,fees=sum((r['fee']for r in rs),D(0)),maximum_drawdown_within_period_pct=dd,
     execution_verified=False if name in ['BUY_HOLD','MA63_90']else None,index_or_cash_reference_only=name in ['HS300_PRICE_INDEX','CASH'],not_a_candidate_strategy_rerun=True))
   assert sum((x['net_PnL']for x in rows if x['policy']=='benchmark_'+name and x['grain']==grain),D(0))==prepared[-1]['NAV_end']-D(1000000)
 A.save('BENCHMARK_ALL_PERIODS.json',rows);A.save('BENCHMARK_RESULT_BINDING.json',dict(source_result=result,latest_independent_review_status=latest,
  scope='Benchmark engine belongs to pressure agent; this script ONLY partitions existing daily NAVs on the same retrospective labels',
  execution_scope='ETF daily raw-open proxy; dated limit/halt state absent, not an independent fillability certification',
  fee_scope='ETF frozen portfolio protocol uses estimated15bp one-way friction/min5 on raw OPEN, no extra slip; not broker quotation and differs from stock native fees+slip. Use source direct-cost bridge only, no exposure rescaling or cost-free trade-path claims',
  identical_484_calendar=True,all_24_months_8_quarters_and5_legs=True))
 A.SRC[str(__file__)]=A.sha(__file__);A.save('BENCHMARK_JOIN_SHA256.json',A.SRC)
 print('READ_ONLY_BENCHMARK_JOIN_PASS',len(rows))
if __name__=='__main__':main()
