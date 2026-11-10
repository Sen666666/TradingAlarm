"""Independent saved-clock partitions and stock-period wealth; no account engine."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict, Counter
import csv, json, gzip, hashlib
import audit_pvr_saved as I
getcontext().prec=60
O=I.TASK/'pvr_pool_feasibility/market_phase_2022_2023'; Z=D(0); SOURCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);SOURCES[str(p)]=sha(p);return json.loads(p.read_text())
def stream(p):
 p=Path(p);SOURCES[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:
  for s in f:yield json.loads(s)
def close(a,b):assert abs(D(str(a))-D(str(b)))<D('0.00000001'),(a,b)
def quarter(d):return d[:4]+'Q'+str((int(d[5:7])-1)//3+1)
def main():
 manifests=['SOURCE_SHA256','FUNNEL_SOURCE_SHA256','STOCK_PHASE_SOURCE_SHA256','BENCHMARK_JOIN_SHA256','REENTRY_SPLIT_SOURCE_SHA256','PUBLISH_SOURCE_SHA256']
 frozen={}
 for name in manifests:
  for p,h in read(O/(name+'.json')).items():
   assert p not in frozen or frozen[p]==h;frozen[p]=h
 for p,h in frozen.items():assert sha(p)==h,p
 with (I.TASK/'benchmark_2022_2023/inputs/HS300_daily.csv').open() as f:idx=list(csv.DictReader(f))
 dates=[r['date']for r in idx];assert len(dates)==len(set(dates))==484
 source=next(Path(p)for p in frozen if p.endswith('/canonical/USZI399300.csv'))
 with source.open() as f:hist={r['date']:D(r['close'])for r in csv.DictReader(f)}
 assert max(d for d in hist if d<dates[0])=='2021-12-31'
 # Independently reconstruct alternating extrema with a fixed10% confirmation.
 days=['2021-12-31']+dates;p=[hist[d]for d in days];extrema=[0];mode=0;hi=lo=0;conf={0:days[0]}
 for j in range(1,len(p)):
  if not mode:
   hi=max((hi,j),key=lambda k:p[k]);lo=min((lo,j),key=lambda k:p[k])
   k=hi if p[j]<=p[hi]*D('.9') else lo if p[j]>=p[lo]*D('1.1') else None
   if k is not None:
    if k>extrema[-1]:extrema.append(k);conf[k]=days[j]
    mode=-1 if k==hi else 1;hi=lo=j
  elif mode>0:
   if p[j]>p[hi]:hi=j
   elif p[j]<=p[hi]*D('.9'):
    if hi>extrema[-1]:extrema.append(hi);conf[hi]=days[j]
    mode=-1;lo=j
  else:
   if p[j]<p[lo]:lo=j
   elif p[j]>=p[lo]*D('1.1'):
    if lo>extrema[-1]:extrema.append(lo);conf[lo]=days[j]
    mode=1;hi=j
 if extrema[-1]!=len(p)-1:extrema.append(len(p)-1);conf[len(p)-1]=None
 legs=read(O/'HS300_ALL_LEGS.json');assert len(legs)==len(extrema)-1==5
 phase={}
 for r,a,b in zip(legs,extrema,extrema[1:]):
  assert (r['left'],r['right'],r['right_pivot_confirmed_at'])==(days[a],days[b],conf[b])
  close(r['HS300_return_pct'],(p[b]/p[a]-1)*100)
  for d in days[a+1:b+1]:assert d not in phase;phase[d]=r['id']
 assert list(phase)==dates
 allrows=read(O/'ALL_PERIODS.json');fd=read(O/'FUNNEL_DAILY.json');fp=read(O/'FUNNEL_ALL_PERIODS.json');stock=read(O/'ALL_PHASE_STOCK_WEALTH.json')
 aligned=read(O/'DAILY_ALIGNED.json');ourcampaigns=read(I.HERE/'PVR_2023_INDEPENDENT_AUDIT_CAMPAIGNS.json')
 configs={'NO60':I.TASK/'pvr_pool_feasibility/continuation2023/run-2023/pair','PVR':I.W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/run-2023/pair'}
 answer={};stockcount=0;observations=0
 for label,root in configs.items():
  b=I.read(root/'B.json.gz');native=list(stream(root/'daily.jsonl.gz'));ds={r['at'][:10]:r for r in native};assert list(ds)==dates
  prev=D(1000000);pe=Z;pon=True
  for d,r in zip(dates,aligned[label]):
   x=ds[d];close(r['NAV_begin'],prev);close(r['NAV_end'],x['nav']);close(r['wealth_change'],D(x['nav'])-prev)
   close(r['lag_exposure_pct'],pe);assert r['ACT_at_OPEN']==pon
   prev=D(x['nav']);pe=D(x['inventory'])/prev*100;pon=x['on']
  groupings={'month':lambda d:d[:7],'quarter':quarter,'HS300_zigzag10_leg':lambda d:phase[d]}
  for grain,key in groupings.items():
   groups=defaultdict(list)
   for d in dates:groups[key(d)].append(d)
   rr=[r for r in allrows if r['policy']==label and r['grain']==grain];assert len(rr)==len(groups)
   for r in rr:
    dd=groups[r['period']];assert (r['start'],r['end'],r['days'])==(dd[0],dd[-1],len(dd))
    k=dates.index(dd[0]);begin=D(native[k-1]['nav'])if k else D(1000000);end=D(ds[dd[-1]]['nav'])
    close(r['begin_NAV'],begin);close(r['end_NAV'],end);close(r['net_PnL'],end-begin);close(r['return_pct'],(end/begin-1)*100)
    close(r['mean_lag_exposure_pct'],sum((D(x['lag_exposure_pct'])for x in aligned[label]if x['day']in dd),Z)/len(dd))
   close(sum((D(r['net_PnL'])for r in rr),Z),D(native[-1]['nav'])-1000000)
  # Every raw stock-day and all role/barrier denominators independently counted.
  counts={d:Counter()for d in dates}
  for x in stream(root/'opportunities.jsonl.gz'):
   c=counts[x['day']];c['all_stock_days']+=1;c['core_Q_true']+=x['core_Q']is True;c['mobile_Q_true']+=x['mobile_Q']is True
   cp=bool(x['CP1_id']);c['raw_fresh_CP1_stock_days']+=cp
   if cp:c['fresh_CP1_mobile_Q_true']+=x['mobile_Q']is True;c['fresh_CP1_mobile_Q_not_true']+=x['mobile_Q']is not True
   c['eligible_role_events_before_barriers']+=len(x['roles']);c['eligible_stock_days_before_barriers']+=bool(x['roles'])
   bs=x['barriers'];gate=next((k for k in ['ACT_paused','exit_pending','buy_pending']if k in bs),'other_barriers'if bs else'clear')
   for role in x['roles']:c['eligible_'+role]+=1;c['role_barrier_'+gate]+=1;c[role+'_barrier_'+gate]+=1
  for r in fd[label]:
   assert counts[r['day']]['all_stock_days']==1709
   for k,v in counts[r['day']].items():assert r['counts'].get(k,0)==v,(label,r['day'],k)
   observations+=counts[r['day']]['all_stock_days']
  for grain,key in groupings.items():
   groups=defaultdict(Counter)
   for r in fd[label]:groups[key(r['day'])].update(r['counts'])
   for r in fp:
    if r['policy']==label and r['grain']==grain:assert +groups[r['period']]==+Counter(r['counts'])
  actual=read(O/(label+'_ACTUAL_EXECUTABLE_FILLS.json'));byorder=defaultdict(list)
  for j in b['journal']:
   if j['kind']=='real_buy_fill':byorder[j['budget_order']].append(j)
  seen=set()
  for r in actual:
   k='B|'+r['signal_day']+'T15:10:00+08:00|'+r['sid']+'|'+r['role'];assert k not in seen;seen.add(k)
   assert r['actual_fills']==byorder[k];assert dates[dates.index(r['signal_day'])+1]==r['OPEN_day']
   q=r['reserved_quantity'];assert q>=r['legal_minimum_quantity']and(q-r['legal_minimum_quantity'])%r['legal_step']==0
   assert q<=r['frozen_max_quantity']
  assert seen==set(byorder)
  # All stock-period rows, independent raw-price marks and actual cash/div accrual.
  for leg in legs:
   left,right=leg['left'],leg['right'];before=ds.get(left,{'positions':{},'nav':'1000000'});after=ds[right]
   vals=lambda x,d:{s:D(q)*I.price(s,d)for s,q in x['positions'].items()if q}
   a=vals(before,left);z=vals(after,right);flow=defaultdict(lambda:Z);div=defaultdict(lambda:Z);buy=defaultdict(lambda:Z);fees=defaultdict(lambda:Z)
   boughtbefore={t['security_id']for t in b['trades']if t['side']=='buy'and t['at'][:10]<=left}
   for t in b['trades']:
    if left<t['at'][:10]<=right:
     s=t['security_id'];g=D(t['gross_cny']);f=D(t['fees_cny']);flow[s]+=(g if t['side']=='sell'else -g)-f;fees[s]+=f
     if t['side']=='buy':buy[s]+=g+f
   for x in b['audit']:
    if x['kind']=='dividend_accrual':
     y=x['receivable']
     if left<y['ex_at'][:10]<=right:div[y['security_id']]+=D(y['net_local'])
   rr=[r for r in stock[label]if r['leg']==leg['id']];assert {r['sid']for r in rr}==set(a)|set(z)|set(flow)|set(div)
   for r in rr:
    s=r['sid'];v=flow[s]+div[s]+z.get(s,Z)-a.get(s,Z);close(v,r['net_PnL']);close(a.get(s,Z),r['start_inventory']);close(z.get(s,Z),r['end_inventory']);close(buy[s],r['actual_buy_cash']);close(fees[s],r['actual_fees'])
    cohort='carried_stock_at_start_may_have_new_adds'if s in a else'previously_bought_but_flat_reentry'if buy[s]and s in boughtbefore else'new_stock_foothold'if buy[s]else'no_start_inventory_or_new_buy'
    assert r['cohort']==cohort;stockcount+=1
   close(sum((D(r['net_PnL'])for r in rr),Z),D(after['nav'])-D(before['nav']))
  answer[label]={'native_days':484,'complete_period_rows':37,'actual_buy_orders':len(actual),'full_stock_day_population':484*1709}
 # Prior-campaign negative grouping uses our independently recovered flat boundaries.
 split=read(O/'REENTRY_PRIOR_CAMPAIGN_SPLIT.json')
 for r in split['rows']:
  leg=next(x for x in legs if x['id']==r['leg']);phaseby={x['sid']:x for x in stock['NO60']if x['leg']==r['leg']and x['cohort']=='previously_bought_but_flat_reentry'}
  assert {x['sid']for x in r['stocks']}==set(phaseby)
  for x in r['stocks']:
   previous=max((c for c in ourcampaigns['PVR_NO_CONFIRMED60']if c['sid']==x['sid']and c['closed']and c['closed'][:10]<=leg['left']),key=lambda c:c['closed'])
   assert previous['closed']==x['previous_campaign_close'];close(previous['contribution'],x['previous_campaign_net']);close(phaseby[x['sid']]['net_PnL'],x['phase_wealth'])
   assert ('negative'if D(previous['contribution'])<0 else'nonnegative')==x['classification'].removeprefix('last_prior_closed_campaign_')
 bench=read(O/'BENCHMARK_ALL_PERIODS.json');complete=read(O/'COMPLETE_COMPARISON.json');assert len(bench)==148 and len(complete)==222
 for label in ['BUY_HOLD','MA63_90','HS300_PRICE_INDEX','CASH']:
  path=I.TASK/'benchmark_2022_2023/daily'/(label+'.csv');SOURCES[str(path)]=sha(path)
  with path.open()as f:raw=list(csv.DictReader(f))
  assert [x['date']for x in raw]==dates
  for r in [x for x in bench if x['policy']=='benchmark_'+label]:
   dd=[x for x in raw if r['start']<=x['date']<=r['end']];j=dates.index(dd[0]['date']);begin=D(raw[j-1]['NAV'])if j else D(1000000);end=D(dd[-1]['NAV'])
   close(r['begin_NAV'],begin);close(r['end_NAV'],end);close(r['net_PnL'],end-begin);close(r['return_pct'],(end/begin-1)*100)
   if label in ['BUY_HOLD','MA63_90']:assert r['execution_verified']is False
 lookup={(x['policy'],x['grain'],x['period']):x for x in complete};assert len(lookup)==222
 for r in allrows+bench:
  x=lookup[r['policy'],r['grain'],r['period']]
  for k in ['begin_NAV','end_NAV','net_PnL','return_pct','days']:assert x[k]==r[k]
 out={'passed':True,'policies':answer,'complete_native_period_rows':len(allrows),'complete_benchmark_period_rows':len(bench),'complete_comparison_rows':len(complete),'all_stock_period_rows_checked':stockcount,'raw_stock_day_observations':observations,'source_SHA_checks':len(frozen),'reviewer_source_SHA256':sha(__file__),'reviewer_account_events':0,'reviewer_attempts':'First readonly pass stopped on missing-zero Counter serialization; confirmed0 versus absent only, corrected reviewer equality. No producer mutation or account event.','scope':'All24months/8quarters/5fixed retrospective legs partition484 days. Every native/benchmark period NAV and every stock-leg cash/div/rawinventory wealth independently checked. All raw stock-day role/barrier denominators, every actual buy-order join/nextOPEN/legalunit, and all funnel-period sums checked. Detailed unfunded routing outcome classification source-reviewed, not rerun as an alternative portfolio. Retrospective labels, prior failure cohorts and overlapping rejection tags are descriptive only; no avoidable-loss or causal filter claim. ETF execution remains proxy as separately audited.'}
 (I.HERE/'PVR_MARKET_PHASE_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
