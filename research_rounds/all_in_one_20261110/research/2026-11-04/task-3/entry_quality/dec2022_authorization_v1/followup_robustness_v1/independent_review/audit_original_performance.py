"""Thin existing-output audit of original72 periods and270 concentration bridges."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter,defaultdict
import json,gzip,hashlib
import pandas as pd
getcontext().prec=65
O=Path(__file__).resolve().parent;F=O.parent;P=F.parent;R=P.parent/'trend_exit_controls_v1';C=P/'account_comparison/results_v1';Q=F/'performance/results_v1';Z=D(0);I=D(1000000);checks=Counter();SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def near(a,b,k):assert abs(D(str(a))-D(str(b)))<D('.000001'),(k,a,b);checks[k]+=1
prior=read(P/'independent_review/H2_COMPARISON_MATRIX_DEC_TAIL_AUDIT.json');assert prior['status']=='PASS_ALL_32_PERIODS_DEC_WEALTH_CAPITAL_AND_FIXED_TAILS'
for p,h in prior['source_sha256'].items():assert sha(p)==h
for name in ['SOURCE_SHA256.json','DELIVERABLE_SHA256.json','INCREMENTAL_SOURCE_SHA256.json']:
 for p,h in read(Q/name).items():assert sha(p)==h;checks['performance_source_and_output_SHA']+=1
rows=read(Q/'FIXED_PERIOD_PERFORMANCE.json');assert len(rows)==72;inc=read(Q/'INCREMENTAL_CONCENTRATION_SUMMARY.json');assert len(inc)==270;detail={};runcache={}
freeze=read(F/'performance/SEMICONDUCTOR_COHORT_FREEZE.json');semi={x['sid'] for x in freeze['all_metadata_members'] if x['in_frozen1709']};assert len(semi)==126
SM={m['symbol']:m for m in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};FR={}
def quote(sid,day):
 if sid not in FR:
  p=SM[sid]['refs']['facts'];assert sha(p)==SM[sid]['output_sha256'][p];FR[sid]=pd.read_parquet(p,columns=['raw_close'])
 f=FR[sid];j=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert j>=0;return D(str(f.raw_close.iloc[j]))
def stockwealth(run,sid,j):
 if j<0:return Z
 d=run['raw'][j];held={x['id']:x for x in d['layers']};v=Z
 for l in run['book']['layers']:
  if l['sid']!=sid or l['opened']>d['at']:continue
  if l['id'] in held:h=held[l['id']];v+=D(h['cash'])+D(h['qty'])*quote(sid,d['at'][:10])+D(h['dividend'])
  else:assert l['closed'] and l['closed']<=d['at'];v+=D(l['cash'])+D(l['dividend'])
 return v
for x in rows:
 arm=x['arm'];win=x['window'];k=(arm,win)
 if k not in runcache:
  out=(R if arm=='BASELINE' else P)/'runs'/arm/win;runcache[k]=dict(raw=read(out/'pair/daily.jsonl.gz',True),book=read(out/'pair/B.json.gz'),led=read(C/f'{arm}_{win}_DAILY_WEALTH_SPLIT.json'))
 run=runcache[k];raw=run['raw'];led=run['led'];ix=[j for j,d in enumerate(raw) if x['start']<=d['at'][:10]<=x['end']];sel=[raw[j] for j in ix];prevs=[raw[j-1] if j else dict(nav=str(I),inventory='0') for j in ix];priorrow=raw[ix[0]-1] if ix[0] else dict(nav=str(I));beg=D(priorrow['nav']);end=D(sel[-1]['nav']);mean=sum((D(d['nav']) for d in sel),Z)/len(sel);pmean=sum((D(d['nav']) for d in prevs),Z)/len(sel);peak=beg;dd=Z
 for d in sel:peak=max(peak,D(d['nav']));dd=max(dd,1-D(d['nav'])/peak)
 trades=[t for t in run['book']['trades'] if x['start']<=t['at'][:10]<=x['end']];buy=sum((D(t['gross_cny']) for t in trades if t['side']=='buy'),Z);sell=sum((D(t['gross_cny']) for t in trades if t['side']=='sell'),Z)
 expected=dict(observations=len(sel),NAV_begin=beg,NAV_end=end,net_wealth_change=end-beg,return_fraction=end/beg-1,period_rebased_max_DD=dd,maximum_account_DD_from_entire_account_path_peak=max(D(d['drawdown_from_full_path_peak']) for d in led[ix[0]:ix[-1]+1]),mean_CLOSE_NAV=mean,mean_previous_CLOSE_NAV=pmean,mean_CLOSE_exposure=sum((D(d['inventory'])/D(d['nav']) for d in sel),Z)/len(sel),mean_previous_CLOSE_exposure=sum((D(d['inventory'])/D(d['nav']) for d in prevs),Z)/len(sel),mean_CLOSE_inventory=sum((D(d['inventory']) for d in sel),Z)/len(sel),mean_previous_CLOSE_inventory=sum((D(d['inventory']) for d in prevs),Z)/len(sel),fees=sum((D(t['fees_cny']) for t in trades),Z),buy_gross=buy,sell_gross=sell,buy_plus_sell_gross=buy+sell,buy_gross_over_mean_CLOSE_NAV=buy/mean,sell_gross_over_mean_CLOSE_NAV=sell/mean,two_sided_gross_over_mean_CLOSE_NAV=(buy+sell)/mean,conventional_oneway_turnover_over_mean_CLOSE_NAV=(buy+sell)/2/mean,actual_buycash=sum((D(t['gross_cny'])+D(t['fees_cny']) for t in trades if t['side']=='buy'),Z),actual_sell_net=sum((D(t['gross_cny'])-D(t['fees_cny']) for t in trades if t['side']=='sell'),Z),buy_fills=sum(t['side']=='buy' for t in trades),sell_fills=sum(t['side']=='sell' for t in trades),ACT_paused_closes=sum(not d['on'] for d in sel))
 for new,old in [('strict_realized_change','strict_realized'),('open_unrealized_change','open_unrealized'),('AR_change','AR')]:expected[new]=D(led[ix[-1]][old])-(D(led[ix[0]-1][old]) if ix[0] else Z)
 for field,v in expected.items():near(x[field],v,'period_'+field)
 assert x['first_observed']==sel[0]['at'][:10] and x['last_observed']==sel[-1]['at'][:10];d=read(Q/f'{arm}_{x["period"]}_DETAIL.json');detail[arm,x['period']]=d
 # Full grouping/cohort arithmetic; representative top stock independently re-marked.
 for dimension,rr in d['group_rows'].items():
  near(sum((D(r['wealth']) for r in rr),Z),end-beg,'all_group_NAV_bridge');positive=sorted([r for r in rr if D(r['wealth'])>0],key=lambda r:D(r['wealth']),reverse=True);totalpos=sum((D(r['wealth']) for r in positive),Z);conc=x['concentration'][dimension]
  near(conc['net'],end-beg,'concentration_net');near(conc['gross_positive'],totalpos,'concentration_positive');near(conc['gross_negative'],sum((min(Z,D(r['wealth'])) for r in rr),Z),'concentration_negative')
  for n in [1,5,10]:
   top=conc['top'][str(n)];assert top['groups']==[r['group'] for r in positive[:n]];v=sum((D(r['wealth']) for r in positive[:n]),Z);near(top['positive_contribution'],v,'concentration_top_amount');near(top['descriptive_net_after_subtracting_these_contributions'],end-beg-v,'concentration_remaining')
   if totalpos:near(top['share_of_gross_positive'],v/totalpos,'concentration_top_share')
   else:assert top['share_of_gross_positive'] is None
  if totalpos:near(conc['positive_share_HHI'],sum(((D(r['wealth'])/totalpos)**2 for r in positive),Z),'concentration_HHI')
  else:assert conc['positive_share_HHI'] is None
  if dimension=='stock' and positive:
   top=positive[0];near(top['wealth'],stockwealth(run,top['group'],ix[-1])-stockwealth(run,top['group'],ix[0]-1),'independent_top_stock_boundary_rawwealth')
  if dimension in ['day','week','month']:
   groups=defaultdict(lambda:Z)
   for j in ix:
    day=raw[j]['at'][:10];dt=pd.Timestamp(day);ic=dt.isocalendar();label=day if dimension=='day' else day[:7] if dimension=='month' else f'{ic.year}-W{ic.week:02d}';groups[label]+=D(raw[j]['nav'])-(D(raw[j-1]['nav']) if j else I)
   assert set(groups)=={r['group'] for r in rr}
   for r in rr:near(r['wealth'],groups[r['group']],'independent_time_group_NAV_wealth')
 stock={r['group']:r for r in d['group_rows']['stock']};assert {r['sid'] for r in d['semiconductor']['rows']}==semi
 for r in d['semiconductor']['rows']:
  for field in ['real','unreal','AR','wealth']:near(r[field],stock.get(r['sid'],{}).get(field,0),'all126_semi_source_group_component')
 for field in ['real','unreal','AR','wealth']:near(d['semiconductor']['components'][field],sum((D(r[field]) for r in d['semiconductor']['rows']),Z),'semiconductor_total')
 checks['periods']+=1
lookup={(x['arm'],x['period']):x for x in rows}
for s in inc:
 arm,period,dim=s['arm'],s['period'],s['grouping'];b={r['group']:r for r in detail['BASELINE',period]['group_rows'][dim]};a={r['group']:r for r in detail[arm,period]['group_rows'][dim]};g=[(k,D(a.get(k,{}).get('wealth','0'))-D(b.get(k,{}).get('wealth','0'))) for k in sorted(a.keys()|b.keys())];g.sort(key=lambda r:r[1],reverse=True);pos=[r for r in g if r[1]>0];total=sum((v for k,v in g),Z);positive=sum((v for k,v in pos),Z);negative=sum((min(Z,v) for k,v in g),Z);assert s['groups']==len(g) and s['positive_groups']==len(pos);near(s['net_difference'],total,'incremental_net');near(total,D(lookup[arm,period]['net_wealth_change'])-D(lookup['BASELINE',period]['net_wealth_change']),'incremental_actual_account_delta');near(s['positive_difference'],positive,'incremental_positive');near(s['negative_difference'],negative,'incremental_negative')
 for n in [1,5,10]:
  top=s['top'][str(n)];assert top['groups']==[k for k,v in pos[:n]];v=sum((v for k,v in pos[:n]),Z);near(top['positive_difference'],v,'incremental_top_amount');near(top['descriptive_net_after_subtracting_these_positive_differences'],total-v,'incremental_remaining')
  if positive:near(top['share_of_all_positive_differences'],v/positive,'incremental_top_share')
  else:assert top['share_of_all_positive_differences'] is None
 if positive:near(s['positive_share_HHI'],sum(((v/positive)**2 for k,v in pos),Z),'incremental_HHI')
 else:assert s['positive_share_HHI'] is None
 checks['incremental_groupings']+=1
result=dict(status='PASS_THIN_ORIGINAL72_PERIODS_270_INCREMENTAL_BRIDGES',checks=dict(checks),source_sha256=SRC,script_sha256=sha(__file__),new_accounts=0,limits=['All72 original-row financial metrics independently reconstructed from raw daily/trades and previously audited daily wealth components. No old account/indicator rerun.','All group arithmetic and270 incremental positive/negative/top/HHI bridges checked. Only each period top positive stock boundary independently re-marked; all old individual stock attributions were not regenerated.','Concentration subtraction is descriptive, not a removal/backtest/causal strategy result. Semiconductors retain all126 snapshot members; zeros are actual unallocated contribution, not missing-stock price returns.','2025H2 and2026H1 explicitly partial years on independent strong account; no2022→2026 unbroken account or annualized extrapolation.'])
(O/'ORIGINAL72_PERFORMANCE_270_CONCENTRATION_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=result['status'],checks=dict(checks)),ensure_ascii=False,indent=2))
